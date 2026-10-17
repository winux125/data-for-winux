"""Compact frontend fixture-test failures; excludes noisy browser process logs."""
from pathlib import Path
import re
lines = Path('data/frontend-checks-final.log').read_text().splitlines()
collect = 0
for line in lines:
    if re.match(r'\s+\d+\) \[', line):
        print(line)
    if 'Error:' in line and '[err]' not in line:
        print(line)
    if 'Call log:' in line:
        collect = 11
    if collect:
        print(line)
        collect -= 1
