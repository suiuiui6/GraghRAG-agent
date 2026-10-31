# Independent model-test budget and new-test review — 2026-10-25

Target: C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent, branch codex/safe-snapshot-20261019, HEAD b1e300f plus working changes. Target was read only during this review. Only this private report was written. No full suite or additional model load was launched by the reviewer.

## Budget conclusion

Accept the narrow change from 180 to 240 seconds for test_fixed_local_model_http_upload_update_delete_restart only. This is a correctness/continuous lifecycle acceptance chain, not a latency SLA. Preserve global 60 seconds, real-model child 60 seconds, synthetic child 35 seconds, all lifecycle assertions and fixed coverage scope. A further timeout requires diagnosis rather than another automatic increase. R2 full-suite results remain pending and cannot be inferred from this decision.

Evidence independently read:
- D:/graghRAG-agent/.tmp/vector-resume-20261022/model-timeout-repro-20261025.log: same real-model chain passes without coverage, 118.87s call, 1.98s setup, 122.74s total.
- D:/graghRAG-agent/.tmp/vector-resume-20261022/model-coverage-repro-20261025.log: same chain under coverage passes, 157.24s call, 2.90s setup, 162.90s total. Call overhead is approximately 32.3%. At the 55s diagnostic stack, the parent is still importing BERT/model dependencies inside create_pinned_embedding rather than blocked in business query logic.
- D:/graghRAG-agent/.tmp/vector-resume-20261022/full-backend-20261025-r1/tests.log: aggregate 180s thread timeout occurs in subprocess communication at the second child query after deletion. This is consistent with aggregate budget exhaustion across one parent and two genuine model loads. It does not establish a product query deadlock.

240s is approximately 1.5 times the measured instrumented chain time, leaving about 80 seconds of suite/host variance allowance instead of approximately 20. This is an explicit measured guard budget, not a correctness waiver. Keeping 180 and repeatedly rerunning would leave only a small measured margin; removing a fresh-process load or the delete/restart assertion would weaken acceptance and is rejected. These measurements do not prove an upper bound for all hosts, nor prove the absence of every product performance issue.

Current reviewed source:
- backend/tests/test_vector_http_lifecycle.py:331 child_http_query; :373 subprocess launch; :377 unchanged real/synthetic child timeouts.
- Same file :439-445 documents measured rationale and applies only @pytest.mark.timeout(240).
- Same file :446 onwards still performs actual upload, query v1, explicit update v2, query excluding v1, fresh-process query after update, delete and fresh-process 404 after deletion.
- backend/pyproject.toml tool.pytest.ini_options retains timeout=60.

## Windows process-timeout limitation

Inspected the actual local runtime implementation:
- D:/graghRAG-agent/.tmp/vector-runtime-20261020/derived/python/Lib/subprocess.py:551-559: on TimeoutExpired, kill the Popen handle then call communicate again on Windows without a further explicit timeout.
- Same file :1667-1682: kill/terminate delegates to TerminateProcess for that direct process handle; it does not itself promise recursive process-tree termination.
- D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Lib/site-packages/pytest_timeout.py:505-542: thread timeout eventually calls os._exit(1), bypassing normal Python finally/context cleanup and coverage export.

Actual reviewer probes used the installed venv Python and tiny synthetic child programs, no model, network or target file writes:
1. Popen returned PID 88220 while the child reported Python PID 86136, confirming the venv redirector layer. Child exited0 normally.
2. A second short-lived child used a two-second sleep. After terminating launcher PID 93488, the actual Python PID 97344 was momentarily still alive according to a zero-time WaitForSingleObject check. Pipe draining returned immediately (rounded 0.0s), and a subsequent bounded wait confirmed child exit. This did NOT reproduce a persistent orphan and must not be reported as one.

Therefore a persistent leftover child in the failed model test is a plausible cleanup risk, not an observed fact. Do not describe the existing 60-second subprocess setting as a proven process-tree deadline. Minimal recommendation for this task is the narrow 240-second aggregate budget plus a post-run check for remaining Python children attributable to this test. Only if a leftover is actually reproduced should the helper receive targeted Popen/Windows tree termination and bounded output-drain handling. No generalized new cleanup mechanism is required by the present evidence.

## Bounded static review of the two new test files

Reviewed full text of test_vector_numeric_build_policy.py (10 parameterized cases), test_vector_storage_boundary_behaviors.py (60 parameterized cases), and numeric policy implementation backend/native/vector_numeric/build.py. No additional full suite was run and no independent passing claim is made for these new cases by this review.

No blocking ineffective/assertion-weakening issue found. Assertions exercise externally observable behavior rather than merely obtaining coverage:
- Numeric policy: isolated physical source/binary/receipt files; unapproved build does not install; exact locked offline cargo invocation and checked subprocess calls; platform/compiler/features fail without issuing a receipt; approval/binary/source drift prevents installation; successful installation independently hashes the copied bytes and checks approved receipt identity. Compiler subprocesses are explicitly substituted at the external compiler boundary, so this is build-policy unit evidence, not a real Rust compiler/native binary acceptance result.
- Storage: actual temporary SQLite connections and payload/schema mutations; exact filter result membership through get and search; rejection preserves existing IDs; nested snapshot scope restoration and transaction ownership; manifest/model/dimension mismatch codes for both connection paths; no successful-empty fallback when the collection is missing; WAL checkpoint after early-close or corrupt scan demonstrates released readers; large Unicode pages preserve complete strings; invalid metadata does not appear and private stage is absent; real orphan payload and modified backup schema rejected; source deletion targets exact identity; unrepresentable second-row vector cannot partially insert the valid first row.

Narrow limitation (nonblocking, no change requested): test_vector_storage_boundary_behaviors.py:243 names a nested-metadata case as batch atomicity but supplies one invalid chunk, so that case proves rejection/no mutation/staging cleanup rather than valid-first-row plus invalid-second-row atomicity specifically for nested metadata. The distinct two-row vector test at :351 does cover valid-then-invalid vector atomicity. Do not overstate one as proof of the other.

Reviewed SHA256:
- test_vector_numeric_build_policy.py: 0a3dc467d948ea9fb434f5fccfe1846e2093975a1beb76b12aa4bc10fc4b1920
- test_vector_storage_boundary_behaviors.py: dd6714bcafd2937f4da42eb860d635071f1f3c170983e50095f54d3f4f4c85f3
- test_vector_http_lifecycle.py: 299a3fdbab8099958d5e7dabf20a947f6763a95e61da8ec69985c1aadbd91ffa

No product changes, target edits, commit, push or deployment. Full backend R2, final input freeze, coverage totals and all other acceptance gates remain the root task's independent execution responsibilities.
