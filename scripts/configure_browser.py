"""Configure public browser origins without exposing the private jury key."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'secrets/service.env'
values = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))
values.update(FORTE_BROWSER_API_ORIGIN='https://154.54.100.194.sslip.io',
    FORTE_CORS_ORIGINS='https://forte26.vercel.app,https://154.54.100.194.sslip.io')
path.write_text(''.join(f'{k}={v}\n' for k,v in values.items()))
path.chmod(0o600)
print('Browser origins configured; private jury key retained')
