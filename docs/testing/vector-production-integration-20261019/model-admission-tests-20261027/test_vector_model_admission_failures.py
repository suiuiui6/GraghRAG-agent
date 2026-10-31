"""Real admission failures must precede model loading and persistent mutation."""
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services import document_runtime as runtime
from services.vector_startup import compose_synthetic_runtime
from vector_runtime import SyntheticStorageConfig


def test_matching_hashes_do_not_admit_a_manifest_missing_model_assets(tmp_path):
    snapshot = tmp_path / 'incomplete-model'
    snapshot.mkdir()
    config = snapshot / 'config.json'
    config.write_bytes(b'{"model_type":"bert"}')
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    profile = {
        'model': 'BAAI/bge-small-zh-v1.5', 'revision': 'fixed-local-revision',
        'dimension': 512, 'normalize': True,
        'files_sha256': {'config.json': digest},
    }
    assert list(snapshot.iterdir()) == [config]
    assert all(hashlib.sha256((snapshot / name).read_bytes()).hexdigest() == expected
               for name, expected in profile['files_sha256'].items())

    # Exercise the real admission and hash-checking path, with no loader mock.
    with pytest.raises(HTTPException) as caught:
        runtime.create_pinned_embedding(snapshot, profile)

    assert caught.value.status_code == 503
    assert caught.value.detail == 'Pinned embedding model unavailable'
    assert type(caught.value.__cause__) is ValueError
    assert str(caught.value.__cause__) == 'incomplete model identity'
    assert config.read_bytes() == b'{"model_type":"bert"}'
    assert list(snapshot.iterdir()) == [config]


def test_composition_revision_mismatch_preserves_disk_and_existing_publication():
    profile = {'model': 'fixed-admission', 'revision': 'fixture-v1',
               'dimension': 2, 'normalize': True}
    original_encoder = SimpleNamespace(model_profile=dict(profile),
                                       model=profile['model'], dim=profile['dimension'])
    previous_service = runtime.get_publication()
    previous_encoder = runtime._embedding_client
    try:
        with SyntheticStorageConfig.create() as existing_admission:
            existing_service = compose_synthetic_runtime(existing_admission, profile, original_encoder)
            assert runtime.get_publication() is existing_service
            assert runtime.get_embedding_client() is original_encoder

            with SyntheticStorageConfig.create() as rejected_admission:
                before = {p.relative_to(rejected_admission.root).as_posix(): p.read_bytes()
                          for p in rejected_admission.root.iterdir()}
                assert set(before) == {'.graphrag-synthetic.json'}
                mismatched_encoder = SimpleNamespace(
                    model_profile={**profile, 'revision': 'fixture-v2'},
                    model=profile['model'], dim=profile['dimension'])
                assert mismatched_encoder.model == profile['model']
                assert mismatched_encoder.dim == profile['dimension']
                assert mismatched_encoder.model_profile == {**profile, 'revision': 'fixture-v2'}

                with pytest.raises(ValueError, match='^model_profile_mismatch$'):
                    compose_synthetic_runtime(rejected_admission, profile, mismatched_encoder)

                # A premature VectorStore/DocumentPublication construction would
                # leave a database or asset directory in this allocated root.
                after_paths = {p.relative_to(rejected_admission.root).as_posix()
                               for p in rejected_admission.root.rglob('*')}
                assert after_paths == set(before)
                assert {name: (rejected_admission.root / name).read_bytes()
                        for name in after_paths} == before
                assert runtime.get_publication() is existing_service
                assert runtime.get_embedding_client() is original_encoder
    finally:
        runtime.configure_publication(previous_service, previous_encoder)
