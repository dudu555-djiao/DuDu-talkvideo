#!/usr/bin/env python3
"""Offline smoke tests for partial-render planning and AAC variant muxing.

Run: python tests/media_helpers_smoke.py
Requires Python 3.10+ and system ffmpeg/ffprobe (FFmpeg with libx264 and AAC).
All fixtures are generated in a temporary directory and removed after the run.
No project episodes, network, credentials, TTS services or paid APIs are used.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / 'scripts' / 'plan_partial_render.py'
MUX = ROOT / 'scripts' / 'mux_audio_variants.py'
FFMPEG = shutil.which('ffmpeg')
FFPROBE = shutil.which('ffprobe')


def invoke(arguments, expected_success=True):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=90)
    if (result.returncode == 0) != expected_success:
        raise AssertionError(
            f'Unexpected exit code {result.returncode}: {arguments!r}\n'
            f'stdout: {result.stdout[-3000:]}\nstderr: {result.stderr[-3000:]}')
    return result


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MediaHelpersSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='dudu-media-helpers-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.fixtures = Path(cls.temporary.name)
        if not PLANNER.is_file() or not MUX.is_file():
            raise RuntimeError('Run this test from the complete DuDu-talkvideo repository')
        cls.picture = cls.fixtures / 'picture.mp4'
        invoke([FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                'testsrc2=size=320x180:rate=30:duration=6', '-c:v', 'libx264',
                '-threads', '1', '-preset', 'fast', '-g', '30', '-keyint_min', '30',
                '-sc_threshold', '0', '-bf', '2', '-pix_fmt', 'yuv420p', str(cls.picture)])
        for label, frequency, duration in [('voice', 440, 6), ('sfx', 660, 6), ('short', 330, 5)]:
            invoke([FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    f'sine=frequency={frequency}:sample_rate=48000:duration={duration}',
                    '-c:a', 'aac', '-b:a', '128k', str(cls.fixtures / f'{label}.m4a')])
        invoke([FFMPEG, '-v', 'error', '-y', '-i', str(cls.fixtures / 'voice.m4a'),
                str(cls.fixtures / 'voice.wav')])
        invoke([FFMPEG, '-v', 'error', '-y', '-i', str(cls.picture), '-vf',
                r'select=not(eq(mod(n\,10)\,0))', '-fps_mode', 'vfr',
                '-c:v', 'libx264', '-threads', '1', str(cls.fixtures / 'vfr.mp4')])
        invoke([FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                'testsrc2=size=320x180:rate=30000/1001:duration=3',
                '-c:v', 'libx264', '-threads', '1', '-g', '30',
                str(cls.fixtures / 'fractional.mp4')])
        invoke([FFMPEG, '-v', 'error', '-y', '-i', str(cls.picture),
                '-vf', 'setpts=PTS+0.2/TB', '-fps_mode', 'passthrough',
                '-c:v', 'libx264', '-threads', '1', str(cls.fixtures / 'offset.mp4')])
        subtitle = cls.fixtures / 'captions.srt'
        subtitle.write_text('1\n00:00:00,000 --> 00:00:05,500\nSynthetic subtitle fixture\n', encoding='utf-8')
        invoke([FFMPEG, '-v', 'error', '-y', '-i', str(cls.picture),
                '-i', str(cls.fixtures / 'voice.m4a'), '-i', str(subtitle),
                '-map', '0:v:0', '-map', '1:a:0', '-map', '2:s:0',
                '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text',
                str(cls.fixtures / 'subtitled.mp4')])

    def setUp(self):
        self.work = self.fixtures / self._testMethodName
        self.work.mkdir()

    def plan_command(self, *arguments, base=None):
        return [sys.executable, str(PLANNER), str(base or self.picture),
                '--ffprobe', FFPROBE, *arguments]

    def plan(self, *arguments, base=None):
        return json.loads(invoke(self.plan_command(*arguments, base=base)).stdout)

    def manifest(self, rows=None):
        path = self.work / 'variants.json'
        rows = rows if rows is not None else [
            {'id': 'voice', 'audio': '../voice.m4a', 'output': 'out/voice.mp4'},
            {'id': 'sfx', 'audio': '../sfx.m4a', 'output': 'out/sfx.mp4'},
        ]
        path.write_text(json.dumps(rows), encoding='utf-8')
        return path

    def mux_command(self, manifest, *arguments):
        return [sys.executable, str(MUX), str(self.picture), str(manifest),
                '--ffmpeg', FFMPEG, '--ffprobe', FFPROBE, *arguments]

    def test_01_cli_help(self):
        for script in (PLANNER, MUX):
            result = invoke([sys.executable, str(script), '--help'])
            self.assertIn('usage:', result.stdout)

    def test_02_sort_expand_and_merge(self):
        plan = self.plan('--range', '1.6:1.7', '--range', '1.2:1.4', '--handle', '0.2')
        self.assertEqual(plan['candidateRenderRanges'], [[30, 60]])
        self.assertEqual((plan['renderFrames'], plan['copyCandidateFrames']), (30, 150))

    def test_03_half_open_pieces_cover_video(self):
        plan = self.plan('--range', '1.2:1.4', '--handle', '0.2')
        position = 0
        for piece in plan['pieces']:
            self.assertEqual(piece['startFrame'], position)
            self.assertGreater(piece['endFrame'], piece['startFrame'])
            self.assertEqual(piece['frames'], piece['endFrame'] - piece['startFrame'])
            position = piece['endFrame']
        self.assertEqual(position, 180)
        self.assertTrue(plan['planOnly'])
        self.assertFalse(plan['spliceSafetyVerified'])
        self.assertEqual(plan['baseSha256'], file_hash(self.picture))

    def test_04_default_two_second_context(self):
        plan = self.plan('--range', '2.7:2.8')
        self.assertEqual(plan['handleSeconds'], 2)
        self.assertEqual(plan['candidateRenderRanges'], [[0, 150]])

    def test_05_json_ranges_and_final_boundary(self):
        ranges = self.work / 'ranges.json'
        ranges.write_text(json.dumps({'ranges': [[5.8, 6.0]]}), encoding='utf-8')
        plan = self.plan('--ranges-json', str(ranges), '--handle', '0')
        self.assertEqual(plan['candidateRenderRanges'], [[150, 180]])

    def test_06_reject_invalid_ranges(self):
        for interval in ('-1:2', 'nan:2', '1:inf', '2:2', '3:2', '1:6.2'):
            with self.subTest(interval=interval):
                invoke(self.plan_command(f'--range={interval}'), expected_success=False)

    def test_07_reject_invalid_handles(self):
        for handle in ('-1', 'nan', 'inf'):
            with self.subTest(handle=handle):
                invoke(self.plan_command('--range', '1:2', '--handle', handle), expected_success=False)

    def test_08_malformed_json_types_have_clean_errors(self):
        ranges = self.work / 'ranges.json'
        for value in ([[None, 1]], [[True, 1]], {'ranges': None}, [], [[1]]):
            with self.subTest(value=value):
                ranges.write_text(json.dumps(value), encoding='utf-8')
                result = invoke(self.plan_command('--ranges-json', str(ranges)), expected_success=False)
                self.assertNotIn('Traceback', result.stderr)

    def test_09_reject_variable_frame_rate(self):
        invoke(self.plan_command('--range', '1:2', base=self.fixtures / 'vfr.mp4'), expected_success=False)

    def test_10_accept_fractional_constant_frame_rate(self):
        plan = self.plan('--range', '1.3:1.5', '--handle', '0', base=self.fixtures / 'fractional.mp4')
        self.assertEqual(plan['fps'], '30000/1001')
        self.assertEqual(plan['totalFrames'], 90)

    def test_11_reject_nonzero_video_start(self):
        invoke(self.plan_command('--range', '1:2', base=self.fixtures / 'offset.mp4'), expected_success=False)

    def test_12_plan_does_not_overwrite_existing_output(self):
        output = self.work / 'plan.json'
        command = self.plan_command('--range', '1:2', '--output', str(output))
        invoke(command)
        original_hash = file_hash(output)
        invoke(command, expected_success=False)
        self.assertEqual(file_hash(output), original_hash)

    def test_13_mux_preserves_video_audio_frames_and_duration(self):
        report_path = self.work / 'report.json'
        invoke(self.mux_command(self.manifest(), '--report', str(report_path)))
        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertTrue(report['passed'])
        self.assertEqual(report['frames'], 180)
        self.assertAlmostEqual(report['durationSeconds'], 6.0)
        self.assertEqual(report['pictureSha256'], file_hash(self.picture))
        self.assertEqual(len(report['variants']), 2)
        for row in report['variants']:
            self.assertTrue(all(row['checks'].values()), row)
            output = Path(row['output'])
            self.assertEqual(row['sha256'], file_hash(output))
            copied_video = invoke([FFMPEG, '-v', 'error', '-i', str(output), '-map', '0:v:0',
                                   '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-']).stdout.strip()
            copied_audio = invoke([FFMPEG, '-v', 'error', '-i', str(output), '-map', '0:a:0',
                                   '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-']).stdout.strip()
            self.assertEqual(copied_video, report['videoStreamHash'])
            self.assertEqual(copied_audio, row['audioStreamHash'])

    def test_14_mux_does_not_overwrite_existing_media(self):
        command = self.mux_command(self.manifest())
        first = json.loads(invoke(command).stdout)
        outputs = {Path(row['output']): row['sha256'] for row in first['variants']}
        invoke(command, expected_success=False)
        self.assertEqual({path: file_hash(path) for path in outputs}, outputs)

    def test_15_reject_audio_duration_mismatch_without_output(self):
        manifest = self.manifest([{'id': 'short', 'audio': '../short.m4a', 'output': 'out/short.mp4'}])
        invoke(self.mux_command(manifest), expected_success=False)
        self.assertFalse((self.work / 'out').exists())

    def test_16_reject_unsupported_audio_without_output(self):
        manifest = self.manifest([{'id': 'wav', 'audio': '../voice.wav', 'output': 'out/wav.mp4'}])
        invoke(self.mux_command(manifest), expected_success=False)
        self.assertFalse((self.work / 'out').exists())

    def test_17_reject_duplicate_ids_before_writing(self):
        manifest = self.manifest([
            {'id': 'same', 'audio': '../voice.m4a', 'output': 'out/a.mp4'},
            {'id': 'same', 'audio': '../sfx.m4a', 'output': 'out/b.mp4'},
        ])
        invoke(self.mux_command(manifest), expected_success=False)
        self.assertFalse((self.work / 'out').exists())

    def test_18_reject_picture_soft_subtitles_without_output(self):
        command = self.mux_command(self.manifest())
        command[2] = str(self.fixtures / 'subtitled.mp4')
        result = invoke(command, expected_success=False)
        self.assertIn('soft subtitles', result.stderr)
        self.assertIn('subtitle-preserving workflow', result.stderr)
        self.assertFalse((self.work / 'out').exists())

    def test_19_reject_audio_source_soft_subtitles_before_writing(self):
        manifest = self.manifest([
            {'id': 'first-valid', 'audio': '../voice.m4a', 'output': 'out/first.mp4'},
            {'id': 'subtitled', 'audio': '../subtitled.mp4', 'output': 'out/subtitled.mp4'},
        ])
        result = invoke(self.mux_command(manifest), expected_success=False)
        self.assertIn('soft subtitles', result.stderr)
        self.assertIn('subtitle-preserving workflow', result.stderr)
        self.assertFalse((self.work / 'out').exists())


if __name__ == '__main__':
    if sys.version_info < (3, 10):
        sys.exit('Python 3.10+ is required to run the media helper smoke tests.')
    if not FFMPEG or not FFPROBE:
        sys.exit('Missing ffmpeg or ffprobe. Install FFmpeg with libx264/AAC support and add both executables to PATH.')
    unittest.main(verbosity=2)
