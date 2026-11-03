"""Offline checks of presenter gates and disabled default music/SFX."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import approval
import build_review
import presenter
import sound_design
import workflow




class WorkflowChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dudu-intake-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / 'input').mkdir()
        (self.project / 'input/script.txt').write_text('测试内容。')
        self.board = {'projectId': 'test-presenter', 'title': 'Test', 'version': 1,
                      'shots': [{'id': 's01', 'narration': '测试内容。', 'purpose': '解释结果',
                                 'visual': {'type': 'note', 'description': '真实结果'},
                                 'ip': {'mode': 'hidden'}, 'render': {'type': 'note'},
                                 'cameraPlan': {'subject': '本人', 'framing': '中景', 'movement': '静止', 'reason': '让观众听清'}}]}
        self.save_board()

    def save_board(self):
        workflow.save(self.project / 'storyboard.json', self.board)

    def choose(self, mode='real'):
        with contextlib.redirect_stdout(io.StringIO()):
            workflow.presenter(argparse.Namespace(project=str(self.project), mode=mode,
                                                    quote='本期用真人', evidence='synthetic-test-only'))
        self.board = workflow.read(self.project / 'storyboard.json')

    def test_new_requires_presenter_choice_before_semantic(self):
        source = self.project / 'source.txt'
        source.write_text('新一期文案')
        target = self.project / 'new'
        with patch('runtime_support.prepare_episode'), contextlib.redirect_stdout(io.StringIO()):
            workflow.new(argparse.Namespace(script=str(source), title='new', out=str(target)))
        self.assertEqual(workflow.read(target / 'presenter-request.json')['mode'], 'pending')
        config = workflow.read(target / 'audio-request.json')['soundtrack']
        self.assertFalse(config['music'])
        self.assertFalse(config['sfx'])
        self.assertEqual(config['cuePolicy'], 'none')
        with self.assertRaisesRegex(ValueError, '先向用户确认'):
            workflow.validate_board(target)

    def test_choice_and_camera_are_required_for_new_board(self):
        self.board['presenterMode'] = 'pending'
        self.save_board()
        with self.assertRaisesRegex(ValueError, '缺少 presenter-request'):
            workflow.validate_board(self.project)
        self.choose()
        workflow.validate_board(self.project)
        del self.board['shots'][0]['cameraPlan']
        self.save_board()
        with self.assertRaisesRegex(ValueError, 'cameraPlan'):
            workflow.validate_board(self.project)

    def test_real_rejects_ip_and_ip_mode_allows_it(self):
        self.choose()
        self.board['shots'][0]['ip']['mode'] = 'corner'
        self.save_board()
        with self.assertRaisesRegex(ValueError, '隐藏 IP'):
            workflow.validate_board(self.project)
        self.choose('ip')
        workflow.validate_board(self.project)

    def test_no_choice_change_after_approval_and_no_postapproval_mismatch(self):
        self.choose()
        workflow.save(self.project / 'approvals/semantic.json', {
            'status': 'approved', 'approvedBy': 'user', 'userStatement': 'test only',
            'storyboardSha256': approval.digest(self.project / 'storyboard.json')})
        approval.require_semantic(self.project)
        with self.assertRaisesRegex(ValueError, '已有语义审批'):
            self.choose('ip')
        choice = workflow.read(self.project / 'presenter-request.json')
        choice['mode'] = 'ip'
        workflow.save(self.project / 'presenter-request.json', choice)
        with self.assertRaisesRegex(ValueError, '不一致'):
            approval.require_semantic(self.project)

    def test_legacy_board_compatible_and_review_includes_plans(self):
        workflow.validate_board(self.project)
        self.choose()
        self.board['shots'][0]['soundPlan'] = '保持安静'
        self.save_board()
        before = (self.project / 'storyboard.json').read_bytes()
        output = build_review.build(self.project, 'semantic')
        document = output.read_text()
        self.assertIn('真人出镜', document)
        self.assertIn('保持安静', document)
        self.assertIn('cameraPlan', document)
        self.assertEqual(before, (self.project / 'storyboard.json').read_bytes())







    def test_no_default_music_or_automatic_cues(self):
        board = {'shots': [{'id': 's01', 'narration': 'test', 'render': {'type': 'note'}}]}
        timing = {'duration': 2, 'shots': [{'id': 's01', 'start': 0, 'end': 2, 'narrationStart': 0}]}
        result = sound_design.resolve({}, {}, board, timing, None, lambda text: (text, []))
        self.assertFalse(result['resolved']['music'])
        self.assertFalse(result['resolved']['sfx'])
        self.assertEqual(result['cues'], [])

    def test_default_audio_stems_are_silent(self):
        try:
            from audio_pipeline import soundtrack
        except ModuleNotFoundError as error:
            if error.name == 'numpy':
                self.skipTest('Run with the configured DuDu Python for audio checks')
            raise
        music, effects, cues = soundtrack(1, 48000, {'audio': {'music': False}, 'cues': []})
        self.assertFalse(music.any())
        self.assertFalse(effects.any())
        self.assertEqual(cues, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
