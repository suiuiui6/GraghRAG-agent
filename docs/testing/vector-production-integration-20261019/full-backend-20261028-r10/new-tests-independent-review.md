# Reviewed additional 14 contract cases — final independent review

Verdict: no remaining blocking finding in the revised new test file. Original candidate failure evidence remains retained; no earlier failing result has been overwritten or relabeled.

Final candidate: `D:/graghRAG-agent/.tmp/git-metadata-contract-tests-reviewed-20261028/test_git_identity_failure_contracts.py`, SHA256 `19cbabcd3a74249650d31696139e7a1caf380d140c83b5d57a0ba138e676b431` independently matched immediately before execution. Reviewer changed neither candidate nor production. Current production remains reviewed Git collector v2.

Actual command, exit **0**:

```text
D:/graghRAG-agent/.tmp/backend-runtime-20261028/.venv/Scripts/python.exe -B -m pytest --noconftest -p no:cacheprovider -o addopts= -o timeout=60 --basetemp=D:/graghRAG-agent/.tmp/git-identity-independent-review-20261028/failure-contracts-v2-tmp D:/graghRAG-agent/.tmp/git-metadata-contract-tests-reviewed-20261028/test_git_identity_failure_contracts.py -q
```

Working directory this review directory. Explicit environment: `PYTHONDONTWRITEBYTECODE=1`, `PYTHON_DOTENV_DISABLED=1`, `GRAPHRAG_FROZEN_TEST_ROOT=D:/graghRAG-agent`, `PYTHONPATH=C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent;C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend;C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/langextract`; TMP/TEMP set to reviewer directory. Other inherited environment was not dumped.

Actual output **14 passed in 1.40s**, no skips or fatal-handle diagnostics. Log `failure-contracts-v2.log`.

The reviewed fixture corrections preserve effective assertions. `_ObservedJobApi` calls the actual CloseHandle on a valid owned handle and records its real BOOL return; exact `(handle,True)` singleton assertions prove the supplied resource was successfully closed once. Real query-only / terminate-only access rights still exercise actual OS refusal. The independent owner remains queryable and inactive. Accounting-delay injection changes only query observations while real Job termination, child execution, bounded wait and exit status remain asserted. Failure cleanup avoids double-close by checking the observed successful close.

The invalid NULL helper-input case was redundant with valid restricted-handle failure branches and outside the internal successful-allocation handle contract. Removing this unshipped malformed fixture does not remove an original R9 test, production behavior assertion or uniquely covered branch. No original 2187 case changed. No call probes an already closed handle in the revision. The original independent five-failure evidence and the reason for replacement remain in `failure-contracts-initial-review.md` / `failure-contracts-14.log`.

The remaining cases assert real subprocess invalid/non-ASCII commit rejection before diff, silent default CLI argument failure, mapping coordinate success/failure and sanitized output, allocation failure without configuring a nonexistent handle, and configuration access denial while releasing only the restricted owned handle. Small proxy injections are not substitutes for all OS behavior: owned Jobs, real permissions, actual CloseHandle and real child process lifecycle are executed and asserted.

R10 runner static review: SHA256 `5865c90248f509476c8d7e7459e9a24ec1121f3095c9f1de67f2a2af45ec22fb`. Changes relative to reviewed R9 are only output directory and old-baseline count/path to retain every original 2187 R9 identity. Complete dynamic Python production denominator, both raw-integer90 checks, no-skip/failure/error requirement, snapshots and 1200/60-second limits remain unchanged. No new full R10 run performed by this reviewer.

This is Windows scoped test review (`audit-only-windows`), not Linux acceptance, not Python full coverage acceptance or first-party Rust coverage acceptance, not a claim that diagnostic +12 arcs guarantees a full run. New test publication requires fresh full-suite evidence. No commit/push/deploy/activation claim.
