# Independent final R7 backend evidence review — 2026-10-28

Decision: R7 passes the fixed-scope complete backend test and independent dual-coverage evidence checks for the current hash-bound target snapshot. No blocking evidence inconsistency found. This is not complete production admission, native security approval, Linux/container acceptance, or authorization to commit/push/deploy.

## Independently verified inputs

Target: `C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent`, baseline `b1e300f1445c48f9f838bcc0d7b91cb39c1171b2`. Original static/failed-attempt review remains in report.md; this new file does not replace it. Applied requesting-code-review as independent reviewer.

R7 driver SHA256 independently matches `84bed636a868734839c923529df925fdca3f759f93f53c6172cdd0d1cc559bb8`. Prior independent R6/R7 diff showed only the output directory changes. Whole-command 1200-second limit, test collection targets, offline flags, ROOT/langextract/backend PYTHONPATH, production enumeration, raw integer dual-90 checks, zero-failure/error/skip and input-stability checks remain intact.

Read before.json and after.json independently: 255 entries each and identical SHA256 `b4199695ee3ae5004c76e8cf85a3b5204a5439ce3d96fcb487a5ea8f68008416`. Rehashed every recorded current C input: zero absent files and zero hash drift. Independently walked current backend Python input directories, pruning only dependency/generated/runtime-output locations and named ephemeral test sandboxes; no walk errors, no added or removed Python input relative to the recorded snapshot. R6 and R7 before manifests are exactly equal. This covers current source/tests, locks/config, selected authoritative docs/native bridge inputs as enumerated in the driver; it is not an independent fresh audit of every external installed runtime/model file.

## Execution and coverage

- Raw commands receipt: tests exit 0, 396.141 seconds; coverage export exit 0, 3.328 seconds. Log records collection of 2157 and `2157 passed, 25 warnings in 365.86s`. Warnings are not failures or skips.
- Independently parsed actual junit.xml: 2157 testcase elements, zero failure/error/skipped elements. This goes beyond the driver's nonempty-collection gate and confirms expected full count.
- Independently enumerated 119 current first-party production Python files and compared exact normalized sets with coverage.json: 119 measured, missing=[], extra=[]. Unimported files remain eligible under source=backend and include_namespace_packages=True.
- Coverage config has no diff from baseline b1e300f. Branch tracking and fixed source/omit unchanged; tests/helpers are outside production denominator. exclude_lines and partial_branches are empty. Raw report has zero excluded lines and no file with excluded lines.
- Independently summed each of the 119 per-file summaries; every covered/total line/branch and excluded-line count agrees with report totals.
- Lines: 16456 / 17653 = 93.21928284144339%; integer check 16456*100 - 17653*90 = 56830 >= 0.
- Branches: 5440 / 6044 = 90.0066181336863%; integer check 5440*100 - 6044*90 = 40 >= 0. This passes without rounding, with a very small margin. Report's mixed 92.39988% is not used for either gate.

## Actual model-chain and timing interpretation

Actual JUnit contains exactly one successful `tests.test_vector_http_lifecycle::test_fixed_local_model_http_upload_update_delete_restart`, time 43.470 seconds with no failure/skip child. Log independently marks it PASSED and call duration 42.95 seconds. Current hash-matched test still requires the receipt or skips, sets offline flags, constructs BAAI/bge-small-zh-v1.5 dimension-512 pinned profile, calls production create_pinned_embedding and real authenticated HTTP upload/query/update, verifies old-text disappearance, checks v2 in a fresh process, deletes and verifies 404 in another fresh process. No model substitution was introduced by the bootstrap. Production loader hashes all manifest files, requires essential assets and loads local safetensors with local_files_only=True/trust_remote_code=False. Separate synthetic sibling test checks another live document after deletion; do not describe that particular additional assertion as part of the fixed-model test.

Preparation log is 24.422 seconds. Actual bootstrap prepares trusted SentenceTransformers library inside coverage before pytest collection, outside the lifecycle 240-second marker but inside the tests command 1200-second limit. Global timeout remains 60 seconds; fixed-model lifecycle marker remains 240; fresh real/synthetic children remain 60/35 seconds. Child cold library import, model hash validation/loading and HTTP assertions are inside its own boundary. R7 passing is correct prepared-execution evidence; it does not retrospectively pass old parent cold-start timing or prove performance improvement/root cause.

## Historical failures and remaining limits

Independently read retained R3/R4/R5/R6 summary.json files: all backend_gate=false. Respective tests exits 2/1/2/1; R6 export also 1. These failures are retained and not reclassified by R7. No old R4 JWT-containing raw log or process CommandLine was printed. README draft still needs R6 added to its retained-failures history list at publication; its acceptance requirements and timing description have no false pass statement.

Windows results remain audit-only-windows. Passing tests and package pip-audit receipts do not establish complete CPython/SQLite/NumPy/OpenBLAS/CRT native applicability, Linux actual runtime/container build and persistent restoration, production compatibility admission, or remote CI/branch protection. Default compatibility_not_approved cannot be opened by this evidence review. Cross-subproject impact policy and any submission/security gates remain for the owner to close on the final proposed snapshot.

## Reviewer actions and artifacts

Ran only read-only file/hash/config/XML/JSON verification with explicit locked Python `-B`; verifier execution exited 0. `verify_r7.py` and `check_history.py`, plus machine-readable `final-r7.json`, are in this authorized review directory. JSON records independent counts, exact scope/drift results, config, driver/artifact SHA256 and retained history. No full suite, model import, heavy workload or whole-D-.tmp scan was run; no production/test/config, Git state or existing failure evidence changed. No permission/tool usage failure occurred in this final verification. No commit/push/migration/deployment occurred.
