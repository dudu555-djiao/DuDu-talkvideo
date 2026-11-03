"""Real local HTTP/filesystem checks; all comments and attachments are synthetic."""
import base64
import copy
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from serve_review import create_server


class ProjectFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dudu-feedback-api-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / 'review').mkdir()
        (self.project / 'review/index.html').write_text('<script id="workbench-data" type="application/json">{"episodeKey":"qa-feedback"}</script>')
        self.server = create_server(self.project, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.token = self.call('GET')[1]['writeToken']

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def call(self, method, path='/api/workbench/feedback', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        outgoing = {'Content-Type': 'application/json', 'X-Workbench-Token': getattr(self, 'token', '')}
        outgoing.update(headers or {})
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=outgoing)
        response = connection.getresponse(); raw = response.read(); status = response.status
        connection.close()
        return status, json.loads(raw) if path.startswith('/api/') else raw

    def payload(self):
        item = {'stableId': 'S01', 'view': 'segment-frames', 'itemId': 'scene', 'identity': 'qa-v1'}
        key = json.dumps(list(item.values()), separators=(',', ':'))
        return {'projectId': 'qa-feedback', 'baseRevision': 0,
                'context': {'episodeKey': 'qa-feedback', 'metadata': [item], 'stage': 'keyframes'},
                'store': {'schemaVersion': 5, 'records': {key: {**item, 'note': '意见原文', 'content': [{'type': 'text', 'text': '意见原文'}]}},
                          'legacy': {'old': {'note': '旧版意见'}},
                          'workbench': {'deleted': {}, 'journal': [{'id': 'edit-1', 'before': None, 'after': {'note': '意见原文'}}]}},
                'assets': []}

    def upload(self, raw=b'original file bytes', name='原文件.txt'):
        value = {'sha256': hashlib.sha256(raw).hexdigest(), 'name': name, 'mimeType': 'text/plain',
                 'dataUrl': 'data:text/plain;base64,' + base64.b64encode(raw).decode()}
        status, ref = self.call('POST', '/api/workbench/feedback/assets', value)
        self.assertEqual(status, 200, ref)
        self.assertEqual((self.project / ref['path']).read_bytes(), raw)
        return ref

    def test_snapshot_preserves_comments_history_and_no_approval(self):
        payload = self.payload()
        status, result = self.call('POST', body=payload)
        self.assertEqual(status, 200, result)
        snapshot = json.loads((self.project / 'feedback/latest.json').read_text())
        self.assertEqual(snapshot['store'], payload['store'])
        self.assertEqual(snapshot['records'][0]['note'], '意见原文')
        self.assertTrue(snapshot['records'][0]['current'])
        self.assertFalse(snapshot['workflowApproved'])
        self.assertTrue((self.project / 'feedback/revisions/00000001.json').is_file())
        self.assertFalse((self.project / 'approvals').exists())

    def test_original_attachment_and_folder_paths_are_readable(self):
        ref = self.upload()
        payload = self.payload()
        payload['assets'] = [{'id': 'a', 'kind': 'file', 'name': '原文件.txt', 'file': ref},
                             {'id': 'folder', 'kind': 'folder', 'name': '资料', 'directories': ['资料', '资料/空目录'],
                              'files': [{'name': 'a.txt', 'relativePath': '资料/子目录/a.txt', 'file': ref}]}]
        record = next(iter(payload['store']['records'].values()))
        record['content'] += [{'type': 'file', 'id': 'a'}, {'type': 'folder', 'id': 'folder'}]
        self.assertEqual(self.call('POST', body=payload)[0], 200)
        saved = self.call('GET')[1]['snapshot']
        self.assertEqual(saved['records'][0]['content'][1]['path'], ref['path'])
        self.assertEqual(saved['records'][0]['content'][2]['files'][0]['relativePath'], '资料/子目录/a.txt')
        self.assertIn('资料/空目录', saved['assets'][1]['directories'])

    def test_stale_browser_saved_as_conflict_without_overwrite(self):
        payload = self.payload()
        self.call('POST', body=payload)
        before = (self.project / 'feedback/latest.json').read_bytes()
        payload['store']['legacy']['old']['note'] = '另一个浏览器的意见'
        status, result = self.call('POST', body=payload)
        self.assertEqual(status, 409)
        self.assertEqual((self.project / 'feedback/latest.json').read_bytes(), before)
        conflict = json.loads((self.project / result['conflictPath']).read_text())
        self.assertEqual(conflict['incoming']['store'], payload['store'])

    def test_undo_and_revision_history_preserved(self):
        payload = self.payload()
        self.call('POST', body=payload)
        payload['baseRevision'] = 1
        payload['store']['workbench']['journal'][0]['undoneAt'] = 'test-time'
        payload['store']['records'] = {}
        self.assertEqual(self.call('POST', body=payload)[0], 200)
        self.assertEqual(self.call('GET')[1]['snapshot']['store'], payload['store'])
        self.assertEqual(len(list((self.project / 'feedback/revisions').glob('*.json'))), 2)

    def test_reject_cross_site_missing_token_and_other_project(self):
        payload = self.payload()
        for headers in ({'X-Workbench-Token': ''}, {'Origin': 'https://unrelated.example'}, {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.call('POST', body=payload, headers=headers)[0], 403)
        payload['projectId'] = 'other'
        self.assertEqual(self.call('POST', body=payload)[0], 400)
        self.assertFalse((self.project / 'feedback/latest.json').exists())

    def test_reject_missing_tampered_or_outside_attachment(self):
        ref = self.upload()
        for bad in ({**ref, 'path': '../outside.txt'}, {**ref, 'bytes': 99}, {**ref, 'sha256': '0' * 64}):
            payload = self.payload(); payload['assets'] = [{'id': 'a', 'kind': 'file', 'file': bad}]
            self.assertEqual(self.call('POST', body=payload)[0], 400)
        (self.project / ref['path']).write_bytes(b'tampered')
        payload = self.payload(); payload['assets'] = [{'id': 'a', 'kind': 'file', 'file': ref}]
        self.assertEqual(self.call('POST', body=payload)[0], 400)
        self.assertFalse((self.project / 'feedback/latest.json').exists())

    def test_upload_checks_original_hash_and_cannot_escape(self):
        self.upload(name='../../cannot-escape.txt')
        self.assertFalse((self.project / 'cannot-escape.txt').exists())
        status, _ = self.call('POST', '/api/workbench/feedback/assets', {'sha256': '0' * 64, 'dataUrl': 'data:;base64,eA=='})
        self.assertEqual(status, 400)

    def test_range_serving_unchanged_and_snapshot_survives_restart(self):
        ref = self.upload(b'0123456789')
        status, raw = self.call('GET', '/' + quote(ref['path']), headers={'Range': 'bytes=2-4'})
        self.assertEqual((status, raw), (206, b'234'))
        self.call('POST', body=self.payload())
        from feedback_store import FeedbackStore
        self.assertEqual(FeedbackStore(self.project).load()['revision'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
