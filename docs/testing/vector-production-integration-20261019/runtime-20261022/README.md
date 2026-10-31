# 2026-10-22 dependency/runtime validation

Target: codex/safe-snapshot-20261019, existing worktree safe-checkpoint-20261014/graghRAG-agent. Baseline three dependency files were verified clean against HEAD before transfer; originals retained in D:/graghRAG-agent/.tmp/runtime-lock-20261022/original. No commit/push/deploy.

Python: D:/graghRAG-agent/.tmp/runtime-lock-20261022/.venv/Scripts/python.exe. Python3.12.15 / SQLite3.54.0 / NumPy2.5.4. Chroma absent. Final versions aiohttp3.14.4 and certifi2026.10.19. The 1019 langextract gitlink was strictly empty and populated only with the pre-existing isolated local package sources/build metadata; existing user child-repo content was not overwritten.

Final commands (all exit 0):

- uv lock --project TARGET/backend --check --offline --cache-dir SCRATCH/uv-cache --python DERIVED/python.exe --no-python-downloads
- uv export --project TARGET/backend --frozen --all-groups --no-emit-project --no-emit-package langextract --format requirements-txt --output-file SCRATCH/windows-requirements.txt
- uv pip install --python SCRATCH/.venv/Scripts/python.exe --require-hashes --no-deps -r SCRATCH/windows-requirements.txt --cache-dir SCRATCH/uv-cache
- uv pip check --python SCRATCH/.venv/Scripts/python.exe
- Python -B -m pip_audit -r SCRATCH/final-all-lock-requirements.txt --disable-pip --no-deps --format json --output SCRATCH/final-pip-audit-all-lock.json --cache-dir SCRATCH/audit-cache --progress-spinner off
- Python -B -m pip_audit --format json --output SCRATCH/final-pip-audit-full.json --cache-dir SCRATCH/audit-cache --progress-spinner off
- Python -B SCRATCH/final_probe.py

179 universal registry packages audited; 158 Windows-applicable registry versions plus local LangExtract (159 installed), mismatches0/extras0. Final audits found no known vulnerabilities; no advisory ignores used. Real SQLite/NumPy blob roundtrip passes. See machine receipts for exact hashes/versions. This is audit-only-windows and is not full native security or container acceptance.

Initial preserved failures: missing local LangExtract metadata, default uv cache denied, unsupported installed audit --no-deps usage, and certifi PYSEC-2026-4320 fixed2026.10.19 (initial full and universal audit exit1). aiohttp3.14.3's three historical advisories fixed3.14.4. No test timeout or assertions changed.

Normal uv --compile-bytecode completed exit0 but reused installed packages without generating bytecode. The 18930 installed .py source files match exactly before/after. Additional compileall workers4 failed Windows pipe permission; sequential workers1 is still running at this handoff, so its result is NOT claimed. Pre-certifi RECORD full hash probe superseded by final runtime probe; incomplete and not claimed. Fresh process import timing after uv preparation: 48.281s and40.594s total, torch9.422/8.671s, sentence_transformers37.125/30.454s, exits0. These are observed process timings, not an import-time guarantee.

Final bytecode addendum: sequential compileall completed exit0, 171.719s, pyc298→19102, compileall_ok=true. Post-compileall18930 .py hashes exactly match precompile (final-source-compare exit0). The preceding pending description is superseded by this observed final result. No installed dependency source was changed.
