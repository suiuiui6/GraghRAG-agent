# Independent backend evidence review — 2026-10-27

## Stage 1: proposed testing README section

Decision: no blocking finding. The proposed `testing-runtime-section-20261027.md` may be appended to the target testing README. This is a static documentation review, not R6 acceptance or production admission.

Reviewed target: `C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent`; HEAD independently read as `b1e300f1445c48f9f838bcc0d7b91cb39c1171b2`. Existing dirty changes were read and preserved. Applied installed requesting-code-review skill as the independent reviewer; read target AGENTS, memory index/current date, vector integration design/plan and fixed coverage configuration.

Independently read the actual bootstrap, current lifecycle test, full R6 driver and startup-order review. R6 driver SHA256 is `4f5c29b99669640577feaed28206e0693a783d2a00e834a095dea0db1993dd8f`.

- Actual bootstrap conditionally imports trusted `sentence_transformers` before `runpy.run_module('pytest', run_name='__main__')`; it does not directly import the application or load pinned model bytes and catches no failure. It runs below coverage and forwards normal pytest arguments.
- Parent preparation falls outside pytest collection/test marker, while the driver's whole tests subprocess retains a 1200-second timeout. README correctly separates preparation timing and does not claim old cold-start timing or performance equivalence.
- Actual lifecycle still has its 240-second marker and actual restart subprocess retains 60 seconds for the real profile, 35 for synthetic. Child reads transport from stdin and imports the trusted library in its own fresh process before application import; it does not inherit a preloaded parent model.
- Driver explicitly includes actual repository root, local langextract and backend in PYTHONPATH, preserves offline flags and frozen-input root. The command structure in proposed README matches it. R5 import-path failure remains a failure.
- Fixed coverage `source = backend`, branch tracking and namespace package discovery include unimported production modules. Test helper is excluded as a test, not a new production exclusion. Empty exclude_lines and partial_branches prohibit pragma exemptions. Current production enumeration returned 119; that PowerShell recursive read also hit denied `.pytest_cache`, so its aggregate count is corroborative rather than authoritative scope evidence. R6 exact measured-file comparison remains pending.
- Driver calculates both gates by integer covered*100 >= total*90, checks exact missing/extra sets, failure/error/skipped zero and snapshot equality. README correctly requires all prescribed tests, not merely the driver's weaker nonempty-collection criterion; stage 2 will independently require all 2157.
- README correctly distinguishes audit-only-windows, package advisory scans, native applicability, Linux/container and persistence checks, and default compatibility_not_approved production gate.

No production, test, configuration, Git state or existing evidence was modified. No tests or model imports were executed. No process CommandLine or old JWT-containing log was printed. R6 reports intentionally not read before root's explicit follow-up. Stage 2 remains pending.

## Stage 2: R6 failed execution follow-up

Root explicitly notified failure and authorized reading R6. Independently read `summary.json`, `commands.json`, selective sanitized log lines and tail, export log, before/after JSON and report presence. No success verification is claimed.

Actual evidence:

- Bootstrap preparation logged 100.063 seconds. Pytest collected 2157 items.
- Test command exited 1 after 421.51499999995576 seconds. `test_local_scope_v2.py::test_b0_preparation_is_not_execution` hit the timeout while `prepare_b0 -> _git_identity -> subprocess.run` waited on `git status --porcelain --untracked-files=all`. This establishes the blocked call stack; it does not establish why Git stalled.
- Export exited 1 after 0.4850000000442378 seconds and logged `No data to report.` Neither coverage.json nor junit.xml exists. Thus no complete passing-test count, scope measurement, line percentage, branch percentage or actual-model-in-full-run success can be certified from R6.
- Before/after JSON each contain 255 entries; independently comparing all before keys against after found zero differing hashes. This is preserved snapshot evidence, not passing acceptance.
- All R6 summary gates are false, including backend_gate. R6 remains a failed complete-suite attempt with partial execution; collection of 2157 does not mean execution of 2157.

The proposed README remains accurate after this failure: it specifies execution and acceptance requirements and makes no R6 passing claim. Its generic list of retained R3/R4/R5 failures may optionally include R6 for current historical completeness, but no substantive false success statement requires correction. No timeout increase, weakened assertion, exclusion or code change is proposed by this reviewer.

Final successful-suite evidence review is pending a new root follow-up. Native applicability, Linux actual runtime/container persistence, and production compatibility admission remain separate open conditions. No tests, model imports or production mutations were performed by this reviewer.

## R7 driver static follow-up

Independently diffed R6 and R7 driver: the sole difference is output directory `full-backend-20261027-r6` to `full-backend-20261027-r7`. Driver SHA256 independently matches `84bed636a868734839c923529df925fdca3f759f93f53c6172cdd0d1cc559bb8`. No budget, path, tests, coverage configuration or gate change occurs. This allows a clean separate report directory and does not erase the failed R6 attempt.

Independently read focused.exit=0 and focused.log tail in `D:/graghRAG-agent/.tmp/git-status-diagnostic-20261027/`: two previously implicated tests passed in 43.69s, calls 20.80s and 22.52s. This supports intermittent execution feasibility under retained limits; it does not prove a root cause or replace the complete suite. Root reports a separately bounded Git diagnostic returned in 16.86s with 5.2MB output retained only as hash, not printed here; this specific measurement was not independently reread by this reviewer.

R7 is in progress. No R7 result was read, no full temporary-tree scan or heavy workload was run. README failure-history list must include R6 when published. Root reports Linux engine is now available, which changes engine availability only; actual runtime/container/persistence and native applicability acceptance still require their own evidence.
