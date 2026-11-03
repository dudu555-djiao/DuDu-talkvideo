#!/usr/bin/env python3
"""Isolated synthetic installation fixture; never grants production approval."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def call(*arguments, success=True):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/workflow.py'), *map(str, arguments)],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if (result.returncode == 0) != success:
        raise AssertionError('Unexpected result for ' + ' '.join(map(str, arguments)) + '\n' + result.stdout[-1000:] + result.stderr[-2000:])
    return result


def main():
    import numpy as np
    from playwright.sync_api import sync_playwright
    from runtime_support import launch, open_page
    from doctor import inspect
    assert inspect()['localReady'], 'Run bootstrap first'
    report = {'fixture': 'synthetic offline installation test; not a production episode',
              'networkTtsRequests': 0, 'paidRequests': 0}
    with tempfile.TemporaryDirectory(prefix='dudu-install-') as temporary:
        target = Path(temporary)
        episode = target / '中文 空格 fixture'
        script = target / 'script.txt'
        script.write_text('先看实际结果。\n再把重点讲清楚。', encoding='utf-8')
        call('new', '--script', script, '--title', '安装验证', '--out', episode)
        soundtrack = json.loads((episode / 'audio-request.json').read_text(encoding='utf-8'))['soundtrack']
        assert not soundtrack['music'] and not soundtrack['sfx'] and soundtrack['cuePolicy']=='none'
        report['defaultSoundtrackEnabled'] = False
        call('presenter', episode, '--mode', 'ip', '--quote', 'QA ONLY: generic mascot', '--evidence', 'synthetic installation fixture')
        board = json.loads((episode / 'storyboard.json').read_text(encoding='utf-8'))
        board['shots'] = [
            {'id': 'S01', 'narration': '先看实际结果。', 'purpose': '离线安装测试的纸条场景',
             'visual': {'type': 'note', 'description': '合成测试纸条，不代表真实教程结果', 'assets': []},
             'screenText': '安装测试', 'estimatedDuration': 1.5,
             'ip': {'mode': 'corner', 'emotion': 'explaining', 'emphasis': []},
             'render': {'type': 'note', 'title': '安装测试', 'text': '声音驱动说话'}},
            {'id': 'S02', 'narration': '再把重点讲清楚。', 'purpose': '测试词锚点强调和回位',
             'visual': {'type': 'chapter', 'description': '第二个合成测试场景', 'assets': []},
             'screenText': '把重点讲清楚', 'estimatedDuration': 1.5,
             'ip': {'mode': 'corner', 'emotion': 'explaining', 'emphasis': [{'anchor': '重点'}]},
             'render': {'type': 'chapter', 'title': '把重点讲清楚', 'number': '02'}}]
        for shot in board['shots']:
            shot['cameraPlan']={'subject':'generic mascot and test text','framing':'wide','movement':'restrained emphasis','reason':'synthetic runtime validation'}
        board_path = episode / 'storyboard.json'
        board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding='utf-8')
        semantic_sha = hashlib.sha256(board_path.read_bytes()).hexdigest()
        call('semantic', episode)
        assert (episode / 'review/index.html').is_file()
        for command in ('voice', 'audio', 'assemble', 'frames', 'review', 'render'):
            call(command, episode, success=False)
        report['approvalGate'] = 'six downstream commands blocked before approval'
        # This synthetic record exists only inside this disposable QA directory.
        call('approve', episode, '--quote', 'QA ONLY: synthetic fixture approval, not a human production decision',
             '--evidence', 'tests/installation_smoke.py disposable QA fixture')
        rate = 48000
        t = np.arange(rate * 3) / rate
        gate = ((t > .35) & (t < 1.1)) | ((t > 1.9) & (t < 2.65))
        signal = (np.sin(t * 2 * math.pi * 240) * .12 * gate * 32767).astype('<i2')
        fixture_audio = target / 'synthetic-tone-not-voice.wav'
        with wave.open(str(fixture_audio), 'wb') as output:
            output.setnchannels(2); output.setsampwidth(2); output.setframerate(rate)
            output.writeframes(np.column_stack((signal, signal)).tobytes())
        fixture_timing = target / 'synthetic-timing.json'
        fixture_timing.write_text(json.dumps({'text': script.read_text(encoding='utf-8'), 'words': [
            {'word': '先看实际结果。', 'startTime': .35, 'endTime': 1.1},
            {'word': '再把重点讲清楚。', 'startTime': 1.9, 'endTime': 2.65}]}, ensure_ascii=False), encoding='utf-8')
        subprocess.run([sys.executable, str(ROOT / 'scripts/audio_pipeline.py'), '--project', str(episode),
                        '--import-audio', str(fixture_audio), '--timing', str(fixture_timing)], check=True,
                       stdout=subprocess.DEVNULL)
        call('assemble', episode)
        episode_path = episode / 'episode.json'
        data = json.loads(episode_path.read_text(encoding='utf-8'))
        data.update(width=640, height=360)
        episode_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        call('frames', episode)
        call('review', episode)
        errors = []
        with sync_playwright() as pw:
            browser = launch(pw)
            page = open_page(browser, episode, data, errors)
            assert page.evaluate("document.fonts.check('600 42px DuDuBody')")
            assert page.evaluate('(t)=>window.render(t)', 0)['avatar']['mouth'] == 'closed'
            speaking = page.evaluate('(t)=>window.render(t)', .65)['avatar']
            assert speaking['active'] and speaking['mouth'] in ('small', 'wide')
            assert page.evaluate('(t)=>window.render(t)', 1.5)['avatar']['mouth'] == 'closed'
            emphasis = data['scenes'][1]['ip']['emphasis'][0]
            pop = page.evaluate('(t)=>window.render(t)', min(emphasis['end'], emphasis['start'] + .3))['avatar']
            assert pop['pop'] > .5 and pop['emphasisOffsetY'] < 0
            assert not errors
            browser.close()
        report['fontsMascotAndEmphasis'] = 'passed'
        voice_hash = hashlib.sha256((episode / 'audio/narration.wav').read_bytes()).hexdigest()
        call('render', episode)
        call('check', episode)
        assert hashlib.sha256(board_path.read_bytes()).hexdigest() == semantic_sha
        assert hashlib.sha256((episode / 'audio/narration.wav').read_bytes()).hexdigest() == voice_hash
        info = json.loads((episode / 'qa/final-checks.json').read_text(encoding='utf-8'))
        assert info['passed'] and int(info['frames']) == 90
        sound = json.loads((episode / 'audio/soundtrack.json').read_text(encoding='utf-8'))
        assert not sound['resolved']['music'] and not sound['resolved']['sfx']
        assert sound['cues']==[]
        report.update(actualKeyframes='passed', reviewHtml='passed', videoRender='passed',
                      completeDecode='passed', frames=90, duration=3, semanticSourceUnchanged=True,
                      narrationUnchanged=True, passed=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
