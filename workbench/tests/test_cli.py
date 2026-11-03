"""Small, offline workbench contract regression. Approvals are test fixtures only."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from build_review import build

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dudu-workbench-qa-')
        self.p = Path(self.temp.name)
        self.s = {'projectId':'qa-only','title':'QA','version':'qa-v1','shots':[{'id':'S01','narration':'test','purpose':'test','estimatedDuration':3,'visual':{'type':'evidence','assets':[]},'ip':{}}]}
        (self.p/'storyboard.json').write_text(json.dumps(self.s))
        self.sha=hashlib.sha256((self.p/'storyboard.json').read_bytes()).hexdigest()
    def tearDown(self):
        self.temp.cleanup()
    def approve(self):
        (self.p/'approvals').mkdir()
        (self.p/'approvals/semantic.json').write_text(json.dumps({'status':'approved','approvedBy':'user','userStatement':'QA synthetic only','storyboardSha256':self.sha}))
    def test_semantic_and_missing_approval(self):
        result=build(self.p,'semantic')
        self.assertIn('"stage": "semantic"',result.read_text())
        self.assertIn('"frames": []',result.read_text())
        with self.assertRaises(ValueError):build(self.p,'keyframes')
    def test_approval_drift_and_missing_frames(self):
        self.approve()
        with self.assertRaisesRegex(ValueError,'真实关键帧'):build(self.p,'keyframes')
        (self.p/'storyboard.json').write_text(json.dumps(self.s)+'\n')
        with self.assertRaisesRegex(ValueError,'失效'):build(self.p,'keyframes')
    def test_sidecar_and_immutable_cache(self):
        self.approve()
        b=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH7sAAAAASUVORK5CYII=')
        (self.p/'frame.png').write_bytes(b)
        (self.p/'keyframes.json').write_text(json.dumps({'storyboardSha256':self.sha,'shots':[{'shotId':'S01','start':0,'end':3,'keyframes':[{'path':'frame.png','time':1}]}]}))
        first=build(self.p,'keyframes').read_bytes()
        self.assertEqual(hashlib.sha256((self.p/'storyboard.json').read_bytes()).hexdigest(),self.sha)
        self.assertEqual(next((self.p/'review/assets').glob('*.png')).read_bytes(),b)
        build(self.p,'keyframes')
        self.assertIn(first,[p.read_bytes() for p in (self.p/'review').glob('history-*.html')])

if __name__=='__main__':unittest.main()
