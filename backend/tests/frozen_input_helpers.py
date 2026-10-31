"""Test-only local fixture selector; never changes production input resolution.

GRAPHRAG_FROZEN_TEST_ROOT must explicitly name an existing absolute directory.
Absent configuration means the current checkout; missing inputs fail normally.
Gold/source inspection treats external Python as fixture text. The separately
registered native SDK mock preflight deliberately executes a hash-verified frozen
runtime in a fresh process; it does not provide current production coverage.
"""
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'docs/superpowers/plans/scope-pilot/gold-review-v2'


def data_root():
    value = os.environ.get('GRAPHRAG_FROZEN_TEST_ROOT')
    if value is None:
        return CODE_ROOT
    path = Path(value)
    if not value or not path.is_absolute():
        raise ValueError('ABSOLUTE_FROZEN_TEST_ROOT_REQUIRED')
    path = path.resolve(strict=True)
    if not path.is_dir():
        raise ValueError('FROZEN_TEST_ROOT_DIRECTORY_REQUIRED')
    return path


def assert_current_module(module, name):
    assert Path(module.__file__).resolve() == (CODE_ROOT / 'backend/research' / (name + '.py')).resolve(), 'CURRENT_CODE_MODULE_REQUIRED'
    return module


def current_module(name, namespace='backend.research'):
    return assert_current_module(importlib.import_module(namespace + '.' + name), name)


def verified_file(root, relative, expected):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError('FROZEN_TEST_INPUT_OUTSIDE_ROOT')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('FROZEN_TEST_INPUT_HASH_MISMATCH')
    return path


def frozen_gold():
    # The current checkout's loader owns every source/provenance/hash check.
    return current_module('gold_v2').load_gold(data_root())


def frozen_source(relative):
    package = frozen_gold()
    documents = package.data['documents']
    matching = [key for key, record in documents.items() if record['path'] == relative]
    if len(matching) != 1:
        raise ValueError('UNREGISTERED_FROZEN_TEST_SOURCE')
    return package.texts[matching[0]]


@contextmanager
def frozen_database():
    # Registration remains in the current checkout, not the supplied input root.
    registration = json.loads((CODE_ROOT / PACKAGE / 'local-preflight-20261008.json').read_text(encoding='utf-8'))['corpus_audit']
    expected = registration['sqlite_sha256_before']
    assert expected == registration['sqlite_sha256_after']
    module = current_module('source_mapping_v2')
    path = verified_file(data_root(), 'backend/output/vectordb/chroma.sqlite3', expected)
    before = module._snapshot_hashes(path)
    try:
        yield path
    finally:
        assert module._snapshot_hashes(path) == before, 'FROZEN_DATABASE_BUNDLE_CHANGED'


def prepare_frozen_b0():
    # prepare_b0 reports integrity for its explicit data root; imported code is current.
    frozen_gold()
    registered = CODE_ROOT / PACKAGE / 'local-freeze-v2-20261008.json'
    verified_file(data_root(), str(registered.relative_to(CODE_ROOT)), hashlib.sha256(registered.read_bytes()).hexdigest())
    with frozen_database():
        return current_module('local_scope_v2').prepare_b0(data_root())


def frozen_p0_root():
    registration = json.loads((CODE_ROOT / 'docs/review/common-three-arm-20261015/registration.json').read_text(encoding='utf-8'))
    root = data_root() / '.tmp/public-dev-budget-20261015-r2'
    verified_file(root, 'snapshot.json', registration['frozen_snapshot_sha256'])
    for name, digest in registration['path_proof']['source_sha256'].items():
        verified_file(root, 'backend/' + name, digest)
    return root


def frozen_prompt_root():
    """Bind historical SDK fixture to permanent receipts and the full verifier."""
    relative = 'docs/review/simple-output-20261016'
    receipt = json.loads((CODE_ROOT / relative / 'registration-receipt.json').read_text(encoding='utf-8'))
    root = data_root() / '.tmp/simple-output-20261016'
    registered = verified_file(root, 'registration.json', receipt['registration_sha256'])
    registration = json.loads(registered.read_text(encoding='utf-8'))
    assert registration['runtime_snapshot_sha256'] == receipt['runtime_snapshot_sha256']
    assert registration['governance_sha256'][str(data_root() / relative / 'derived-inputs.json')] == receipt['new_inputs_sha256']
    prompt_path = data_root() / relative / 'prompts.v1.json'
    expected = registration['governance_sha256'][str(prompt_path)]
    actual_prompt = verified_file(data_root(), relative + '/prompts.v1.json', expected)
    permanent = json.loads((CODE_ROOT / relative / 'prompts.v1.json').read_text(encoding='utf-8'))
    assert json.loads(actual_prompt.read_text(encoding='utf-8')) == permanent, 'FROZEN_PROMPT_SEMANTIC_MISMATCH'
    for key, value in permanent.items():
        assert registration[key] == value, 'FROZEN_PROMPT_REGISTRATION_MISMATCH'
    # No replacement verifier: current code checks all source, KG, runtime,
    # environment and governance hashes before this fixture is executed.
    verified = current_module('common_three_arm', namespace='research').verify_registration(root)
    assert verified == registration
    return root
