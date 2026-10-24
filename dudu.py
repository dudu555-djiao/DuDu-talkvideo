#!/usr/bin/env python3
"""Cross-platform entry point; prefer this project's isolated Python runtime."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
venv_python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
python = os.environ.get('DUDU_PYTHON') or (str(venv_python) if venv_python.is_file() else sys.executable)
environment = os.environ.copy()
environment['PYTHONUTF8'] = '1'
environment['PYTHONIOENCODING'] = 'utf-8'
raise SystemExit(subprocess.call([python, str(ROOT / 'scripts/workflow.py'), *sys.argv[1:]], env=environment))
