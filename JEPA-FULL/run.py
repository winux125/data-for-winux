#!/usr/bin/env python3
"""Use the package's environment without manual activation. JSON stays on stdout."""
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
py = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if not py.is_file():
    print('Run installation first: python install.py --device auto', file=sys.stderr)
    raise SystemExit(1)
progress = '--check' not in sys.argv and '--help' not in sys.argv and '-h' not in sys.argv
if progress:
    print('Загрузка модели и обработка видео. На CPU это может занять несколько минут.', file=sys.stderr, flush=True)
process = subprocess.Popen([str(py), str(ROOT/'inference.py'), *sys.argv[1:]])
started = time.monotonic()
try:
    while True:
        try:
            raise SystemExit(process.wait(timeout=30))
        except subprocess.TimeoutExpired:
            if progress:
                print(f'Обработка продолжается: {time.monotonic()-started:.0f} с.', file=sys.stderr, flush=True)
except KeyboardInterrupt:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    raise SystemExit(130)
