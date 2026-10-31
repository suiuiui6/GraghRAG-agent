# Git identity unbounded wait diagnosis — 2026-10-28

Scope: read-only investigation of 1019 checkout; no product, test, config, ignore, old environment, frozen input or Git mutation. systematic-debugging skill read and applied. This report is the only written artifact.

## Confirmed root cause

`backend/research/local_scope_v2.py:55-67` runs rev-parse, binary diff and full untracked status through capture_output subprocess.run with no timeout. Any of these optional on-disk metadata commands can therefore block the entire offline prepare CLI. R8 traceback explicitly waits in status -> subprocess.run -> Windows _communicate -> stdout_thread.join. R8 command exit1 after308.953s and export exit1; no valid coverage/test acceptance. Existing except catches OSError/CalledProcessError, not TimeoutExpired. The fault is an unbounded dependency wait in metadata collection; the precise filesystem/subprocess reason for the intermittent long Git operation remains undetermined.

Read old trace2 JSONL using an in-memory JSON aggregate, never printed argv/path content. 228 events, 5 starts/5 exits(all0), 4 child_start/4 child_exit. Parent Git exit16.789586s. read_directory14.934333s/status untracked14.955180s; index preload1.119982s, status worktrees0.562313s. This independent successful diagnostic supports expensive real enumeration, does not prove R8 had identical timing or that inherited pipes caused R8. No new Git invocation needed: previous trace and actual R8 traceback already establish the product bug without another expensive enumeration.

## Windows timeout trap

Read the actual R8 Python3.12.16 `derived/python/Lib/subprocess.py`: run TimeoutExpired branch kills immediate process then calls process.communicate() without timeout on Windows. Reader threads execute fh.read() through EOF. If a descendant inherits stdout/stderr, killing only the parent need not close all writers. Simple subprocess.run(timeout=N) is therefore not a robust wall-clock bound. Actual trace confirms Git legitimately creates children; inheritance/hanging descendants in R8 are not established and must remain a tested scenario rather than an asserted cause.

## Minimal behavior contract for coder

Preserve all three exact Git commands/inventory completeness and successful hash semantics. Introduce a single small total deadline covering all three commands, rather than independent timeouts whose sum can exceed the test limit. Budget must leave adequate headroom under the unchanged global60s per-test timeout. A failed/expired/incomplete collection must return existing {status:GIT_IDENTITY_UNAVAILABLE, loaded_runtime_identity:UNKNOWN}; never retain a partial commit/diff/status tuple or hash partial output as complete. Optionally add only an enumerated safe reason, never exception text, raw diff/status, cwd/environment or credentials. Do not cache a stale result or skip untracked/submodule inventory.

The process wrapper must bound acquisition, output draining and cleanup; do not use an unbounded cleanup communicate, wait, join or Popen context-manager __exit__. Prefer explicit process-tree lifetime containment (Windows Job Object kill-on-close; POSIX session/process group) plus bounded waits. A cheaper Popen.communicate(timeout)/kill/top-level bounded wait implementation can bound the caller if it deliberately avoids the second communicate, but can leave daemon pipe-reader threads/descendants and needs explicit independent review; do not call that fully cleaned up. Avoid tempfile output redirection because it persists sensitive diff/status bytes contrary to the current in-memory-only contract. Hash incrementally if implementing a draining worker; accept complete output only after successful process completion and completed stream drain.

## Consumer and research boundary

Only current-module prepare_b0 calls _git_identity; prepare_frozen_b0 selects explicit D root but imports current checkout code. Existing tests inspect integrity against original production freeze and assert runtime_identity UNKNOWN. `prepare_b0` independently emits BLOCKED_NOT_EXECUTED, NOT_EXECUTED, M2_OPEN, runtime/embedding/corpus UNKNOWN, source unresolved, transfer and finite-batch NOT_GRANTED. CLI exit0 means valid preparation manifest, not research success. Existing GIT_IDENTITY_UNAVAILABLE fallback already supports unavailable metadata. Changing failure timing must not alter any integrity/gate/authorization value, frozen SHA, corpus, API behavior or production admission. Update LOCAL_SCOPE_V2.md for the bounded metadata/unavailable behavior only; retain research restrictions.

## Required real behavior tests

1. Real temporary Git repository init/commit then modified tracked file and untracked file. Compare hashes against actual exact Git stdout held only in memory. Confirm untracked bytes are not in tracked diff hash.
2. Real executable subprocess fixture (not monkeypatched subprocess.run): sleeps beyond tiny collector budget, asserts bounded caller return and exact unavailable/UNKNOWN, no leaked sensitive sentinel in JSON/stdout/stderr. Test each command phase and total shared deadline, not only status.
3. Real parent that spawns a descendant inheriting stdout/stderr and exits or sleeps. Demonstrate old simple run(timeout) can outlast deadline under an outer bounded harness; repaired collector returns within budget and no owned descendant/reader leak. Cleanup test-owned processes only.
4. Large stdout+stderr concurrently beyond pipe capacity exercises drain/deadlock handling and complete hashes; partial output followed by nonzero exit or deadline must be unavailable, never successful partial identity.
5. Real absent Git / not-a-repository/nonzero error retains sanitized fallback and no exception string. Prepare CLI still reports blocked/not executed and unchanged research gates on timeout. Existing exact freeze and artifact tests remain intact and full backend rerun is still required.

Not executed: new Git operation, code changes, RED/GREEN tests, full backend, coverage, scan or commit. This is diagnosis and handoff, not a claim of fixed or accepted.
