#!/usr/bin/env python3
"""Bind a storyboard to the preserved, project-enhanced review workbench.

Does not approve a storyboard, generate fake keyframes, or mutate storyboard.json.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DATA_RE = re.compile(r'(<script id="workbench-data" type="application/json">).*?(</script>)', re.S)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def stable(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def require_approval(project):
    from approval import require_semantic
    return require_semantic(project)


def load_sidecar(project, storyboard_sha):
    path = project / 'keyframes.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if isinstance(data, dict) and data.get('storyboardSha256') and data['storyboardSha256'] != storyboard_sha:
        raise ValueError('keyframes.json 对应旧文案；请按当前已批准分镜重新生成关键帧。')
    rows = data.get('shots', data) if isinstance(data, dict) else data
    if isinstance(rows, list):
        result = {}
        for row in rows:
            key = row.get('shotId') or row.get('id')
            if not key or key in result:
                raise ValueError('keyframes.json 镜头 ID 缺失或重复。')
            result[key] = row
        return result
    if isinstance(rows, dict):
        return {key: value if isinstance(value, dict) else {'keyframes': value} for key, value in rows.items() if key not in ('storyboardSha256', 'schemaVersion')}
    raise ValueError('keyframes.json 必须为 shots 列表或镜头 ID 映射。')


def media(project, path, required=False):
    if not path:
        if required:
            raise ValueError('关键帧缺少 path。')
        return None
    local = Path(path)
    local = local if local.is_absolute() else project / local
    local = local.resolve()
    if not local.is_file():
        if required:
            raise ValueError(f'素材不存在：{local}')
        return None
    try:
        relative = local.relative_to(project)
    except ValueError:
        raise ValueError(f'素材须在本期目录内；请先复制入本期 assets/：{local}')
    hasher = hashlib.sha256()
    with local.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            hasher.update(block)
    sha = hasher.hexdigest()
    cache = project / 'review/assets' / (sha + local.suffix.lower())
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        shutil.copyfile(local, cache)
    return {'path': str(relative), 'sha256': sha, 'url': 'assets/' + quote(cache.name)}


def finite_number(value, label):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{label} 必须为数字。')
    if not math.isfinite(number):
        raise ValueError(f'{label} 不能为无穷或 NaN。')
    return number


def build(project, stage):
    project = Path(project).expanduser().resolve()
    raw = (project / 'storyboard.json').read_bytes()
    source_sha = digest(raw)
    source = json.loads(raw)
    if not source.get('projectId') or not source.get('title') or not source.get('version'):
        raise ValueError('storyboard.json 需要 projectId、title、version。')
    shots = source.get('shots')
    if not isinstance(shots, list) or not shots:
        raise ValueError('storyboard.json 需要非空 shots。')
    if stage == 'keyframes':
        require_approval(project)
    sidecar = load_sidecar(project, source_sha) if stage == 'keyframes' else {}
    ids = [s.get('id') for s in shots]
    if any(not isinstance(x, str) or not re.fullmatch(r'[\w.-]+', x) for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('镜头 id 须唯一，仅使用文字、数字、下划线、点或短横线。')
    fps = int(source.get('fps', 30))
    if not 1 <= fps <= 120:
        raise ValueError('fps 必须在 1–120。')
    scenes, metadata = [], []
    cursor = 0.0
    for number, shot in enumerate(shots, 1):
        sid = shot['id']
        frame_row = sidecar.get(sid, {})
        timing = frame_row if stage == 'keyframes' else shot
        start = finite_number(timing.get('start', shot.get('start', cursor)), f'{sid}.start')
        duration = finite_number(shot.get('estimatedDuration', 4), f'{sid}.estimatedDuration')
        end = finite_number(timing.get('end', shot.get('end', start + duration)), f'{sid}.end')
        if start < 0 or end <= start or start < cursor - 0.001:
            raise ValueError(f'{sid} 时间区间无效或与前镜头重叠。')
        cursor = end
        visual = shot.get('visual') or {}
        ip = shot.get('ip') or {}
        visual_assets = []
        for item in visual.get('assets', []):
            visual_assets.append({**item, 'media': media(project, item.get('path'))})
        frames = []
        rows = frame_row.get('keyframes', frame_row.get('frames', shot.get('keyframes', [])))
        if stage == 'keyframes':
            if not rows:
                raise ValueError(f'{sid} 没有真实关键帧，不能构建关键帧审查页。')
            for index, frame in enumerate(rows, 1):
                ref = media(project, frame.get('path'), True)
                if Path(ref['path']).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
                    raise ValueError(f'{sid} 关键帧须为实际渲染的 PNG/JPEG/WebP。')
                time = finite_number(frame.get('time', start), f'{sid}.keyframes.time')
                if not start - 0.001 <= time < end + 0.001:
                    raise ValueError(f'{sid} 关键帧全局时间 {time} 不在镜头范围 {start}—{end}。')
                frames.append({'id': f'{sid}-{index:02d}-{ref["sha256"][:8]}', 'localFrame': round((time-start)*fps), 'globalFrame': round(time*fps), 'timeSeconds': time, 'image': ref, 'thumbnail': ref, 'label': frame.get('label', '实际渲染关键帧')})
            frames.sort(key=lambda f: f['timeSeconds'])
        semantic = {'visual': visual, 'ip': ip, 'assets': visual_assets, 'screenText': shot.get('screenText', ''), 'reviewNotes': (shot.get('review') or {}).get('notes', '')}
        semantic_identity = stable({'projectId': source['projectId'], 'version': source['version'], 'shot': {k:v for k,v in shot.items() if k not in ('keyframes', 'review')}})
        frame_identity = stable({'semantic': semantic_identity, 'frames': [(f['timeSeconds'], f['image']['sha256']) for f in frames]})
        items = {}
        for mode, scope in [('suggestion', 'direction'), ('keyframes', 'static-scene-frame-set'), ('video', 'video-review')]:
            identity = stable({'mode': mode, 'artifact': semantic_identity if mode == 'suggestion' else frame_identity})
            item = {'rowId': 'scene-review-' + identity[:20], 'episodeKey': source['projectId'], 'stableId': sid, 'view': {'suggestion':'segment-direction','keyframes':'segment-frames','video':'segment-video'}[mode], 'itemId': 'scene', 'identity': identity, 'approvalScope': scope, 'artifact': {'available': mode == 'suggestion' or bool(frames), 'kind': scope, 'frameCount': len(frames), 'frameSetSha256': frame_identity if frames else None}, 'context': {'narration': shot.get('narration',''), 'startSeconds': start, 'endSeconds': end, 'timelineFps': fps}}
            items[mode] = item
            metadata.append(item)
        scenes.append({'stableId': sid, 'number': number, 'title': shot.get('title') or shot.get('purpose') or sid, 'narration': shot.get('narration',''), 'startSeconds': start, 'endSeconds': end, 'startFrame': round(start*fps), 'durationInFrames': round((end-start)*fps), 'frames': frames, 'candidates': [], 'videos': [], 'sourceSceneIds': [sid], 'plan': {'enter':'','change':'','read':'','exit':'','handoff':''}, 'component': visual.get('type', ''), 'reason': shot.get('purpose',''), 'replacement': visual.get('focus',''), 'reviewItems': items, 'semantic': semantic})
    review = project / 'review'
    review.mkdir(exist_ok=True)
    old = review / 'index.html'
    archive = None
    if old.is_file():
        before = old.read_bytes()
        archive = 'history-' + digest(before)[:16] + '.html'
        (review / archive).write_bytes(before)
    media_file = project / 'review-media.json'
    media_options = json.loads(media_file.read_text()) if media_file.exists() else {}
    audio_path = media_options.get('audio', source.get('audio'))
    if not audio_path and (project/'audio/mix.wav').is_file():
        audio_path = 'audio/mix.wav'
    master_path = media_options.get('master', media_options.get('video'))
    if not master_path and (project/'out/final.mp4').is_file():
        master_path = 'out/final.mp4'
    if isinstance(master_path, dict):
        master_path = master_path.get('path')
    master = media(project, master_path) if stage == 'keyframes' else None
    if isinstance(audio_path, dict):
        audio_path = audio_path.get('path')
    data = {'schemaVersion': 1, 'episodeKey': source['projectId'], 'storageKey': 'dudu-talkvideo-review:' + source['projectId'], 'title': source['title'], 'revision': source['version'], 'fps': fps, 'durationSeconds': cursor, 'audio': media(project, audio_path), 'master': master, 'scenes': scenes, 'metadata': metadata, 'historyRecords': [], 'legacyPage': {'url': archive} if archive else None, 'initialView': 'suggestion' if stage == 'semantic' else 'keyframes', 'availableModes': ['suggestion'] if stage == 'semantic' else ['suggestion','keyframes'] + (['video'] if master else []), 'stage': stage, 'timingKind': 'estimated' if stage == 'semantic' else 'rendered', 'storyboardSha256': source_sha, 'frameEditor': None}
    if master:
        for scene in scenes:
            video = scene['reviewItems']['video']
            video['identity'] = stable({'keyframes': video['identity'], 'videoSha256': master['sha256']})
            video['rowId'] = 'scene-review-' + video['identity'][:20]
            video['artifact'].update({'available': True, 'sourceVideoSha256': master['sha256']})
    template = (ROOT / 'workbench/template.html').read_text()
    encoded = json.dumps(data, ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    if template.count('__WORKBENCH_DATA__') != 1:
        raise ValueError('工作台模板数据标记异常。')
    result = template.replace('__WORKBENCH_DATA__', encoded)
    result = result.replace('<title>DuDu-talkvideo · 分镜共创工作台</title>', '<title>' + html.escape(source['title']) + ' · DuDu-talkvideo</title>')
    old.write_text(result)
    (review / 'build.json').write_text(json.dumps({'stage': stage, 'projectId': source['projectId'], 'version': source['version'], 'storyboardSha256': source_sha, 'templateSha256': digest(template.encode()), 'htmlSha256': digest(result.encode()), 'shots': len(scenes), 'keyframes': sum(len(s['frames']) for s in scenes), 'previousVersion': archive, 'workflowApprovedByPage': False}, ensure_ascii=False, indent=2))
    return old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path)
    parser.add_argument('--stage', choices=['semantic','keyframes'], required=True)
    args = parser.parse_args()
    try:
        print(build(args.episode, args.stage))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        parser.exit(2, f'工作台生成失败：{error}\n')


if __name__ == '__main__':
    main()
