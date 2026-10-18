import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('forte_deployment_renderer',ROOT/'scripts/render_deployment.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)


def test_deployment_targets_the_requested_checkout_and_cache(tmp_path):
    paths=renderer.render(tmp_path,'/opt/forte','bankworker','example.test','/srv/model-cache')
    assert len(paths)==5
    worker=(tmp_path/'forte-worker.service').read_text()
    assert 'User=bankworker' in worker and 'WorkingDirectory=/opt/forte' in worker
    assert 'HF_HOME=/srv/model-cache' in worker and 'PrivateNetwork=true' in worker
    assert '/opt/forte/.venv/bin/python -m backend.worker' in worker
    assert '/opt/forte/data/deploy/Caddyfile' in (tmp_path/'caddy.service').read_text()
    assert (tmp_path/'Caddyfile').read_text().startswith('example.test {')
    assert all('@SERVICE_' not in p.read_text() for p in paths)


@pytest.mark.parametrize('root,user,host',[
    ('relative','worker','example.test'),('/opt/forte','worker','example.test { evil'),
    ('/opt/forte\nExecStart=bad','worker','example.test'),('/opt/forte','bad\nUser=root','example.test')])
def test_invalid_deployment_values_fail_before_writing(tmp_path,root,user,host):
    with pytest.raises(ValueError):renderer.render(tmp_path/'output',root,user,host)
    assert not (tmp_path/'output').exists()
