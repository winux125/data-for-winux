"""Detector selection must load the requested package, with no legacy fallback."""
import json
import importlib.util
from pathlib import Path

import pytest

from backend.detector import detector_config, load_detector


def package(tmp_path, model_id='JEPA-LGBM-FULL'):
    (tmp_path / 'config').mkdir()
    directory = tmp_path / 'model_packages/jepa_lgbm'
    directory.mkdir(parents=True)
    config = dict(schema_version=1, package_dir='model_packages/jepa_lgbm',
                  model_id='JEPA-LGBM-FULL', device='cuda', threads=8)
    (tmp_path / 'config/detector.json').write_text(json.dumps(config))
    (directory / 'runtime.py').write_text(
        'def load_spec(root):\n'
        f'    return {{"model_id": {model_id!r}}}\n'
        'class JepaModel:\n'
        '    def __init__(self, **kwargs): self.received = kwargs\n')
    return config, directory


def test_selected_public_api_receives_configured_root_device_and_threads(tmp_path):
    _, directory = package(tmp_path)
    model = load_detector(tmp_path)
    assert model.received == dict(package_dir=directory, device='cuda', threads=8)


def test_wrong_identity_does_not_fall_back_to_svm(tmp_path):
    package(tmp_path, 'JEPA-FULL')
    with pytest.raises(ValueError, match='identity'):
        load_detector(tmp_path)


@pytest.mark.parametrize('field,value', [('package_dir', '../../outside'), ('threads', True),
                                        ('threads', 0), ('device', 'invalid'), ('extra', 1)])
def test_invalid_configuration_is_rejected(tmp_path, field, value):
    config, _ = package(tmp_path)
    config[field] = value
    (tmp_path / 'config/detector.json').write_text(json.dumps(config))
    with pytest.raises(ValueError):
        detector_config(tmp_path)


def test_detector_verifier_detects_tampered_weights(tmp_path):
    import hashlib
    _, directory = package(tmp_path)
    weights = directory / 'weights'
    weights.mkdir()
    (weights / 'head.joblib').write_bytes(b'original')
    (directory / 'model.json').write_text(json.dumps(dict(model_id='JEPA-LGBM-FULL',
        sha256={'weights/head.joblib': hashlib.sha256(b'original').hexdigest()})))
    script = Path(__file__).resolve().parents[1] / 'scripts/install_detector.py'
    spec = importlib.util.spec_from_file_location('detector_installer_test', script)
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    assert installer.install(root=tmp_path)['verified_files'] == 1
    (weights / 'head.joblib').write_bytes(b'changed')
    with pytest.raises(ValueError, match='checksum'):
        installer.install(root=tmp_path)
