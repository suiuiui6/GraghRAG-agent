"""Metadata-only offline CLI. Deliberately has no provider/B0 execution operation."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

from .gold_v2 import PACKAGE_DIR, load_gold, local_path
from .git_identity_worker import _create_job, _stop_job
from .scope_v2 import Source, assemble_scope, resolve_scope
from .source_mapping_v2 import audit_chroma, map_text

ROOT = Path(__file__).resolve().parents[2]
GIT_IDENTITY_TIMEOUT_SECONDS = 15.0
GIT_IDENTITY_CLEANUP_SECONDS = 2.0


def check_package(root):
    package = load_gold(root)
    return {'status': 'LOCAL_SOURCE_BINDING_PASS', 'counts': package.summary,
            'gold_sha256': package.gold_sha256, 'gold_version': '2.0',
            'coordinates': 'LF Unicode_codepoint [start,end)',
            'human_certified': False, 'semantic_answer_scoring': 'NOT_IMPLEMENTED',
            'scientific_stage': 'M2_OPEN', 'api_execution': 'NOT_EXECUTED'}


def auto_scope(root, query, selected_paths, max_bytes):
    # Explicit CLI paths are selection only for this local diagnostic. They are
    # not retrospectively evidence of selection in the production UI.
    sources = [Source(str(Path(path).as_posix()), local_path(root, path).read_text(encoding='utf-8'))
               for path in selected_paths]
    resolution = resolve_scope(query, sources)
    assembly = assemble_scope(resolution, sources, max_bytes)
    return {'routing_status': resolution.status, 'reason': resolution.reason,
            'kind': resolution.kind, 'requested_spans': [asdict(s) for s in resolution.spans],
            'assembly_status': assembly.status, 'mappings': list(assembly.mappings),
            'characters': assembly.characters, 'utf8_bytes': assembly.utf8_bytes,
            'max_bytes': max_bytes,
            'assembled_text_sha256': hashlib.sha256(assembly.text.encode('utf-8')).hexdigest(),
            'local_scan_proof': assembly.scan_proof,
            'source_selection_evidence': 'EXPLICIT_LOCAL_CLI_PATHS_NOT_PRODUCTION_UI',
            'api_execution': 'NOT_EXECUTED'}


def _integrity(root, expected):
    records = {}
    for path, wanted in expected.items():
        file = local_path(root, path)
        actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
        records[path] = {'expected': wanted, 'actual': actual, 'match': actual == wanted}
    return {'all_match_freeze': all(r['match'] for r in records.values()), 'files': records,
            'interpretation': 'On-disk hash comparison only, not loaded runtime identity.'}


def _stop_identity_worker(process, job):
    """Reap only our worker's process tree, with a separate bounded budget."""
    deadline = time.monotonic() + GIT_IDENTITY_CLEANUP_SECONDS
    stopped = True
    try:
        if job is not None:
            stopped = _stop_job(job, deadline)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
    except OSError:
        stopped = False
    finally:
        # A Job API error must not bypass bounded reaping of our immediate
        # worker. Keep using this cleanup's original deadline.
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                stopped = False
        try:
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except (OSError, subprocess.TimeoutExpired):
            stopped = False
    return stopped


def _git_identity(root):
    unavailable = {'status': 'GIT_IDENTITY_UNAVAILABLE', 'loaded_runtime_identity': 'UNKNOWN'}
    deadline = time.monotonic() + GIT_IDENTITY_TIMEOUT_SECONDS
    process = None
    job = None
    result = unavailable
    try:
        # Only the fixed trusted worker's small, sanitized JSON reaches this
        # private auto-deleted file. Raw Git stdout/stderr stay in worker memory.
        # No parent PIPE/read thread can be held open by a Git descendant.
        with tempfile.TemporaryFile() as output:
            command = [sys.executable, '-B', str(Path(__file__).with_name('git_identity_worker.py').resolve()), str(root)]
            if os.name == 'nt':
                job, name = _create_job()
                command.append(name)
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
                close_fds=True, start_new_session=os.name != 'nt')
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
            if process.returncode != 0 or time.monotonic() > deadline:
                return unavailable
            output.seek(0)
            raw = output.read(4097)
            if len(raw) > 4096:
                return unavailable
            result = json.loads(raw)
            keys = {'commit', 'tracked_diff_sha256', 'status_inventory_sha256',
                    'untracked_content_in_diff_hash', 'loaded_runtime_identity'}
            if (not isinstance(result, dict) or set(result) != keys
                    or not isinstance(result['commit'], str)
                    or re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', result['commit']) is None
                    or result['untracked_content_in_diff_hash'] is not False
                    or result['loaded_runtime_identity'] != 'UNKNOWN'
                    or any(not isinstance(result[key], str) or len(result[key]) != 64
                           or any(c not in '0123456789abcdef' for c in result[key])
                           for key in ('tracked_diff_sha256', 'status_inventory_sha256'))):
                return unavailable
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return unavailable
    finally:
        try:
            if process is not None:
                if not _stop_identity_worker(process, job):
                    result = unavailable
            elif job is not None:
                _stop_job(job, time.monotonic() + GIT_IDENTITY_CLEANUP_SECONDS)
        except OSError:
            result = unavailable
    return result


def _artifact_metadata(root):
    result = {}
    for name, path, field in (
        ('bm25', 'backend/output/runtime/bm25_artifact.json', 'chunks'),
        ('tables', 'backend/output/runtime/table_artifact.json', 'rows'),
        ('docs_store', 'backend/output/docs_store.json', None),
    ):
        file = local_path(root, path)
        try:
            raw = file.read_bytes()
            data = json.loads(raw)
            records = data if field is None else data.get(field)
            if not isinstance(records, list):
                raise ValueError('UNSUPPORTED_ARTIFACT_SCHEMA')
            result[name] = {'status': 'LOCAL_METADATA_READ', 'path': path,
                            'sha256': hashlib.sha256(raw).hexdigest(),
                            'records': len(records), 'runtime_loaded': 'UNKNOWN'}
        except (OSError, ValueError, AttributeError):
            result[name] = {'status': 'ARTIFACT_UNAVAILABLE_OR_UNSUPPORTED',
                            'path': path, 'runtime_loaded': 'UNKNOWN'}
    return result


def prepare_b0(root):
    root = Path(root).resolve()
    package = load_gold(root)
    freeze = json.loads(local_path(root, f'{PACKAGE_DIR}/local-freeze-v2-20261008.json')
                        .read_text(encoding='utf-8'))
    production = _integrity(root, freeze['production_files_sha256'])
    source_files = {v['path']: v['sha256'] for v in package.data['documents'].values()}
    historical = freeze['historical_run_checkpoint']
    historical_files = {f"{historical['path']}/{name}": digest
                        for name, digest in historical['files_sha256'].items()}
    database = local_path(root, 'backend/output/vectordb/chroma.sqlite3')
    if database.exists():
        try:
            corpus = audit_chroma(database, package.texts, collection='rag_docs')
        except (sqlite3.Error, OSError, ValueError):
            corpus = {'status': 'CORPUS_AUDIT_UNAVAILABLE', 'runtime_membership': 'UNKNOWN'}
    else:
        corpus = {'status': 'CORPUS_UNAVAILABLE', 'runtime_membership': 'UNKNOWN'}
    tools = {f'backend/research/{name}.py': hashlib.sha256(local_path(root,
             f'backend/research/{name}.py').read_bytes()).hexdigest()
             for name in ('gold_v2', 'scope_v2', 'source_mapping_v2', 'local_scope_v2')}
    collector_sources = {
        f'backend/research/{name}.py': hashlib.sha256(Path(__file__).with_name(name + '.py').read_bytes()).hexdigest()
        for name in ('local_scope_v2', 'git_identity_worker')}
    return {
        'status': 'BLOCKED_NOT_EXECUTED', 'api_execution': 'NOT_EXECUTED',
        'scientific_stage': 'M2_OPEN', 'gold_version': '2.0',
        'gold_sha256': package.gold_sha256, 'human_certified': False,
        'arms': ['B0_NATIVE', 'C_NATIVE_CONTEXT', 'C_AUTO_SCOPE', 'C_ORACLE_SCOPE'],
        'git': _git_identity(root), 'adapter_sha256': tools,
        'collector_source_sha256': collector_sources,
        'collector_source_basis': 'CURRENT_MODULE_DIRECTORY_ON_DISK_NOT_LOADED_IDENTITY',
        'production_integrity': production, 'source_integrity': _integrity(root, source_files),
        'historical_integrity': _integrity(root, historical_files),
        'local_artifact_metadata': _artifact_metadata(root),
        'corpus_snapshot': corpus,
        'gates': {
            'gold_local_source_binding': 'PASS',
            'on_disk_production_freeze': 'PASS' if production['all_match_freeze'] else 'DRIFT_REQUIRES_REVIEW',
            'runtime_identity': 'UNKNOWN', 'local_embedding_runtime_ready': 'UNKNOWN',
            'native_corpus_document_identity': 'UNKNOWN', 'index_coordinate_gate': 'UNVERIFIED',
            'production_source_selection': 'SOURCE_UNRESOLVED',
            'same_version_native_context_capture': 'NOT_CAPTURED',
            'prompt_and_request_envelope_freeze': 'NOT_CAPTURED',
            'call_graph_and_retry_bound': 'UNVERIFIED',
            'provider_transfer_authorization': 'NOT_GRANTED_FOR_THIS_BATCH',
            'redacted_export_and_original_mapping': 'NOT_PREPARED',
            'finite_batch_authorization': 'NOT_GRANTED_FOR_THIS_BATCH',
            'state_cache_session_plan': 'NOT_FROZEN',
            'human_gold_certification': 'PENDING_SEPARATE_REVIEW',
        },
        'conditional_call_proposal': {'upper_bound': 54, 'authorized': False,
            'formula': '9 * (1 native preprocessing + 2 native generation attempts + 3 controlled calls)',
            'condition': 'Only if complete call graph proves no additional model calls. '
                         'Otherwise BLOCKED_CALL_BOUND; no monetary cap inferred.'},
        'questions': [{'id': q['id'], 'query_version': q['query_version'],
                       'query_sha256': hashlib.sha256(q['query'].encode('utf-8')).hexdigest(),
                       'source_selection': 'SOURCE_UNRESOLVED',
                       'native_context_capture': 'NOT_CAPTURED', 'status': 'NOT_RUN'}
                      for q in package.data['questions']],
        'native_preservation_contract': [
            'Preserve production retrieval, rescues, reranking, prompt, postprocessing and provider envelope.',
            'Keep extra_body thinking and max_retries=1 (up to two sends); never silently fix native B0.',
            'Record actual preprocessing model; v4-pro generation identity requires runtime evidence.',
            'document_id echo is not source filtering; keep actual native mixed-corpus behavior.',
            'include_evidence_trace changes unavailable-pipeline fallback; record capture options as instrumentation.',
            'Record raw output, staged output and API-visible 4000-character truncation separately.',
            'Controlled adapter is not B0. Reuse captured same-query-version preprocessing/context only.',
            'No old answers rescored; missing/transformed/unmapped corpus is not a model failure.',
        ],
        'required_capture_fields': ['loaded_runtime_identity', 'dependency_lock_hashes', 'model_actual_id',
            'source_selection_provenance', 'index_snapshot_hashes', 'prompt_hash',
            'redacted_request_body_hash', 'query_version', 'preprocessed_query',
            'actual_serialized_context', 'context_source_mappings', 'raw_answer', 'staged_answer',
            'api_visible_answer', 'usage', 'retry_attempts', 'cache_state', 'session_state',
            'controlled_arm_order_seed', 'shared_budget_and_truncation_policy', 'review_disagreements'],
        'one_next_action': 'Verify runtime/corpus identity and source mapping without modifying native B0; '
                           'then register and authorize a finite new batch separately.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check')
    commands.add_parser('prepare-b0')
    auto = commands.add_parser('auto')
    auto.add_argument('--source', action='append', default=[], help='Explicit project-relative selected source')
    auto.add_argument('--query', required=True)
    auto.add_argument('--max-bytes', type=int, default=8192)
    mapping = commands.add_parser('map')
    mapping.add_argument('--source', required=True)
    mapping.add_argument('--chunk-file', required=True, help='Project-relative local chunk text file')
    mapping.add_argument('--stored-start', type=int)
    mapping.add_argument('--stored-end', type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == 'check':
            report = check_package(args.root)
        elif args.command == 'prepare-b0':
            report = prepare_b0(args.root)
        elif args.command == 'auto':
            report = auto_scope(args.root, args.query, args.source, args.max_bytes)
        else:
            if (args.stored_start is None) != (args.stored_end is None):
                raise ValueError('BOTH_STORED_COORDINATES_REQUIRED')
            source = local_path(args.root, args.source).read_text(encoding='utf-8')
            chunk = local_path(args.root, args.chunk_file).read_text(encoding='utf-8')
            stored = None if args.stored_start is None else (args.stored_start, args.stored_end)
            report = map_text(source, chunk, stored)
        sys.stdout.write(json.dumps(report, ensure_ascii=True, indent=2) + '\n')
        # Prepared-but-blocked is a valid manifest, not execution success.
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        sys.stdout.write(json.dumps({'status': 'LOCAL_VALIDATION_FAILED',
                                    'api_execution': 'NOT_EXECUTED'}) + '\n')
        return 2  # Never dump potentially sensitive exception contents.


if __name__ == '__main__':
    sys.exit(main())
