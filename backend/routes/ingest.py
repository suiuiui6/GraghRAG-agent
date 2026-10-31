"""Ingest + status endpoints — §3.2.1, §3.2.2 — REAL pipeline."""

import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, unquote
from filelock import FileLock, Timeout
from services.vector_ingest import task_lock
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from models import (
    IngestResponse, StatusResponse, TaskStatus, StageProgress, TaskResult, TaskError, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE,
)
from routes import add_doc
from services.resource_access import ingest_identity, authorize_resource, is_admin, require_principal, authorized_documents, background_authorizer

from errors import ErrorCode, PipelineError, user_message
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# In-memory task store (persisted to JSON for crash recovery)
TASKS_STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "tasks_store.json")


def _load_tasks() -> dict[str, dict]:
    """Load tasks from JSON file. Returns empty dict on first run or corruption."""
    if os.path.exists(TASKS_STORE_PATH):
        try:
            with open(TASKS_STORE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_tasks(tasks: dict[str, dict], task_id=None):
    """Merge a task and atomically persist it under a cross-process store lock."""
    import datetime as _dt
    def _json_serial(obj):
        if isinstance(obj, (_dt.datetime, _dt.date)):
            return obj.isoformat()
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        if hasattr(obj, 'value'):
            return obj.value
        return str(obj)
    os.makedirs(os.path.dirname(TASKS_STORE_PATH), exist_ok=True)
    with FileLock(TASKS_STORE_PATH + '.lock').acquire(timeout=5):
        current = _load_tasks() if task_id is not None else {}
        current.update({task_id: tasks[task_id]} if task_id is not None else tasks)
        temporary = TASKS_STORE_PATH + '.' + uuid.uuid4().hex + '.tmp'
        try:
            with open(temporary, 'x', encoding='utf-8') as stream:
                json.dump(current, stream, ensure_ascii=False, indent=2, default=_json_serial)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, TASKS_STORE_PATH)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


_tasks: dict[str, dict] = _load_tasks()
_scheduled_leases = {}


def _recover_publication_receipt(task_id):
    from services.document_runtime import get_publication
    service = get_publication()
    if service is None:
        return False
    with service.catalog() as catalog:
        receipt = catalog.task_receipt(task_id)
    if receipt is None or receipt['status'] not in {'done', 'failed'}:
        return False
    if receipt['status'] == 'failed':
        code = receipt.get('error_code') or 'publication_failed'
        existing = _tasks[task_id]
        if existing.get('status') == TaskStatus.FAILED and (existing.get('error') or {}).get('code') == code:
            return True
        existing.update(status=TaskStatus.FAILED, error=TaskError(code=code, message=code).model_dump(),
                        updated_at=datetime.now(timezone.utc))
        _save_tasks(_tasks, task_id)
        return True
    if (_tasks[task_id].get('status') == TaskStatus.DONE
            and (_tasks[task_id].get('result') or {}).get('active_revision') == receipt['result'].get('active_revision')):
        return True
    values = receipt['result']
    result = {key: values[key] for key in TaskResult.model_fields if key in values}
    result['pages_parsed'] = values.get('pages_parsed', values.get('pages'))
    _tasks[task_id].update(status=TaskStatus.DONE, stage='completed', error=None,
                           result=TaskResult(**result).model_dump(), updated_at=datetime.now(timezone.utc))
    _save_tasks(_tasks, task_id)
    return True


def recover_orphaned_tasks():
    """Run once after publication composition, before accepting new requests.

    A kernel lease, rather than a PID or wall clock, proves worker liveness.
    Recovery never retries parsing, embedding, or publication.
    """
    from services.document_runtime import get_publication
    service = get_publication()
    if service is None:
        return
    persisted = _load_tasks()
    for task_id, task in persisted.items():
        if task.get('status') not in {TaskStatus.PENDING, TaskStatus.RUNNING} or task_id in _scheduled_leases:
            continue
        lock = task_lock(TASKS_STORE_PATH, task_id)
        try:
            lock.acquire(timeout=0)
        except Timeout:
            continue
        try:
            latest = _load_tasks().get(task_id)
            if not latest or latest.get('status') not in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                continue
            _tasks[task_id] = latest
            with service.catalog() as catalog:
                with catalog._write():
                    catalog.connection.execute(
                        "UPDATE document_tasks SET status='failed',error_code='ingest_interrupted' "
                        "WHERE task_id=? AND status='prepared'", (task_id,))
            if not _recover_publication_receipt(task_id):
                _tasks[task_id].update(status=TaskStatus.FAILED,
                    error=TaskError(code='ingest_interrupted', message='ingest_interrupted').model_dump(),
                    updated_at=datetime.now(timezone.utc))
                _save_tasks(_tasks, task_id)
        finally:
            lock.release()


def _schedule_indexing(background_tasks, task_id, filepath, filename, file_size, options):
    # Reserve before scheduling: another process restarting during the pending
    # window must not classify this live request's task as orphaned.
    lease = task_lock(TASKS_STORE_PATH, task_id)
    lease.acquire(timeout=0)
    _scheduled_leases[task_id] = lease
    try:
        _save_tasks(_tasks, task_id)
        background_tasks.add_task(_run_indexing, task_id, filepath, filename, file_size, options)
    except BaseException:
        _scheduled_leases.pop(task_id, None)
        lease.release()
        raise


def _run_indexing(task_id, filepath, filename, file_size, ingest_options):
    lease = _scheduled_leases.pop(task_id, None)
    if lease is None:
        lease = task_lock(TASKS_STORE_PATH, task_id)
        try:
            lease.acquire(timeout=0)
        except Timeout:
            return
    try:
        return _run_indexing_locked(task_id, filepath, filename, file_size, ingest_options)
    finally:
        lease.release()


def _run_indexing_locked(task_id: str, filepath: str, filename: str, file_size: int, ingest_options: dict):
    """Background indexing — REAL MinerU → LangExtract → KG pipeline."""

    if _recover_publication_receipt(task_id):
        return
    _tasks[task_id]["status"] = TaskStatus.RUNNING
    _tasks[task_id]["updated_at"] = datetime.now(timezone.utc)
    _save_tasks(_tasks, task_id)

    def progress(stage_key, stage_name, step, details, error=None,
                 error_code=None, degraded=False):
        _tasks[task_id]["stage"] = stage_key
        _tasks[task_id]["progress"] = StageProgress(
            stage_name=stage_name,
            current_step=step, total_steps=5,
            details=details,
        ).model_dump()
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc)
        if error:
            if degraded:
                # 任务**确实完成**，只是结果不完整 —— 骑在 result 上，
                # 不改 TaskStatus（那是 wire 契约，DEGRADED 是质量维度）。
                existing = _tasks[task_id].get("result") or {}
                _tasks[task_id]["result"] = {
                    **existing,
                    "partial": True,
                    "warnings": [*(existing.get("warnings") or []), error],
                }
                logger.warning("ingest_degraded", task_id=task_id, stage=stage_key,
                               error_code=error_code, detail=error)
            else:
                _tasks[task_id]["status"] = TaskStatus.FAILED
                _tasks[task_id]["error"] = TaskError(
                    code=error_code or ErrorCode.INTERNAL_ERROR.value,
                    message=error,
                ).model_dump()
                logger.error("ingest_failed", task_id=task_id, stage=stage_key,
                             error_code=error_code, detail=error)
        _save_tasks(_tasks, task_id)

    # Download once; provider parsing and publication consume the same bytes.
    if filepath.startswith(('http://', 'https://')):
        from services.vector_ingest import materialize_original
        original_path = Path(UPLOADS_DIR) / (task_id + Path(filename).suffix.lower())
        try:
            filepath, file_size = materialize_original(filepath, original_path, max_bytes=MAX_FILE_SIZE)
        except (ValueError, OSError):
            _tasks[task_id].update(status=TaskStatus.FAILED,
                error=TaskError(code='source_download_failed', message='source_download_failed').model_dump(),
                updated_at=datetime.now(timezone.utc))
            _save_tasks(_tasks, task_id)
            return
        _tasks[task_id]['file_size_bytes'] = file_size
        _save_tasks(_tasks, task_id)
    try:
        from worker import run_real_pipeline
        result = run_real_pipeline(task_id, filepath, filename, progress, ingest_options)
    except PipelineError as exc:
        progress(exc.stage.value if exc.stage else "mineru", "Pipeline Error", 0, {},
                 error=exc.message, error_code=exc.code.value)
        return
    except Exception:
        logger.error("ingest_unexpected", task_id=task_id, exc_info=True)
        progress("mineru", "Pipeline Error", 0, {},
                 error=user_message(ErrorCode.INTERNAL_ERROR),
                 error_code=ErrorCode.INTERNAL_ERROR.value)
        return

    if result is None:
        return  # Already marked as failed in progress callback

    from services.document_runtime import get_publication, publish_pipeline_result
    service = get_publication()
    if service is not None:
        try:
            publish_pipeline_result(task_id, filepath, filename, result, ingest_options,
                                    authorize=background_authorizer(ingest_options))
        except Exception as exc:
            from services.document_catalog import CatalogConflict, CatalogNotFound
            code = exc.code if isinstance(exc, CatalogConflict) else 'document_not_found' if isinstance(exc, CatalogNotFound) else 'publication_failed'
            http_status = 409 if isinstance(exc, CatalogConflict) else 404 if isinstance(exc, CatalogNotFound) else exc.status_code if isinstance(exc, HTTPException) else 503
            _tasks[task_id].update(status=TaskStatus.FAILED, error=TaskError(code=code, message=code, http_status=http_status).model_dump(), updated_at=datetime.now(timezone.utc))
            _save_tasks(_tasks, task_id)
            return
    doc_id = result["document_id"]
    if service is None:
        add_doc({**ingest_options.get('identity', {}), 'document_id': doc_id,
                 'filename': filename, 'status': 'indexed', 'kg_path': result.get('kg_path'),
                 'kg_nodes': result['kg_nodes'], 'kg_edges': result['kg_edges'],
                 'pages': result['pages_parsed'], 'indexed_at': datetime.now(timezone.utc).isoformat(),
                 'file_size_bytes': file_size, 'filepath': filepath})
    _tasks[task_id].update({
        "status": TaskStatus.DONE,
        "stage": "completed",
        "progress": StageProgress(
            stage_name="Complete", current_step=5, total_steps=5,
            details={"mineru": "done", "bridge": "done", "extraction": "done", "grounding": "done", "kg_build": "done"},
        ).model_dump(),
        "result": TaskResult(
            document_id=doc_id,
            active_revision=result.get("active_revision"),
            kg_nodes=result["kg_nodes"],
            kg_edges=result["kg_edges"],
            grounded_entities=result["grounded_entities"],
            entity_types=result["entity_types"],
            pages_parsed=result["pages_parsed"],
            kg_path=result.get("kg_path", ""),
            partial=result.get("partial", False),
            warnings=result.get("warnings", []),
        ).model_dump(),
        "updated_at": datetime.now(timezone.utc),
    })
    _save_tasks(_tasks, task_id)

    if service is not None:
        return
    # Hot-reload KG so query endpoint picks up new data
    try:
        from routes.query import reload_kg
        reload_kg()
    except Exception:
        # Non-fatal: KG will load on next query
        logger.error("kg_reload_failed", task_id=task_id, exc_info=True)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(default=None),
    url: str = Form(default=""),
    language: str = Form(default="ch"),
    enable_ocr: bool = Form(default=False),
    enable_formula: bool = Form(default=True),
    enable_table: bool = Form(default=True),
    model_version: str = Form(default="pipeline"),
    # Retained for wire compatibility; true is rejected because legacy cached
    # artifacts cannot prove they belong to this upload.
    allow_cached_mineru_output: bool = Form(default=False),
    replace_document_id: str | None = Form(default=None),
    expected_revision: str | None = Form(default=None),
):
    identity = ingest_identity(request)
    from services.document_runtime import get_publication
    from services.document_catalog import DocumentCatalog, CatalogConflict
    revision = None
    if replace_document_id is not None or expected_revision is not None:
        import re
        if (not replace_document_id or not replace_document_id.strip() or expected_revision is None
                or re.fullmatch(r'[1-9][0-9]*', expected_revision) is None):
            raise HTTPException(422, "replace_document_id and a positive integer expected_revision are required together")
        revision = int(expected_revision)
        target = authorized_documents(request, replace_document_id, write=True)[0]
        if get_publication() is None:
            raise HTTPException(503, "Document vector publication is not configured")
        try:
            DocumentCatalog.require_revision(target, revision)
        except CatalogConflict as exc:
            raise HTTPException(409, detail={'code': exc.code}) from exc
        identity = {key: target.get(key) for key in ('owner_id', 'org_id', 'project_id')}
    publication_context = {'replace_document_id': replace_document_id, 'expected_revision': revision,
                           'principal': dict(require_principal(request)),
                           'selected_project': request.headers.get('X-Project-Id')}
    if allow_cached_mineru_output:
        raise HTTPException(400, detail="Unverified MinerU cache reuse is disabled")
    filename_override = None
    # ── JSON body mode (from Engine-Vue Java backend) ──
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            json_body = await request.json()
            json_url = json_body.get("url", "")
            if json_url:
                url = json_url
            json_filename = json_body.get("filename", "")
            if json_filename:
                filename_override = json_filename
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

    # ── URL mode: skip file upload, pass path directly to worker ──
    url = url.strip()
    if url:
        if not (url.startswith("http://") or url.startswith("https://")):
            if not is_admin(require_principal(request)):
                raise HTTPException(403, detail="Local server paths require administrator access")
            # Administrative integration path
            if not os.path.exists(url):
                raise HTTPException(400, detail=f"File not found: {url}")
            task_id = f"ingest_{uuid.uuid4().hex}"
            filename = filename_override or os.path.basename(url) or "document.docx"
            now = datetime.now(timezone.utc)
            _tasks[task_id] = {
                **identity,
                "task_id": task_id, "status": TaskStatus.PENDING, "stage": "upload",
                "filename": filename, "file_size_bytes": os.path.getsize(url) if os.path.exists(url) else 0,
                "created_at": now, "updated_at": now, "progress": None, "result": None, "error": None,
            }
            ingest_options = {
                "language": language,
                "enable_ocr": enable_ocr,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
                "model_version": model_version,
            }
            ingest_options.update(publication_context)
            ingest_options["identity"] = identity
            _schedule_indexing(background_tasks, task_id, url, filename, os.path.getsize(url), ingest_options)
            return IngestResponse(task_id=task_id, status=TaskStatus.PENDING, filename=filename,
                                  file_size_bytes=os.path.getsize(url), created_at=now, estimated_duration_seconds=60,
                                  links={"status": f"/api/v1/status/{task_id}"})

        task_id = f"ingest_{uuid.uuid4().hex}"
        filename = filename_override or unquote(urlsplit(url).path.rsplit('/', 1)[-1]) or "document.pdf"
        filename = filename.replace('\\', '/').rsplit('/', 1)[-1]
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(400, detail="Unsupported URL document format")
        now = datetime.now(timezone.utc)
        _tasks[task_id] = {
            **identity,
                "task_id": task_id, "status": TaskStatus.PENDING, "stage": "upload",
            "filename": filename, "file_size_bytes": 0,
            "created_at": now, "updated_at": now, "progress": None, "result": None, "error": None,
        }
        ingest_options = {
            "language": language,
            "enable_ocr": enable_ocr,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "model_version": model_version,
        }
        ingest_options.update(publication_context)
        ingest_options["identity"] = identity
        _schedule_indexing(background_tasks, task_id, url, filename, 0, ingest_options)
        return IngestResponse(task_id=task_id, status=TaskStatus.PENDING, filename=filename,
                              file_size_bytes=0, created_at=now, estimated_duration_seconds=60,
                              links={"status": f"/api/v1/status/{task_id}"})

    # ── File upload mode ──
    if file is None:
        raise HTTPException(400, detail="Either file or url parameter is required")

    ext = os.path.splitext(file.filename or "x")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, detail=f"Unsupported format: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, detail=f"File too large: {len(contents)} bytes (max {MAX_FILE_SIZE})")

    task_id = f"ingest_{uuid.uuid4().hex}"
    filepath = os.path.join(UPLOADS_DIR, f"{task_id}{ext}")
    with open(filepath, "wb") as f:
        f.write(contents)

    now = datetime.now(timezone.utc)
    _tasks[task_id] = {
        **identity,
                "task_id": task_id, "status": TaskStatus.PENDING, "stage": "upload",
        "filename": file.filename, "file_size_bytes": len(contents),
        "created_at": now, "updated_at": now, "progress": None, "result": None, "error": None,
    }
    ingest_options = {
        "language": language,
        "enable_ocr": enable_ocr,
        "enable_formula": enable_formula,
        "enable_table": enable_table,
        "model_version": model_version,
        "allow_cached_mineru_output": False,
    }
    ingest_options.update(publication_context)
    ingest_options["identity"] = identity
    _schedule_indexing(background_tasks, task_id, filepath, file.filename or "unknown", len(contents), ingest_options)

    return IngestResponse(task_id=task_id, status=TaskStatus.PENDING,
        filename=file.filename or "unknown", file_size_bytes=len(contents),
        created_at=now, estimated_duration_seconds=60,
        links={"status": f"/api/v1/status/{task_id}"})


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str, request: Request):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, detail=f"Task not found: {task_id}")

    authorize_resource(request, task)
    _recover_publication_receipt(task_id)
    def timestamp(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value

    return StatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        stage=task.get("stage"),
        progress=StageProgress(**task["progress"]) if task.get("progress") else None,
        result=TaskResult(**task["result"]) if task.get("result") else None,
        error=TaskError(**task["error"]) if task.get("error") else None,
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        duration_seconds=int((timestamp(task["updated_at"]) - timestamp(task["created_at"])).total_seconds()) if task.get("updated_at") else None,
    )
