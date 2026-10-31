# Independent final v2 review — 2026-10-28

Verdict: no remaining blocking finding in the bounded Git identity fix, its scoped tests, CLI registration or specification. This is local repair acceptance only. It is not full backend acceptance, dual-90 coverage acceptance, security-scan acceptance, research admission, commit, deployment or activation.

## Final binding

Read-only candidate and published C target five files were independently hashed and match `candidate-manifest-v2.json` exactly. See `final-hashes.json` for full hashes. Final local_scope SHA256: `70ab4227fbfa4583b7ad11bbc5406f12dffd85c2f708af8acd2ff955688be6d4`; worker: `915ffed9ef4ba8f6dfd57024f0bcdc2d6d373f3df8b6c1ceb5b2da3cde4580d1`; regression test: `9bec72304edf58e3b64acf6717f7dbd93264d4271b896ed81bc4e6c4b24e8d12`. No author or C target file changed by this reviewer.

## Actual independent commands and results

Working directory: `D:/graghRAG-agent/.tmp/git-identity-independent-review-20261028`.

Python: `D:/graghRAG-agent/.tmp/backend-runtime-20261028/.venv/Scripts/python.exe`.

Explicit environment overrides for pytest: `PYTHONDONTWRITEBYTECODE=1`; `GRAPHRAG_FROZEN_TEST_ROOT=D:/graghRAG-agent`; `TMP`/`TEMP` set to the independent review directory; `PYTHONPATH` = candidate root, C target root, C backend, C langextract in that order. Other inherited environment was not dumped.

Actual arguments:

```text
-B -m pytest --noconftest -p no:cacheprovider -o addopts= -o timeout=60 --basetemp=D:/graghRAG-agent/.tmp/git-identity-independent-review-20261028/pytest-tmp D:/graghRAG-agent/.tmp/git-identity-fix-20261028/backend/tests/test_git_identity_deadline.py -q
```

Exit 0: **30 passed, 1 warning in 26.46s**. Full output is `independent-30.log`. Warning is the existing policy docstring invalid escape, not a skipped test. This scoped run intentionally uses the author regression file without unrelated conftest; root's separate full suite remains required.

Additional reviewer-authored independent command:

```text
-B D:/graghRAG-agent/.tmp/git-identity-independent-review-20261028/independent_small.py
```

Exit 0, output `real_sha256_repository_binary_diff_unicode_untracked PASS`, measured collection elapsed 0.625 seconds. This created an owned SHA-256-format Git repository, committed a binary file, changed tracked binary bytes, added a Chinese-named untracked file, and compared all three exact Git outputs to collector identity. A subsequent change only to untracked body preserves identity. Raw Git outputs stayed in memory. No global Git identity/configuration changed.

## Specification review

- The exact three Git commands and successful raw stdout SHA256 semantics remain intact. Real SHA-1 regression and independent SHA-256 Git repository pass.
- Single 15-second collection budget plus separate two-second cleanup budget; no parent inherited-PIPE draining threads. Worker owns raw capture in memory. Only validated hexadecimal commit plus fixed hashes/flags reach the private temporary JSON.
- Failure/timeout/invalid metadata remains the original unavailable/UNKNOWN pair. Partial identity is not promoted.
- Windows Job is created by the parent, worker joins before launching Git, parent retains the handle, and cleanup executes even after worker/intermediate parent exit. Tests verify ordinary inherited output, exited helper with pipe and no-pipe descendants, individual phase timeout/failure, shared deadline, large concurrent streams, missing Git/nonrepository, invalid large commit, launch/containment failure, cleanup exception, and immediate-worker reap.
- Original BLOCKED_NOT_EXECUTED, NOT_EXECUTED, M2_OPEN, research authorization and UNKNOWN gates are explicitly asserted unchanged.
- Existing input-root adapter hashes retain their old meaning. New current-module-directory two-file collector hashes explicitly deny loaded-runtime identity; no frozen data is modified.

## Code quality, security and test effectiveness

All three preliminary findings are closed in final code: taskkill ancestry race replaced by Job containment; raw/unbounded commit JSON prevented by worker validation and parent validation; Job API OSError no longer bypasses bounded immediate-worker wait. On abnormal Job API failure, the code returns UNKNOWN and attempts bounded immediate-worker reap; do not claim the unavailable Job active-process query proved every descendant stopped. Normal Job cleanup independently exercises active-process-zero and PID assertions.

Regression tests use real executable processes with owned, self-expiring fixtures; launch substitutions select fixture behavior without mocking process execution. Real Git comparison binds complete binary stdout hashes. No PID assertions were weakened, no global 60-second test limit changed, no production coverage range excluded. Worker is explicitly registered as a research CLI, with entrypoint-only print permission. Full R9 must still demonstrate that new worker is included in the complete production denominator and achieve both raw-count coverage thresholds.

## R9 runner static follow-up

Final driver SHA256 `84bcea51ca9636835609ecddb4a4f10dfb03d6d07c2f48fabaf06e8b880f2ea7`. Re-read changes: runtime snapshot now includes driver itself and non-cache coverage-tool files. Earlier static conclusion on collection-count, retained 2157-case Counter, no skipped tests, command exit gates, dynamic complete production scope, separate raw-integer dual90, source/runtime snapshot equality, and unchanged 1200-second whole-command / 60-second per-test budgets stands. Selected runtime snapshot is not a claim that all installed site-packages bytes were hashed. This reviewer did not execute R9.
