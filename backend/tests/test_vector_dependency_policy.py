"""The shipped runtime must not retain the removed vector backend."""
import tomllib
from pathlib import Path


def test_main_runtime_declares_numpy_and_removes_chroma():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    dependencies = project['project']['dependencies']
    assert 'numpy==2.5.4' in dependencies
    assert not any(value.lower().startswith('chromadb') for value in dependencies)
    requirements = (root / 'requirements.txt').read_text(encoding='utf-8').splitlines()
    assert 'numpy==2.5.4' in requirements
    assert not any(value.lower().startswith('chromadb') for value in requirements)
