"""Historical SDK inputs fail closed before any frozen runtime execution."""
import json
import hashlib
from pathlib import Path
import pytest
from backend.tests import frozen_input_helpers as inputs


def copy_registration(tmp_path):
    source=inputs.data_root()
    root=tmp_path/'.tmp/simple-output-20261016'
    root.mkdir(parents=True)
    (root/'registration.json').write_bytes((source/'.tmp/simple-output-20261016/registration.json').read_bytes())
    return root


def test_missing_historical_profile_fails_without_skip(tmp_path,monkeypatch):
    monkeypatch.setenv('GRAPHRAG_FROZEN_TEST_ROOT',str(tmp_path))
    with pytest.raises(FileNotFoundError):inputs.frozen_prompt_root()


def test_changed_historical_registration_fails_before_runtime(tmp_path,monkeypatch):
    root=copy_registration(tmp_path)
    (root/'registration.json').write_bytes(b'{}')
    monkeypatch.setenv('GRAPHRAG_FROZEN_TEST_ROOT',str(tmp_path))
    with pytest.raises(ValueError,match='FROZEN_TEST_INPUT_HASH_MISMATCH'):inputs.frozen_prompt_root()


def test_prompt_bytes_drift_fails_before_full_verifier(tmp_path,monkeypatch):
    # An independently registered temporary fixture verifies the entire helper
    # path against modified prompt bytes without touching historical evidence.
    root=copy_registration(tmp_path)
    prompt=tmp_path/'docs/review/simple-output-20261016/prompts.v1.json'
    prompt.parent.mkdir(parents=True)
    prompt.write_bytes(b'{}')
    registration=json.loads((root/'registration.json').read_text(encoding='utf-8'))
    original=inputs.data_root()
    governance=registration['governance_sha256']
    governance[str(prompt)]=governance[str(original/'docs/review/simple-output-20261016/prompts.v1.json')]
    governance[str(prompt.parent/'derived-inputs.json')]=governance[str(original/'docs/review/simple-output-20261016/derived-inputs.json')]
    (root/'registration.json').write_text(json.dumps(registration),encoding='utf-8')
    receipt=json.loads((inputs.CODE_ROOT/'docs/review/simple-output-20261016/registration-receipt.json').read_text(encoding='utf-8'))
    receipt['registration_sha256']=hashlib.sha256((root/'registration.json').read_bytes()).hexdigest()
    (prompt.parent/'registration-receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
    monkeypatch.setenv('GRAPHRAG_FROZEN_TEST_ROOT',str(tmp_path))
    monkeypatch.setattr(inputs,'CODE_ROOT',tmp_path)
    with pytest.raises(ValueError,match='FROZEN_TEST_INPUT_HASH_MISMATCH'):
        inputs.frozen_prompt_root()


def test_permanent_prompt_semantic_drift_rejected(tmp_path,monkeypatch):
    original=inputs.CODE_ROOT/'docs/review/simple-output-20261016'
    permanent=tmp_path/'docs/review/simple-output-20261016'
    permanent.mkdir(parents=True)
    (permanent/'registration-receipt.json').write_bytes((original/'registration-receipt.json').read_bytes())
    (permanent/'prompts.v1.json').write_text('{}',encoding='utf-8')
    monkeypatch.setattr(inputs,'CODE_ROOT',tmp_path)
    with pytest.raises(AssertionError,match='FROZEN_PROMPT_SEMANTIC_MISMATCH'):inputs.frozen_prompt_root()
