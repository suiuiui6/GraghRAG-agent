# Independent test-contract review — 2026-10-25

Target: C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent
Branch: codex/safe-snapshot-20261019
HEAD: b1e300f1445c48f9f838bcc0d7b91cb39c1171b2 (working changes reviewed)

Result: No actionable assertion weakening or contract regression found in the requested scope. This is a bounded independent test-migration review, not full acceptance or coverage certification.

Scope: git diff against HEAD for test_common_three_arm, test_gold_v2, test_local_scope_v2, test_scope_v2, test_source_mapping_v2, test_runtime_recovery, test_vector_store_resilience, test_hybrid_retrieval_trimming, test_source_control_integration, test_worker_extraction_outcome and test_worker_quality_behaviors; new frozen_input_helpers and test_frozen_input_helpers. Also inspected conftest/request_helpers diffs and current research loader/audit implementations for fixture provenance and isolation.

Evidence and decisions:
- Gold counts, frozen source coordinate expectations, mutation rejections, source-selection abstention and B0 blocked/non-executed/UNKNOWN admission assertions remain intact. Current C research modules are guarded by exact __file__ origin; external historical Python files are only read for hash or AST evidence.
- External inputs require explicit existing absolute GRAPHRAG_FROZEN_TEST_ROOT; no automatic historical fallback. Gold hashes are enforced by the current loader, B0 freeze matches the current registered file, database main hash matches the current registration, and DB/WAL/SHM hashes are compared before/after. Actual audit connection mode=ro is asserted. No database copy/migration introduced.
- Chroma mirror rescue expectations were replaced by approved SQLite fail-closed semantics: corrupt authority preserved, error code checked, mirror sentinel unchanged, authority identity unchanged.
- Projection whitelist/text cap and vector/BM25 long-evidence fusion/identity-conflict assertions remain intact with a real synthetic SQLite backend replacing dummy/Chroma dependencies.
- Runtime recovery health retains degraded recovery component and strengthens default blocked-vector health to unhealthy with compatibility_not_approved. BM25 test now uses the real builder for iterable consumption and checks the actual chunk identity plus pipeline index identity.
- Worker extraction outcome assertions are retained; global os.path.exists patch was removed and filesystem output isolated. Grounding failure injection follows the actual grounding module lookup while retaining error type, code, context, stage, cause, terminal transition and no-event assertions.

Executed with D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider and current C root/backend PYTHONPATH; PYTHONDONTWRITEBYTECODE=1. Basetemp paths are private below this report directory. Research tests explicitly use GRAPHRAG_FROZEN_TEST_ROOT=D:/graghRAG-agent. Target source was not edited.

1. focused.log: helper + resilience + hybrid + extraction outcome + four stage failure cases + SQLite/BM25 identity: 27 passed, exit 0, 5.70s.
2. research.log: common-three-arm frozen P0 call bound + full gold/local-scope/scope/source-mapping suites: 78 passed, exit 0, 52.31s.
3. recovery.log: the two modified runtime-recovery cases: 2 passed, exit 0, 12.02s.

Initial focused attempt failed during all 27 setups because the reviewer had not created the private basetemp parent directory. Created that private directory and reran unchanged tests successfully; this was a review harness setup error, not a target defect.

Reviewed file hashes: reviewed-test-hashes.json. No target edits, commit, push, production migration or deployment. Full backend coverage and overall acceptance remain the root task's separate open checks.
