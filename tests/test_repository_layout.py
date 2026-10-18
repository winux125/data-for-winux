"""A source-only checkout must work without an old ZIP or generated overlay."""
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def test_clean_source_tree_can_load_verified_corpus_from_another_directory(tmp_path):
    # Isolated Python cannot accidentally reuse the workspace's other legal_rag.
    code=(f"import sys;sys.path.insert(0,{str(ROOT)!r});"
          "from pathlib import Path;import legal_rag;from legal_rag import shared;"
          f"assert Path(legal_rag.__file__).resolve().parent==Path({str(ROOT/'legal_rag')!r});"
          "rag=shared().warm();library=rag.source_library();"
          "assert len(rag.cards)==8;assert len(library.sources)==54;"
          "assert len(library.units)==5661;assert len(library.chunks)==10176")
    subprocess.run([sys.executable,'-I','-B','-c',code],cwd=tmp_path,check=True,capture_output=True)


def test_preflight_checks_the_same_canonical_package_without_weights():
    spec=importlib.util.spec_from_file_location('forte_runtime_preflight',ROOT/'scripts/verify_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    report=module.verify()
    assert report['rag_package']=='legal_rag'
    assert report['sources']==54 and report['cards']==8


def test_build_fingerprint_changes_when_rag_or_policy_changes(tmp_path):
    import json
    from backend.build import build_id
    for directory in ('backend','legal_rag/data','config','model_packages/jepa_lgbm'):
        (tmp_path/directory).mkdir(parents=True)
    (tmp_path/'config/detector.json').write_text(json.dumps({'package_dir':'model_packages/jepa_lgbm'}))
    (tmp_path/'model_packages/jepa_lgbm/model.json').write_text('{}')
    target=tmp_path/'legal_rag/review.py';target.write_text('original')
    original=build_id(tmp_path)
    target.write_text('changed')
    assert build_id(tmp_path)!=original
    before=build_id(tmp_path)
    (tmp_path/'config/analysis-policy.json').write_text('{"mode":"changed"}')
    assert build_id(tmp_path)!=before
    target.write_bytes(b'changed\r\n')
    windows=build_id(tmp_path)
    target.write_bytes(b'changed\n')
    assert build_id(tmp_path)==windows
