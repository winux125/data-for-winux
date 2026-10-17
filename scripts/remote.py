"""Run a shell command on the selected existing Brev machine without nested shell quoting."""
import subprocess
import sys
import os
import base64
from pathlib import Path

if __name__ == '__main__':
    host = os.environ.get('FORTE_BREV_HOST', 'forte-vision-50')
    args = ['wsl', '-d', 'Ubuntu-24.04', '--exec', 'ssh', '-T', '-o', 'BatchMode=yes',
            '-o', 'ControlPath=none', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15',
            '-o', 'ServerAliveCountMax=3']
    if host == 'forte-jepa-rag':
        args += ['-F', '/dev/null', '-i', '/home/winux/.brev/ssh-certs/ppdzcg25r',
                 '-p', '25219']
        host = 'shadeform@global.prd.ga.run.brev.nvidia.com'
    if sys.argv[1] == '--python':
        encoded = base64.b64encode(Path(sys.argv[2]).read_bytes()).decode('ascii')
        command = "cd /home/shadeform/forte-service && .venv/bin/python -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""
    else:
        command = sys.argv[1]
    result = subprocess.run(args + [host, command])
    raise SystemExit(result.returncode)
