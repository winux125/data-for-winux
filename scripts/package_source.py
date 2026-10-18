from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
with tarfile.open(root / 'source.tar.gz', 'w:gz') as archive:
    for directory in ['backend', 'forte-vision', 'config', 'deploy', 'scripts', 'tests', 'docs', 'patches', 'model_packages']:
        for path in (root / directory).rglob('*'):
            excluded = {'__pycache__', 'node_modules', '.git', '.vercel', '.next', 'dist', '.sites-runtime', '.wrangler',
                        '.venv', 'test-results', 'playwright-report', 'outputs', 'output', 'upload', 'weights'}
            if (path.is_file() and not excluded.intersection(path.parts)
                    and not path.name.startswith('.env') and path.name != 'runtime.env'
                    and path.suffix not in {'.key', '.pem', '.tsbuildinfo', '.pt', '.pth', '.joblib', '.safetensors'}):
                archive.add(path, arcname=path.relative_to(root))
    for name in ['requirements.txt', 'README.md', '.gitignore']:
        path = root / name
        if path.exists():
            archive.add(path, arcname=name)
