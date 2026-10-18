"""Offline preflight for the actual checkout; no inference or service restart."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def verify(models=False,cuda=False):
    import legal_rag
    from legal_rag import shared
    from legal_rag.config import load_config
    if Path(legal_rag.__file__).resolve().parent != ROOT/'legal_rag':
        raise RuntimeError('A different legal_rag package shadows this checkout')
    config=load_config(ROOT/'config/rag-mvp.json')
    rag=shared().warm()
    library=rag.source_library()
    report={'rag_package':'legal_rag','cards':len(rag.cards),
            'sources':len(library.sources),'units':len(library.units),
            'children':len(library.chunks),'models_checked':models,'cuda_checked':cuda}
    detector=json.loads((ROOT/'config/detector.json').read_text(encoding='utf-8'))
    package=(ROOT/detector['package_dir']).resolve()
    if not package.is_relative_to(ROOT):raise ValueError('Detector path escapes repository')
    spec=json.loads((package/'model.json').read_text(encoding='utf-8'))
    if spec['model_id']!=detector['model_id']:raise ValueError('Detector identity mismatch')
    verified=0
    for name,expected in spec['sha256'].items():
        if Path(name).parts[0]=='weights':continue
        path=(package/name).resolve()
        if not path.is_relative_to(package):raise ValueError('Detector manifest path escapes package')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
                raise ValueError('Pinned detector source mismatch: '+name)
        verified+=1
    report['detector_sources_verified']=verified
    if models:
        from install_detector import install
        from huggingface_hub import snapshot_download
        report['detector']=install(root=ROOT)
        for model in (config.embedder,config.generator):
            snapshot_download(model.model_id,revision=model.revision,local_files_only=True)
        observer=json.loads((ROOT/'config/observer.json').read_text())
        observer_path=ROOT/observer['model_id']
        if not (observer_path/'config.json').is_file() or not any(observer_path.glob('*.safetensors')):
            raise FileNotFoundError('Visual Qwen weights are missing; run download_models.py')
    if cuda:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA required for production inference')
        report['gpu']=torch.cuda.get_device_name(0)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',action='store_true')
    parser.add_argument('--cuda',action='store_true')
    args=parser.parse_args()
    print(json.dumps(verify(args.models,args.cuda),ensure_ascii=False))
