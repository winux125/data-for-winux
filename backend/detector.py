"""Load the selected, integrity-checked detector through its public Python API."""
import importlib.util
import json
from pathlib import Path

from .settings import ROOT


def detector_config(root=ROOT):
    root = Path(root).resolve()
    config = json.loads((root / 'config/detector.json').read_text(encoding='utf-8'))
    fields = {'schema_version', 'package_dir', 'model_id', 'device', 'threads'}
    if set(config) != fields or config['schema_version'] != 1:
        raise ValueError('Invalid detector configuration')
    package = (root / config['package_dir']).resolve()
    if not package.is_relative_to(root) or not (package / 'runtime.py').is_file():
        raise ValueError('Detector package must exist inside the service root')
    if config['device'] not in ('cuda', 'cpu', 'auto'):
        raise ValueError('Invalid detector device')
    if type(config['threads']) is not int or config['threads'] < 1:
        raise ValueError('Invalid detector thread count')
    return config, package


def load_detector(root=ROOT):
    config, package = detector_config(root)
    # Avoid the ambiguous top-level `runtime` import used by the legacy package.
    module_spec = importlib.util.spec_from_file_location('forte_selected_detector', package / 'runtime.py')
    runtime = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runtime)
    # load_spec verifies every pinned source and weight before deserialization.
    spec = runtime.load_spec(package)
    if spec['model_id'] != config['model_id']:
        raise ValueError('Configured detector identity does not match its package')
    return runtime.JepaModel(package_dir=package, device=config['device'], threads=config['threads'])
