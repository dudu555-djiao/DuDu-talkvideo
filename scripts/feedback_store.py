"""Atomic, project-local workbench snapshots and original attachment bytes."""
import base64
import datetime
import hashlib
import json
from pathlib import Path
import re
import threading
import uuid


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class FeedbackConflict(ValueError):
    def __init__(self, revision, path):
        self.revision, self.path = revision, path
        super().__init__('另一个页面已更新意见；当前修改已另存冲突备份，未覆盖项目意见。')


class FeedbackStore:
    def __init__(self, project):
        self.project = Path(project).resolve()
        page = (self.project / 'review/index.html').read_text(encoding='utf-8')
        match = re.search(r'<script id="workbench-data" type="application/json">(.*?)</script>', page, re.S)
        if not match:
            raise ValueError('工作台缺少项目身份。')
        self.project_id = json.loads(match[1])['episodeKey']
        self.folder = self.project / 'feedback'
        self.latest = self.folder / 'latest.json'
        self.lock = threading.RLock()

    def load(self):
        with self.lock:
            if not self.latest.exists():
                return None
            value = json.loads(self.latest.read_text(encoding='utf-8'))
            if value.get('projectId') != self.project_id or value.get('syncSchemaVersion') != 1:
                raise ValueError('项目意见文件身份不匹配，未覆盖。')
            return value

    def upload(self, value):
        sha = value.get('sha256', '')
        if not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('附件 SHA256 无效。')
        match = re.fullmatch(r'data:([^,]*);base64,([A-Za-z0-9+/=\r\n]*)', value.get('dataUrl', ''))
        if not match:
            raise ValueError('附件缺少原始字节。')
        raw = base64.b64decode(match[2], validate=True)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('附件字节与 SHA256 不符。')
        name = re.sub(r'[^\w.\-\u3400-\u9fff]+', '_', str(value.get('name') or 'attachment'))[:100].strip('.') or 'attachment'
        target = self.folder / 'attachments' / (sha + '-' + name)
        with self.lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                    raise ValueError('已有附件字节已变化，未覆盖。')
            else:
                temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
                try:
                    temporary.write_bytes(raw)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
        return {'path': str(target.relative_to(self.project)), 'sha256': sha, 'bytes': len(raw),
                'mimeType': str(value.get('mimeType') or 'application/octet-stream')}

    def validate_files(self, assets):
        if not isinstance(assets, list):
            raise ValueError('附件清单须为数组。')
        ids = set()
        for asset in assets:
            if not isinstance(asset, dict) or not isinstance(asset.get('id'), str) or asset['id'] in ids:
                raise ValueError('附件身份缺失或重复。')
            ids.add(asset['id'])
            files = asset.get('files', []) if asset.get('kind') == 'folder' else [asset]
            if not isinstance(files, list):
                raise ValueError('文件夹附件清单无效。')
            for item in files:
                ref = item.get('file', {})
                sha = ref.get('sha256', '')
                if not re.fullmatch(r'[0-9a-f]{64}', sha):
                    raise ValueError('附件缺少字节指纹。')
                relative = ref.get('path', '')
                path = (self.project / relative).resolve()
                expected = (self.folder / 'attachments').resolve()
                if not path.is_relative_to(expected) or not path.is_file() or not path.name.startswith(sha + '-'):
                    raise ValueError('附件路径无效或文件不存在。')
                if path.stat().st_size != ref.get('bytes') or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                    raise ValueError('附件原始字节校验失败。')
        return ids

    def save(self, value):
        if value.get('projectId') != self.project_id:
            raise ValueError('不是当前工作台项目。')
        store, assets = value.get('store'), value.get('assets')
        if not isinstance(store, dict) or store.get('schemaVersion') != 5 or not isinstance(store.get('records'), dict):
            raise ValueError('意见存储格式无效。')
        asset_ids = self.validate_files(assets)
        def check_refs(value):
            if isinstance(value, list):
                for item in value:
                    check_refs(item)
            elif isinstance(value, dict):
                if value.get('type') in {'image', 'file', 'folder'} and value.get('id') and not (value.get('dataUrl') or value.get('files')):
                    if value['id'] not in asset_ids:
                        raise ValueError('意见或历史引用的原始附件尚未保存：' + str(value['id']))
                for item in value.values():
                    check_refs(item)
        check_refs(store)
        context = value.get('context', {})
        if not isinstance(context, dict) or context.get('episodeKey') != self.project_id:
            raise ValueError('意见上下文身份不匹配。')
        with self.lock:
            current = self.load()
            revision = current['revision'] if current else 0
            if type(value.get('baseRevision')) is not int or value['baseRevision'] != revision:
                conflict = self.folder / 'conflicts' / (uuid.uuid4().hex + '.json')
                atomic_json(conflict, {'savedAt': timestamp(), 'currentRevision': revision, 'incoming': value,
                                       'workflowApproved': False, 'note': '保留另一份意见，未替换 latest.json。'})
                raise FeedbackConflict(revision, str(conflict.relative_to(self.project)))
            by_id = {asset['id']: asset for asset in assets}

            def expand(value):
                if isinstance(value, list):
                    return [expand(item) for item in value]
                if not isinstance(value, dict):
                    return value
                result = {key: expand(item) for key, item in value.items()}
                asset = by_id.get(value.get('id')) if isinstance(value.get('id'), str) else None
                if asset and value.get('type') in {'image', 'file', 'folder'}:
                    result['name'] = asset.get('name')
                    if asset.get('kind') == 'folder':
                        result.update(directories=asset.get('directories', []), files=[
                            {**{key: item for key, item in f.items() if key != 'file'}, **f['file']} for f in asset['files']])
                    else:
                        result.update(asset['file'])
                return result

            metadata = context.get('metadata', [])
            identity = lambda item: json.dumps([item.get(key) for key in ('stableId', 'view', 'itemId', 'identity')], ensure_ascii=False, separators=(',', ':'))
            current_keys = {identity(item) for item in metadata}
            records = dict(store['records'])
            for item in metadata:
                records.setdefault(identity(item), {**item, 'note': '', 'choice': '', 'content': []})
            snapshot = {'syncSchemaVersion': 1, 'projectId': self.project_id, 'revision': revision + 1,
                        'savedAt': timestamp(), 'workflowApproved': False, 'context': context,
                        'store': store, 'assets': assets,
                        'records': [{**expand(row), 'current': key in current_keys} for key, row in records.items()],
                        'legacyFeedback': expand(store.get('legacy', {})),
                        'workbench': expand(store.get('workbench', {}))}
            # Immutable revisions preserve text, undo history, attachments and proposal states.
            atomic_json(self.folder / 'revisions' / f'{revision + 1:08d}.json', snapshot)
            atomic_json(self.latest, snapshot)
            return snapshot
