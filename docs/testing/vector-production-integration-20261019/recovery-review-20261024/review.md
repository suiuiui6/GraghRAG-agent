# Independent readonly recovery/backup review — 2026-10-24

Target: `C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent`.
Runtime: `D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Scripts/python.exe`.
No production edits, commit, push, or external/paid connections. Only private synthetic local origins/stores used. Root AGENTS, memory index/Oct19 record, Oct19 production design, relevant implementation and tests read. Backend AGENTS absent. Initial unprivileged Git status reported `fatal: this operation must be run in a work tree`; source review uses physical target files.

## Blocking finding

P1 — `backend/services/vector_ingest.py:87`, `connection.getresponse()` does not enforce the declared overall deadline. HTTPResponse header parsing can repeatedly receive header bytes before its socket inactivity timeout, so it does not return to `remaining()` until all headers finish. An attacker-controlled public source can occupy an ingest worker beyond the advertised 60-second budget; a single long header avoids the header-count cap.

Independent concrete reproduction: `independent_probe.py` runs a real loopback HTTP origin, uses the explicit local-origin test callback, and sends 20 header lines at 50ms intervals. `timeout=.2` still consumed 1.21900000004 seconds before `source_download_failed`. No partial asset remained. This is an application deadline failure, not an SSRF bypass. The local callback only permits a deterministic local reproduction of the same HTTP transport behavior. Apply a true deadline during status/header reads and test header trickle, redirects, and body trickle.

Reviewed vector_ingest SHA256: `F1678685010651889E4AFB05300CB260B1040316AC6C92BD4C3DC193DBAF9214`.

## Independently verified

- Original `D:/graghRAG-agent/.tmp/backup-independent-20261023/wal_probe.py` command exited 1 at expected new `ValueError('backup_catalog_integrity')`. Original script does not catch the expected exception and leaks its open attack connection until context cleanup, hence secondary Windows file-in-use cleanup error. No evidence of accepted bad backup.
- Adapted private `independent_probe.py` exited 0: malformed main database + compensating WAL rejected by verify and restore, restore target absent; valid main + corrupting adjacent WAL verified and restored active revision 1; neither verification mutated any backup bytes. JSON retained in `independent_probe.json`.
- Real loopback HTTPS `tls_probe.py` exited 0: numeric socket destinations only; certificate and SNI use original `synthetic.example`; wrong hostname rejected; Host uses original hostname/port; HTTP_PROXY, HTTPS_PROXY, ALL_PROXY pointing to unreachable local port ignored. Temporary private cert/key removed. JSON retained in `tls-result.json`. First attempt exited 1 from a probe-only class replacement fixture error; corrected fixture only adds the local CA to the default context.
- `python -B -m pytest tests/test_vector_url_ingest.py tests/test_vector_ingest_recovery.py -q -p no:cacheprovider --basetemp=D:/graghRAG-agent/.tmp/final-recovery-review-20261024/pytest`: exit 0, **22 passed**, 18.55s. Includes cross-process live leases, commit-before-DONE recovery, uncommitted interruption, rejected private/redirect addresses, pinned numeric resolution, and size/error cleanup.
- `python -B -m pytest tests/test_vector_publication_backup.py tests/test_local_service_quality_behaviors.py tests/test_phase2.py tests/test_service_readiness.py -k backup -q -p no:cacheprovider --basetemp=D:/graghRAG-agent/.tmp/final-recovery-review-20261024/backup-pytest`: exit 0, **38 passed, 75 deselected**, 10.65s. Earlier attempted nonexistent `tests/test_backup.py` command exited 1 with no tests run; corrected after locating the legacy cases.

All Python commands set PYTHONDONTWRITEBYTECODE=1 and PYTHON_DOTENV_DISABLED=1. Synthetic stores use TEMP/TMP in this private directory. One Starlette AnyIO alias deprecation warning in each pytest run.

Other reviewed SHA256:
- vector_backup.py `50C8B54734DF2807649CA34B6C80F1D3B650DD07C84EEBE0EC09B6D5C2453F37`
- routes/ingest.py `2B4A4E9C2B57F05574C4EC92F02024CEDEC875E9A4441FAF198A28BAF27DD146`
- worker.py `72E952212587AEFD4A5304F0CFEFA8E1114DBEC9A315ACF2ADDA19B1445A2E70`

The parent already identified startup recovery wiring as pending. These targeted checks do not establish the full backend acceptance/coverage gates; production remains blocked by the existing compatibility gate and unfinished acceptance.

## Subsequent review of parent's startup wiring

P1 — `backend/services/vector_startup.py:85-86` returns a down state on recovery failure, but does not persist or enforce it. `server.py:219` only stores the state on `app.state.vector_runtime`. `routes/health.py` readiness calls `runtime_status()` afresh, which ignores startup recovery failure. Independent `startup_probe.py` with actual admitted synthetic SQLite store and actual FastAPI health router returned startup `{status:down, ready:false, code:ingest_recovery_failed}` followed immediately by GET `/api/v1/ready` **HTTP200** `{status:ok, ready:true, code:synthetic_only}`. Probe exit0; JSON retained. Injected failure only at recovery boundary, no storage/auth replacement. Existing startup failure unit test checks the returned initializer dictionary and misses actual readiness. Either abort lifespan on recovery failure or ensure health/readiness and request admission retain the failed state until successful recovery; validate actual HTTP.

## Final frozen-fix re-review — both findings closed in reviewed scope

Parent/URL author froze the fixes; independent probes were rerun against the final hashes below. Both earlier P1 findings are now resolved in this scoped review. No new blocking finding identified. This statement is limited to reviewed backup/URL/recovery behavior, not overall project acceptance.

- Final `independent_probe.py`: exit0. Invalid main + compensating WAL rejected; valid main + bad WAL restored active1; archives unchanged. Same slow-header reproduction now exits `source_download_failed` in **0.25 seconds** with **0.2-second budget**, no partial asset. JSON overwritten with final observed result.
- Final `tls_probe.py`: exit0. Original hostname/SNI/certificate checks, wrong-host rejection, numeric-only destinations and ignored proxy environment all reconfirmed. JSON overwritten with final observed result.
- Final `startup_probe.py`: exit0. Failed recovery initializer returns down; actual `/ready` **503**, code `ingest_recovery_failed`. Explicit successful retry reports ready and actual `/ready` **200**. JSON overwritten with final observed result.
- Final `python -B -m pytest tests/test_vector_url_ingest.py tests/test_vector_ingest_recovery.py tests/test_vector_startup_recovery.py tests/test_vector_runtime_health.py -q -p no:cacheprovider --basetemp=D:/graghRAG-agent/.tmp/final-recovery-review-20261024/final-pytest`: **exit0, 37 passed, one Starlette deprecation warning, 16.87s**. Covers slow-header/body watchdog, real TLS hostname, startup health/readiness failure latch and successful retry, and earlier cross-process task/crash cases.

Final frozen SHA256:
- vector_backup.py: `50C8B54734DF2807649CA34B6C80F1D3B650DD07C84EEBE0EC09B6D5C2453F37` (unchanged)
- vector_ingest.py: `FF83DFF078F4A315C3E3DACAC983E455BBC9316D347325184C862B33554CAF49`
- vector_startup.py: `7CE0852214B6264194A925AD333EF59421A3C78FB09550155C6D72CF3CC76259`
- test_vector_startup_recovery.py: `2AD5A5B07DE1B14E6D81B2E2C11A5AA991CF87E98701EE67FB5BE32CA15B9D53`
- test_vector_url_ingest.py: `A60926802EFD6BCBF2C89F5223FF2B47C92861339AABD0F06C1C8AEA80F7CE35`
- routes/ingest.py and worker.py retain earlier listed hashes.

Remaining limits: no external services/paid calls or real production documents; no commit/push; full backend test/coverage gates not revalidated by this scoped review. Startup failure latch gates HTTP readiness/health; it does not claim to stop the process or constitute a global request middleware. Default compatibility admission remains closed.
