"""Request-owned graphs loaded only from authorized, registered documents."""
import json
import hashlib
import re
from pathlib import Path

import networkx as nx
from fastapi import HTTPException


def contained_asset(value: str, root: Path) -> Path:
    path = Path(value).absolute()
    root = root.resolve()
    def linked(candidate: Path) -> bool:
        return candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)()
    if linked(path) or any(linked(parent) for parent in path.parents if parent != root):
        raise HTTPException(409, "Linked document assets are not supported")
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise HTTPException(409, "Document asset is outside its storage root")
    return resolved


def graph_directory(doc: dict, root: Path) -> Path:
    doc_id = doc["document_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", doc_id):
        raise HTTPException(409, "Invalid stored document identifier")
    if doc.get("kg_path"):
        return contained_asset(doc["kg_path"], root)
    # Both historical storage conventions are document-specific, never global.
    exact = contained_asset(str(root / doc_id), root)
    alternate = contained_asset(str(root / f"doc_{doc_id}"), root)
    return exact if exact.exists() else alternate


def document_graph(doc: dict, root: Path) -> nx.Graph:
    if doc.get('active_revision') is not None:
        return _managed_document_graph(doc)
    directory = graph_directory(doc, root)
    version = 0
    meta_path = contained_asset(str(directory / "versions.json"), root)
    if meta_path.exists():
        version = int(json.loads(meta_path.read_text(encoding="utf-8")).get("active_version", 0))
        if version < 0:
            raise HTTPException(409, "Invalid active graph version")
    if version:
        directory = contained_asset(str(directory / f"v{version}"), root)
    return _graph_from_directory(doc, directory, root, version)


def _graph_from_directory(doc, directory, root, version, *, manifest=None):
    nodes_path = contained_asset(str(directory / "nodes.json"), root)
    edges_path = contained_asset(str(directory / "edges.json"), root)
    graph = nx.Graph()
    if manifest is None and not nodes_path.exists():
        return graph
    def read_json(path):
        if manifest is None:
            return json.loads(path.read_text(encoding='utf-8'))
        relative = path.relative_to(root.resolve()).as_posix()
        expected = manifest.get(relative)
        if expected is None:
            raise HTTPException(409, 'Graph asset is not registered')
        with path.open('rb') as source:
            digest = hashlib.sha256()
            while block := source.read(65536):
                digest.update(block)
            if digest.hexdigest() != expected:
                raise HTTPException(409, 'Graph asset integrity check failed')
            source.seek(0)
            return json.load(source)
    raw = read_json(nodes_path)
    nodes = raw.get("nodes", []) if isinstance(raw, dict) else raw
    raw_edges = read_json(edges_path) if manifest is not None or edges_path.exists() else []
    edges = raw_edges.get("edges", []) if isinstance(raw_edges, dict) else raw_edges
    prefix = doc["document_id"] + "__"
    for node in nodes:
        data = dict(node)
        data.update(document_id=doc["document_id"], document_version=version,
                    source_file=doc.get("filename", ""))
        graph.add_node(prefix + node["node_id"], **data)
    for edge in edges:
        source = prefix + edge.get("source_node_id", edge.get("from", ""))
        target = prefix + edge.get("target_node_id", edge.get("to", ""))
        if source in graph and target in graph:
            graph.add_edge(source, target, **edge)
    return graph


def _managed_document_graph(doc):
    from services.document_runtime import get_publication
    from services.document_catalog import CatalogNotFound, CatalogConflict
    service = get_publication()
    if service is None:
        raise HTTPException(503, 'Managed document storage is unavailable')
    try:
        with service.catalog() as catalog:
            active = catalog.get_active(doc['document_id'])
            if active['active_revision'] != doc['active_revision']:
                raise HTTPException(409, 'Document revision changed')
            if not active.get('kg_path'):
                return nx.Graph()
            with catalog.pin(active['document_id'], active['active_revision']):
                directory = contained_asset(active['kg_path'], service.asset_root)
                manifest = {asset['path']: asset['sha256'] for asset in active['assets']}
                graph = _graph_from_directory(active, directory, service.asset_root,
                                              active['active_revision'], manifest=manifest)
                current = catalog.get_active(doc['document_id'])
                if current['active_revision'] != active['active_revision']:
                    raise HTTPException(409, 'Document revision changed')
                return graph
    except CatalogNotFound as exc:
        raise HTTPException(404, 'Document not found') from exc
    except (CatalogConflict, ValueError, KeyError, OSError) as exc:
        raise HTTPException(409, 'Managed graph integrity check failed') from exc


def authorized_graph(docs: list[dict], root: Path) -> nx.Graph:
    merged = nx.Graph()
    for doc in docs:
        merged = nx.compose(merged, document_graph(doc, root))
    return merged
