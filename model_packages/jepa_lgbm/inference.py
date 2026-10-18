#!/usr/bin/env python3
"""Video -> violation label and at most one estimated timestamp. JSON on stdout."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, help='Path to an ordinary video file')
    parser.add_argument('--out', type=Path, help='Also save the JSON result to this path')
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto', help='auto: CUDA if available, otherwise CPU')
    parser.add_argument('--threads', type=int, default=4, help='PyTorch CPU threads (default: 4)')
    parser.add_argument('--check', action='store_true', help='Verify package, dependencies and selected device')
    args = parser.parse_args()
    if not args.check and args.video is None:
        parser.error('--video is required unless --check is used')
    if args.check and args.video is not None:
        parser.error('Use --check separately from --video')
    try:
        from runtime import ROOT, JepaModel, load_spec, resolve_device
        if args.check:
            spec = load_spec()
            import av
            import cv2
            import einops
            import joblib
            import lightgbm
            import scipy
            import sklearn
            import timm
            import torch
            from threadpoolctl import threadpool_limits
            if sklearn.__version__ != spec['sklearn_version']:
                raise RuntimeError('Install scikit-learn==' + spec['sklearn_version'])
            if lightgbm.__version__ != spec['lightgbm_version']:
                raise RuntimeError('Install lightgbm==' + spec['lightgbm_version'])
            device = resolve_device(args.device)
            result = dict(status='ok', model=spec['model_id'],
                          verified_files=len(spec['sha256']), device=device,
                          gpu=torch.cuda.get_device_name() if device == 'cuda' else None,
                          torch=torch.__version__, sklearn=sklearn.__version__, lightgbm=lightgbm.__version__, package=str(ROOT))
        else:
            result = JepaModel(device=args.device, threads=args.threads).predict(args.video)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(encoded, encoding='utf-8')
        sys.stdout.write(encoded)
        return 0
    except Exception as exc:
        print(f'Inference failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
