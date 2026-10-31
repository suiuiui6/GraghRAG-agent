"""Pinned model admission uses local bytes, never a network fallback."""
import hashlib
import json
import os
from pathlib import Path

import pytest
from fastapi import HTTPException
from services import document_runtime as runtime


def test_invalid_model_manifest_rejected_before_loading(tmp_path):
    model = tmp_path / 'model'
    model.mkdir()
    (model / 'config.json').write_text('{}')
    profile = {'model': 'test', 'revision': 'fixed', 'dimension': 2,
               'normalize': True, 'files_sha256': {'config.json': '0' * 64}}
    with pytest.raises(HTTPException) as caught:
        runtime.create_pinned_embedding(model, profile)
    assert caught.value.status_code == 503


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/outside'])
def test_manifest_paths_must_stay_local(tmp_path, name):
    profile = {'model': 'test', 'revision': 'fixed', 'dimension': 2,
               'normalize': True, 'files_sha256': {name: '0' * 64}}
    with pytest.raises(HTTPException) as caught:
        runtime.create_pinned_embedding(tmp_path, profile)
    assert caught.value.status_code == 503


def test_real_offline_fixed_model_encodes_synthetic_input():
    receipt = json.loads(Path(os.environ['GRAPHRAG_TEST_MODEL_RECEIPT']).read_text())
    profile = {'model': 'BAAI/bge-small-zh-v1.5', 'revision': receipt['revision'],
               'dimension': 512, 'normalize': True,
               'files_sha256': {name: item['sha256'] for name, item in receipt['files'].items()}}
    client = runtime.create_pinned_embedding(receipt['snapshot'], profile)
    vectors = client.embed_texts(['锅炉负责人是张三。', '检修时间是周一。'])
    assert client.model_profile == profile
    assert len(vectors) == 2 and all(len(v) == 512 for v in vectors)
    assert all(abs(sum(x*x for x in v) - 1) < 1e-5 for v in vectors)
    assert client.embed_query('负责人') == client.embed_queries(['负责人'])[0]
