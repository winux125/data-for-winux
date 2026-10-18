from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
with tarfile.open(root / 'source.tar.gz', 'w:gz') as archive:
    for directory in ['backend', 'legal_rag', 'forte-vision', 'config', 'deploy', 'scripts', 'tests', 'docs', 'model_packages', '.github']:
        for path in (root / directory).rglob('*'):
            excluded = {'__pycache__', 'node_modules', '.git', '.vercel', '.next', 'dist', '.sites-runtime', '.wrangler',
                        '.venv', 'test-results', 'playwright-report', 'outputs', 'output', 'upload', 'weights'}
            if (path.is_file() and not excluded.intersection(path.parts)
                    and not path.name.startswith('.env') and path.name != 'runtime.env'
                    and path.suffix not in {'.key', '.pem', '.tsbuildinfo', '.pt', '.pth', '.joblib', '.safetensors', '.zip', '.db', '.sqlite', '.log'}
                    and (path.suffix.lower() != '.mov' or 'tests/e2e/fixtures' in path.as_posix())):
                archive.add(path, arcname=path.relative_to(root))
    for name in ['requirements.txt', 'requirements-test.txt', 'README.md', '.gitignore', '.gitattributes']:
        path = root / name
        if path.exists():
            archive.add(path, arcname=name)
