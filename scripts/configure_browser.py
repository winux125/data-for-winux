"""Configure explicitly selected browser origins, preserving the existing API key."""
import argparse
from pathlib import Path
from urllib.parse import urlparse

def origin(value):
    url=urlparse(value)
    if url.scheme not in ('https','http') or not url.netloc or url.path not in ('','/') or url.username or url.password or url.query or url.fragment:
        raise argparse.ArgumentTypeError('Expected an HTTP(S) origin without path or credentials')
    return value.rstrip('/')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-origin',required=True,type=origin)
    parser.add_argument('--site-origin',action='append',default=[],type=origin)
    args=parser.parse_args()
    path=Path(__file__).resolve().parents[1]/'secrets/service.env'
    lines=path.read_text().splitlines()
    updates={'FORTE_BROWSER_API_ORIGIN':args.api_origin,
             'FORTE_CORS_ORIGINS':','.join(dict.fromkeys([args.api_origin,*args.site_origin]))}
    kept=[line for line in lines if line.partition('=')[0] not in updates]
    path.write_text('\n'.join([*kept,*(f'{key}={value}' for key,value in updates.items())])+'\n')
    path.chmod(0o600)
    print('Browser origins configured; private jury key retained')
