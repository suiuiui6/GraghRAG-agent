# Independent Windows runtime preflight — 2026-10-28

Decision: allow root to execute the complete synthetic backend suite using this new profile, with `-B` and `PYTHONDONTWRITEBYTECODE=1`. This is permission to test an isolated candidate, not production approval, full native security approval, or reuse of R7 results. Default compatibility gate remains closed.

Reviewed AGENTS, memory index/current date, effective 2026-10-19 design and plan (actual plan is `docs/plans/2026-10-19-vector-production-integration.md`). C source remains branch `codex/safe-snapshot-20261019`, HEAD `b1e300f1445c48f9f838bcc0d7b91cb39c1171b2`, with existing dirty work protected. Reviewer writes only this review directory.

## Independent execution

All final commands below used `D:/graghRAG-agent/.tmp/backend-runtime-20261028/.venv/Scripts/python.exe -B`, with bytecode writes disabled, and exited 0:

- `review.py` → `integrity-complete.log`, `independent-integrity.json`.
- `io.py` with production C backend on PYTHONPATH → `io.log`, `independent-io.json`.
- `wheel.py` → `wheel.log`, `independent-wheel.json`.

Actual normal I/O uses new databases only here: SQLite WAL, all connection hardening options, committed BLOB plus rollback, online backup, separate child process with 35-second timeout reopening backup and comparing NumPy vector/cosine, Expat normal XML parse, SSL context and msgpack binary/map roundtrip. Exit 0, child exit 0, observed total I/O 0.625 seconds. Actual profile: Python 3.12.16, SQLite 3.54.0, Expat 2.9.0, OpenSSL 3.5.9, NumPy 2.5.4, msgpack 1.2.3.

## Hash and composition scope

Official archive independently SHA256 hashed to `1f2ab53880fc67ea323398c6388e05af28addc99a8e389209f08a51fdff4b149`. Extracted 3348-file inventory and every SHA match with no missing or extra file. Derived manifest differs from extracted manifest only at the declared SQLite DLL. All current derived 3348 declared files were independently hashed, with no missing file and no non-bytecode mismatch. SQLite DLL matches declared `5ca6a16bdd2c5a5037b1e3a942d9ac1c66efe2def902b202d44774680a8a4656`.

Important receipt limitation: current derived directory has 95 rewritten `.pyc` and six additional `.pyc` generated during prior execution. Thus its current bytes do not exactly equal the original derived manifest. All 101 changed/new caches were independently unmarshalled and compared to fresh compilation of their corresponding hash-verified source, recursively normalizing only `co_filename`; all code objects match. No cache was removed or runtime file changed by this reviewer. Initial reviewer inventory erroneously excluded expected archive pyc and failed; subsequent cache-aware checks retain and disclose actual differences. Logs of these failed reviewer attempts are retained. Another reviewer check initially used incomplete package-name normalization (`boolean.py` vs `boolean-py`); corrected to canonical punctuation normalization before final exit 0.

Venv `sys.executable`, prefix and base_prefix bind respectively to this new env and declared derived Python, with `include-system-site-packages=false`. Editable LangExtract finder points at the new runtime-local copied LangExtract source. Production `vector_runtime` is deliberately imported from the C source under review for the I/O probe.

Copy algorithm reviewed: every old site-packages non-pyc file is copied except RECORD-owned msgpack/LangExtract payload; pre-copy source SHA and post-copy target SHA asserted, then author independently rehashes both endpoints. Reviewer independently recomputed manifest source coverage from actual old payload and metadata RECORD: 33,118 files, exact set equality. Reviewer sampled 101 distributed payload entries and all 49 local LangExtract entries, checking source/current target/manifest SHA equality (150 checks total). Reviewer did not independently rehash the full approximately 2 GB payload. Author's full 33,167 post-assembly source/target recheck has empty mismatch list; this is author execution evidence with reviewed logic, not an independent full rehash. RECORD exclusion only handles in-site-packages paths; scripts outside site-packages are not represented by the payload-copy claim.

New installed 159-package set exactly equals receipt; only msgpack changes relative to old set. All registry-installed versions align with the new lock after standard name canonicalization. msgpack wheel independently hashes to `3ec409b0d6aa8e9eec6eaf881b893caa215dbe68c5319ca96e8a271d81bb111d`; all nine original wheel non-RECORD payload files match installed bytes and all 13 current installed RECORD hash entries verify. Full lock 179 registry tuples and actual installed 159 tuples exactly match their respective audit JSON sets; zero vulnerabilities and zero skipped dependencies. Both author scan commands have recorded exit 0 on this date, fresh per-scan dedicated cache paths, with no ignore-vulnerability options. Reviewer parsed and validated those complete JSONs but did not repeat network audits.

## Boundaries and remaining work

This is a verified installed-payload copy, not a complete clean reinstall. Official download failures/partial and author default-cache access denial plus initial editable-build WinError 5 remain preserved. Successful retry does not erase those failures. Pip audit zero does not cover native library safety; UV, CPython embedded dependencies, BLAS/Torch/CRT and model native audit boundaries remain subject to root's separate work. The supplied expected official source hashes are independently checked against bytes here; authoritative remote provenance/earlier SQLite source audit is relied on as supplied evidence, not freshly re-fetched by this reviewer.

New-profile full backend test/coverage, input stability, Linux bridge/container/rebuild recovery and complete project acceptance remain required. Old R7 coverage does not apply to this new profile. No commit, push, deployment, production migration or gate change performed.
