# Health disk artifact candidate — 2026-10-26

Ownership: this directory only. No production or C worktree file was edited.
Target C worktree HEAD: b1e300f1445c48f9f838bcc0d7b91cb39c1171b2.

Candidate: `test_health_artifact_counts.py`, SHA256
`662470e09b493ce307c0cf0218759ed30783ccaf4b4f9d0ff0070bc09250e92d`.
Read root AGENTS, memory index/current record, TDD and verification skills,
current API health specification and existing runtime health tests before writing.
This is existing-behavior characterization, with no production implementation or
claimed red/green implementation cycle.

Fourteen cases exercise actual HTTP GET /api/v1/health and real JSON artifacts:
missing/empty root, stray nondirectory, empty document directory, flat legacy,
two per-document graphs plus legacy files (no double count), malformed and wrong
JSON shape per-document, corrupt flat siblings, missing object keys, empty arrays,
and repeated requests observing changed files. Exact full stats are asserted.
The fixture publishes a real document/chunk/hashed asset to admitted synthetic
SQLite storage and asserts readiness plus active document/chunk counts. JSON,
filesystem operations and counting/HTTP functions are not mocked. Fixture-only
KG path, cached probes, document/query state and unrelated artifact paths are
isolated and restored. Publication state is restored on teardown.

No specification conflict was found in these tested cases. A pre-existing
asymmetry remains unmodified and unendorsed: nodes fallback depends on existence
of per-document node files, whereas edges fallback depends on computed sum zero.
The tests intentionally do not freeze stronger unsupported behavior for flat
edges combined with zero/corrupt per-document edges.

Verification: `run_checks.py` runs the exact commands recorded in `report.json`,
using the existing locked Python environment and unchanged fixed-scope coverage
configuration. Final tests exit 0: 24 passed (14 new + 10 existing runtime health),
one pre-existing Starlette/AnyIO deprecation warning; export exit 0. Bound input
hashes before/after match. Health file has 102/113 lines and 24/26 branches covered.
These are targeted checks, not full backend acceptance or delivery authorization.

Initial attempt used pytest default cross-drive import discovery and exited 4
before collecting tests due D:/WpSystem/__init__.py WinError1337. Evidence is
preserved under `r1/`; final importlib mode plus rootdir/confcutdir resolves it.

Independent review and root-controlled transfer to backend/tests are pending.
Do not claim full backend dual-90, commit, push, deployment or production runtime
admission from these reports. No network or paid API was used.
