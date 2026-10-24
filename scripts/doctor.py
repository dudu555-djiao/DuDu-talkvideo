#!/usr/bin/env python3
"""Local readiness checks. No TTS requests and no credential values in output."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def credential_file():
    return Path(os.environ.get('DUDU_TALKVIDEO_TTS_ENV') or ROOT / '.env').expanduser()


def credential_presence():
    values = {key: os.environ.get(key, '') for key in (
        'VOLC_TTS_API_KEY', 'VOLC_TTS_APP_ID', 'VOLC_TTS_ACCESS_TOKEN')}
    source = credential_file()
    if source.is_file():
        for line in source.read_text(encoding='utf-8-sig').splitlines():
            match = re.match(r'^\s*(?:export\s+)?(VOLC_TTS_\w+)\s*=\s*(.*?)\s*$', line)
            if match and match[1] in values and not values[match[1]]:
                values[match[1]] = match[2].strip('"\'').split(' #', 1)[0].strip()
    populated = lambda value: bool(value and value.lower() not in {
        'your_api_key', 'your_key_here', 'replace_me', 'your_app_id', 'your_access_token'})
    return bool(populated(values['VOLC_TTS_API_KEY']) or (
        populated(values['VOLC_TTS_APP_ID']) and populated(values['VOLC_TTS_ACCESS_TOKEN'])))


def inspect(check_browser=True):
    from runtime_support import binary
    checks = {'python': sys.version_info >= (3, 10), 'numpy': False, 'playwright': False}
    versions = {'python': sys.version.split()[0]}
    for module in ('numpy', 'playwright'):
        checks[module] = importlib.util.find_spec(module) is not None
    for name in ('node', 'ffmpeg', 'ffprobe'):
        try:
            result = subprocess.run([binary(name), '--version' if name == 'node' else '-version'],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
            versions[name] = result.stdout.splitlines()[0] if result.stdout else 'unavailable'
            checks[name] = result.returncode == 0
            if name == 'node':
                checks[name] = checks[name] and int(result.stdout.strip().lstrip('v').split('.')[0]) >= 22
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired):
            checks[name] = False
    try:
        encoders = subprocess.run([binary('ffmpeg'), '-hide_banner', '-encoders'], capture_output=True, text=True, timeout=20)
        filters = subprocess.run([binary('ffmpeg'), '-hide_banner', '-filters'], capture_output=True, text=True, timeout=20)
        checks['h264Encoder'] = 'libx264' in encoders.stdout
        checks['loudnormFilter'] = 'loudnorm' in filters.stdout
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        checks['h264Encoder'] = checks['loudnormFilter'] = False
    checks['bundledFonts'] = all((ROOT / 'assets/fonts' / name).is_file() and (ROOT / 'assets/fonts' / name).stat().st_size > 1000
                                for name in ('ZCOOLQingKeHuangYou-Regular.ttf', 'NotoSansSC-400.woff2', 'NotoSansSC-700.woff2'))
    checks['avatar'] = (ROOT / 'assets/avatar/registration.json').is_file()
    checks['workbench'] = (ROOT / 'workbench/template.html').is_file()
    browser_error = None
    if check_browser:
        checks['chromium'] = False
        if checks['playwright']:
            try:
                from playwright.sync_api import sync_playwright
                from runtime_support import launch
                with sync_playwright() as pw:
                    browser = launch(pw)
                    browser.close()
                checks['chromium'] = True
            except Exception as error:
                browser_error = type(error).__name__
    return {'localReady': all(checks.values()), 'checks': checks, 'versions': versions,
            'ttsCredentialFilePresent': credential_file().is_file(),
            'ttsCredentialsConfigured': credential_presence(), 'remoteTtsTested': False,
            'browserError': browser_error,
            'note': 'localReady只代表本地制作环境。自动配音还需本人火山TTS账号、音色权限和额度；未发送付费请求。'}


if __name__ == '__main__':
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['localReady'] else 1)
