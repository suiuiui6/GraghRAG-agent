"""Fail-closed contracts for explicitly supplied local frozen test inputs."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest
from backend.tests.frozen_input_helpers import CODE_ROOT, data_root, assert_current_module, verified_file


def test_default_input_root_is_current_code_root(monkeypatch):
    monkeypatch.delenv('GRAPHRAG_FROZEN_TEST_ROOT', raising=False)
    assert data_root() == CODE_ROOT


def test_explicit_root_is_required_to_exist_without_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv('GRAPHRAG_FROZEN_TEST_ROOT', str(tmp_path / 'missing'))
    with pytest.raises(FileNotFoundError):
        data_root()


def test_relative_or_empty_root_is_rejected(monkeypatch):
    for value in ('', 'relative'):
        monkeypatch.setenv('GRAPHRAG_FROZEN_TEST_ROOT', value)
        with pytest.raises(ValueError, match='ABSOLUTE_FROZEN_TEST_ROOT_REQUIRED'):
            data_root()


def test_wrong_module_origin_is_rejected(tmp_path):
    with pytest.raises(AssertionError, match='CURRENT_CODE_MODULE_REQUIRED'):
        assert_current_module(SimpleNamespace(__file__=str(tmp_path / 'foreign.py')), 'gold_v2')


def test_input_hash_and_path_escape_fail_closed(tmp_path):
    file = tmp_path / 'input'; file.write_bytes(b'original')
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    assert verified_file(tmp_path, 'input', digest) == file
    file.write_bytes(b'drift')
    with pytest.raises(ValueError, match='FROZEN_TEST_INPUT_HASH_MISMATCH'):
        verified_file(tmp_path, 'input', digest)
    with pytest.raises(ValueError, match='FROZEN_TEST_INPUT_OUTSIDE_ROOT'):
        verified_file(tmp_path, '../input', digest)
