#!/usr/bin/env python3
"""Install the project venv, Chromium, private config template and local skill."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(arguments):
    subprocess.run([str(x) for x in arguments], check=True)


def install_skill(destination):
    source = ROOT / 'skills/dudu-talkvideo'
    destination = Path(destination).expanduser().absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() and destination.resolve() == source.resolve():
        return 'already-linked'
    if destination.exists() or destination.is_symlink():
        print('保留已有Skill，未覆盖：' + str(destination))
        return 'existing-preserved'
    try:
        destination.symlink_to(source, target_is_directory=True)
        return 'linked'
    except OSError:
        # Windows without symlink privileges: a small pointer skill locates the full checkout.
        destination.mkdir()
        content = (source / 'SKILL.md').read_text(encoding='utf-8')
        content = content.replace('<!-- INSTALLED_PROJECT_ROOT -->',
                                  '安装项目根目录：`' + ROOT.as_posix() + '`。先从此目录读取项目文件。')
        (destination / 'SKILL.md').write_text(content, encoding='utf-8')
        shutil.copytree(source / 'agents', destination / 'agents')
        shutil.copytree(source / 'references', destination / 'references')
        (destination / 'project-root.json').write_text(json.dumps({'projectRoot': str(ROOT)}, ensure_ascii=False), encoding='utf-8')
        return 'pointer-copy'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Create .venv, install requirements/Chromium, register Skill')
    parser.add_argument('--smoke-test', action='store_true', help='Run offline synthetic render test; no TTS requests')
    parser.add_argument('--skip-browser-install', action='store_true', help='Use an existing compatible Chromium runtime')
    parser.add_argument('--skill-dir', type=Path, help='Override the user-scope Skill destination')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error('需要 Python 3.10 或更高版本。先按 docs/INSTALL.md 安装系统依赖。')
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if args.install:
        environment = ROOT / '.venv'
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.exists():
            print('建立项目独立 Python 环境', flush=True)
            venv.EnvBuilder(with_pip=True).create(environment)
        run([python, '-m', 'pip', 'install', '-r', ROOT / 'requirements.txt'])
        if not args.skip_browser_install:
            run([python, '-m', 'playwright', 'install', 'chromium'])
        config = ROOT / '.env'
        if not config.exists():
            shutil.copyfile(ROOT / '.env.example', config)
            if os.name != 'nt':
                config.chmod(0o600)
        primary = args.skill_dir or Path.home() / '.agents/skills/dudu-talkvideo'
        registration = {str(primary): install_skill(primary)}
        if not args.skill_dir:
            compatibility = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'skills/dudu-talkvideo'
            if compatibility.absolute() != primary.expanduser().absolute():
                registration[str(compatibility)] = install_skill(compatibility)
        print(json.dumps({'skillRegistration': registration}, ensure_ascii=False))
        if all(status == 'existing-preserved' for status in registration.values()):
            raise SystemExit('所有安装位置已有其他版本，未替换。先审查已有版本，或用 --skill-dir 指定独立测试位置。')
        # Re-enter through the venv; installation does not depend on shell activation.
        run([python, ROOT / 'scripts/bootstrap.py', *(['--smoke-test'] if args.smoke_test else [])])
        return
    from doctor import inspect
    result = inspect()
    result['checkedAt'] = datetime.now().astimezone().isoformat()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['localReady']:
        print('缺少依赖：' + ', '.join(k for k, value in result['checks'].items() if not value))
        print('请让 Codex 按 docs/INSTALL.md 补齐，再运行此命令。Linux Chromium 系统库可能需要 playwright install-deps chromium。')
        raise SystemExit(1)
    if args.smoke_test:
        run([sys.executable, ROOT / 'tests/installation_smoke.py'])
        result['smokeTest'] = 'passed'
    (ROOT / 'installation-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('本地环境已就绪。自动配音配置状态：' + ('已填写，未验证远端权限' if result['ttsCredentialsConfigured'] else '待本人填写 .env；可先使用示例或导入成品录音'))


if __name__ == '__main__':
    main()
