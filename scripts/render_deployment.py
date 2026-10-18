"""Render systemd and Caddy configuration for the actual checkout and owner."""
import argparse
from pathlib import Path, PurePosixPath
import re

ROOT=Path(__file__).resolve().parents[1]


def render(destination, service_root, user, host, hf_home=None):
    for value in (service_root, hf_home or service_root+'/models/hf-cache'):
        if not PurePosixPath(value).is_absolute() or re.search(r'[\s%"\\]',value):
            raise ValueError('Use an absolute Linux path without spaces or systemd specifiers')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*\$?',user):
        raise ValueError('Invalid service user')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',host):
        raise ValueError('Pass a DNS hostname or IPv4 address without scheme/port/path')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    replacements={'@SERVICE_ROOT@':service_root,'@SERVICE_USER@':user,
                  '@PUBLIC_HOST@':host,'@HF_HOME@':hf_home or service_root+'/models/hf-cache'}
    paths=[]
    for name in ('forte-api.service','forte-worker.service','forte-frontend.service','caddy.service','Caddyfile'):
        text=(ROOT/'deploy'/name).read_text(encoding='utf-8')
        for token,value in replacements.items():text=text.replace(token,value)
        if re.search(r'@[A-Z_]+@',text):raise ValueError('Unresolved deployment template')
        output=destination/name;output.write_text(text,encoding='utf-8',newline='\n');paths.append(output)
    return paths


if __name__=='__main__':
    import getpass
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=str(ROOT))
    parser.add_argument('--user',default=getpass.getuser())
    parser.add_argument('--host',required=True)
    parser.add_argument('--hf-home')
    parser.add_argument('--output',type=Path,default=ROOT/'data/deploy')
    args=parser.parse_args()
    render(args.output,args.root,args.user,args.host,args.hf_home)
    print('Rendered 4 service units and Caddyfile; no services changed.')
