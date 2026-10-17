"""WSL only: refresh the migration source cert, restore primary org immediately."""
import json
from pathlib import Path
import subprocess

directory = Path.home() / '.brev'
credentials = directory / 'credentials.json'
original = credentials.read_bytes()
try:
    credentials.write_bytes((directory / 'credentials.forte-secondary.json').read_bytes())
    subprocess.run([str(Path.home()/'.local/bin/brev'), 'mint-cert',
        '--env', 'ppdzcg25r', '--port', 'nport-3KpOFP6i1bVqINGP1dfgtKnpK9q',
        '--linux-user', 'shadeform', '--out-key', str(directory/'ssh-certs/ppdzcg25r')], check=True)
finally:
    credentials.write_bytes(original)
