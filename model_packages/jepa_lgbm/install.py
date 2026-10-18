#!/usr/bin/env python3
"""Create an isolated CPU/CUDA environment for this extracted ZIP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def environment_python():
    return ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def choose_build(requested):
    if requested != 'auto':
        if requested == 'cuda' and platform.system() == 'Darwin':
            raise RuntimeError('CUDA is unavailable on macOS. Choose --device cpu.')
        return requested
    if platform.system() != 'Darwin':
        try:
            r = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return 'cuda'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return 'cpu'


def verify_files():
    spec = json.loads((ROOT / 'model.json').read_text(encoding='utf-8'))
    for name, expected in spec['sha256'].items():
        f = (ROOT / name).resolve()
        if not f.is_relative_to(ROOT) or not f.is_file():
            raise RuntimeError('Missing package file: ' + name)
        h = hashlib.sha256()
        with f.open('rb') as stream:
            for block in iter(lambda: stream.read(8*1024*1024), b''):
                h.update(block)
        if h.hexdigest() != expected:
            raise RuntimeError('Package checksum mismatch: ' + name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    args = p.parse_args()
    try:
        if not (3, 10) <= sys.version_info[:2] <= (3, 13) or struct.calcsize('P') != 8:
            raise RuntimeError('Install 64-bit Python 3.10–3.13 (recommended: 3.11), then rerun install.py.')
        verify_files()
        build = choose_build(args.device)
        py = environment_python()
        if not py.exists():
            try:
                venv.EnvBuilder(with_pip=False).create(ROOT / '.venv')
            except Exception as exc:
                raise RuntimeError('Could not create .venv. On Ubuntu install python3-venv; '
                                   'on other systems install Python with pip/venv. ' + str(exc)) from exc
        available = subprocess.run([str(py), '-m', 'pip', '--version'], capture_output=True).returncode == 0
        if not available:
            subprocess.run([str(py), str(ROOT/'tools/get-pip.py'), '--no-setuptools', '--no-wheel'], check=True)
        subprocess.run([str(py), '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)
        command = [str(py), '-m', 'pip', 'install', 'torch==2.9.1', 'torchvision==0.24.1']
        if platform.system() != 'Darwin':
            command += ['--index-url', 'https://download.pytorch.org/whl/' + ('cu126' if build == 'cuda' else 'cpu')]
        # Switching installation modes must replace an existing wheel of the other build.
        state_path = ROOT / '.install-state.json'
        previous = json.loads(state_path.read_text()) if state_path.exists() else {}
        if previous.get('build') != build:
            command += ['--force-reinstall']
        subprocess.run(command, check=True)
        subprocess.run([str(py), '-m', 'pip', 'install', '--only-binary=:all:', '-r', str(ROOT/'requirements.txt')], check=True)
        subprocess.run([str(py), str(ROOT/'inference.py'), '--check', '--device', 'auto' if args.device == 'auto' else build], check=True)
        state_path.write_text(json.dumps({'build':build,'python':str(py)},indent=2)+'\n')
        print('\nReady. Run: python run.py --video "video.mov" --out result.json')
        return 0
    except Exception as exc:
        print('Installation failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
