"""Explicit application composition for admitted document publication.

No environment switch bypasses compatibility admission. A composition root must
supply a DocumentPublication built with an admitted VectorStore. None preserves
legacy KG operation without claiming that vector publication is available.
"""
from __future__ import annotations

import hashlib
import copy
import os
import shutil
from pathlib import Path

from fastapi import HTTPException

_publication = None
_embedding_client = None


def create_pinned_embedding(snapshot, profile):
    """Load exactly the hash-registered local model; never resolve a model ID."""
    try:
        root = Path(snapshot).resolve(strict=True)
        manifest = profile['files_sha256']
        if (not root.is_dir() or type(manifest) is not dict or not manifest
                or not profile.get('model') or not profile.get('revision')
                or type(profile.get('dimension')) is not int or profile['dimension'] < 1
                or profile.get('normalize') is not True):
            raise ValueError('invalid profile')
        for name, expected in manifest.items():
            relative = Path(name)
            if relative.is_absolute() or relative.drive or '..' in relative.parts:
                raise ValueError('invalid asset path')
            digest = hashlib.sha256()
            with (root / relative).open('rb') as source:
                for block in iter(lambda: source.read(65536), b''):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError('model identity changed')
        required = {'config.json', 'modules.json', 'model.safetensors', 'tokenizer_config.json',
                    'tokenizer.json', '1_Pooling/config.json'}
        if not required.issubset(manifest):
            raise ValueError('incomplete model identity')
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(str(root), local_files_only=True, trust_remote_code=False,
                                    model_kwargs={'use_safetensors': True})
        if model.get_sentence_embedding_dimension() != profile['dimension']:
            raise ValueError('model dimension changed')
        return _PinnedEmbedding(model, profile)
    except Exception as exc:
        raise HTTPException(503, 'Pinned embedding model unavailable') from exc


class _PinnedEmbedding:
    def __init__(self, encoder, profile):
        self._encoder = encoder
        self.model_profile = copy.deepcopy(profile)
        self.model = profile['model']
        self.dim = profile['dimension']

    def embed_texts(self, texts):
        import numpy as np
        if not texts:
            return []
        values = np.asarray(self._encoder.encode(texts, normalize_embeddings=True,
                                                show_progress_bar=False, batch_size=32))
        if values.shape != (len(texts), self.dim) or not np.isfinite(values).all():
            raise HTTPException(503, 'Pinned embedding output invalid')
        return values.tolist()

    def embed_text(self, text):
        return self.embed_texts([text])[0]

    def embed_query(self, text):
        return self.embed_text(text)

    def embed_queries(self, texts):
        return self.embed_texts(texts)


def configure_publication(service, embedding_client=None):
    global _publication, _embedding_client
    _publication, _embedding_client = service, embedding_client


def get_publication():
    return _publication


def get_embedding_client():
    global _embedding_client
    service = get_publication()
    if service is None:
        raise HTTPException(503, 'Document vector publication is not configured')
    if _embedding_client is None:
        raise HTTPException(503, 'Pinned embedding client is not configured')
    if (getattr(_embedding_client, 'model_profile', None) != service.model_profile
            or _embedding_client.model != service.model_profile['model']
            or _embedding_client.dim != service.model_profile['dimension']):
        raise HTTPException(503, 'Embedding profile mismatch')
    return _embedding_client


def publish_pipeline_result(task_id, filepath, filename, result, options, *, authorize):
    """Freeze worker output before the catalog transaction; return its receipt."""
    service = get_publication()
    if service is None:
        raise HTTPException(503, 'Document vector publication is not configured')
    chunks = result.pop('_publication_chunks')
    embeddings = result.pop('_publication_embeddings')
    directory = service.asset_root / task_id
    directory.mkdir(exist_ok=True)
    assets = []

    def freeze(source, name):
        target = directory / name
        # Exclusive creation prevents retry from changing committed bytes.
        if target.exists():
            if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(Path(source).read_bytes()).digest():
                raise HTTPException(409, 'Publication asset changed')
        else:
            with Path(source).open('rb') as inp, target.open('xb') as out:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
        assets.append({'path': target.relative_to(service.asset_root).as_posix(),
                       'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        return str(target)

    original = freeze(filepath, 'original' + Path(filename).suffix.lower())
    kg_path = result.get('kg_path')
    frozen_kg = None
    if kg_path and Path(kg_path).is_dir():
        kg_directory = directory / 'kg'
        kg_directory.mkdir(exist_ok=True)
        for asset in sorted(Path(kg_path).iterdir()):
            if asset.is_file() and not asset.is_symlink():
                freeze(asset, 'kg/' + asset.name)
        frozen_kg = str(kg_directory)
    document_id = options.get('replace_document_id') or result['document_id']
    identity = {**{key: value for key, value in result.items() if key not in {'document_id', 'active_revision'}}, **options['identity'], 'filename': filename, 'status': 'indexed',
                'filepath': original, 'kg_path': frozen_kg, 'file_size_bytes': Path(filepath).stat().st_size,
                'kg_nodes': result.get('kg_nodes', 0), 'kg_edges': result.get('kg_edges', 0),
                'pages': result.get('pages_parsed', 0)}
    receipt = service.publish(task_id, document_id, identity, chunks, embeddings, assets=assets,
                              expected_revision=options.get('expected_revision'), authorize=authorize)
    result.update(document_id=document_id, active_revision=receipt['active_revision'], kg_path=receipt.get('kg_path'))
    return receipt
