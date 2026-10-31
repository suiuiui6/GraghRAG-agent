# Assembly notes
- Owned scope: this directory only. No commit, push, deployment, production storage or gate changes.
- Initial `uv venv` with default cache failed: C:\Users\14156\AppData\Local\uv\cache\sdists-v9\.git permission denied. The failed initialization preceded successful creation with dedicated `--cache-dir` (venv.log / venv.exit).
- `assemble.py` executed with new `.venv/Scripts/python.exe`; stdout/stderr and exit saved in assemble.log / assemble.exit. Source SHA -> copy -> destination SHA assertion per file, excludes msgpack and LangExtract distribution RECORD contents and all pyc. This is a verified copy of installed payload, not a complete clean reinstall.
- `validate.py` records exact commands, exit codes and elapsed time in commands.json; audit failures are retained.

## Verified outcome

Fresh receipt.json captures exact commands/exits and observed UTC timestamp. All six final commands exited 0: offline msgpack install, offline local editable LangExtract build, uv pip check, normal I/O MVP, 179-package complete lock audit, 159-package installed audit. Both audit JSON reports have zero vulnerabilities and zero skipped packages.

33,118 installed-payload files and 49 C LangExtract source/config files had source/target SHA verified during copy and again after assembly; 33,167 rechecks had no mismatch. New Python profile: 3.12.16, SQLite 3.54.0, Expat 2.9.0, OpenSSL 3.5.9, NumPy 2.5.4, msgpack 1.2.3. Package set stayed 159 with only msgpack 1.2.2 to 1.2.3 changed. Synthetic normal.sqlite/backup.sqlite were created only here.

The first editable build failed with sandbox WinError5 in its newly generated build directory; full failure and first command receipt retained under attempt1 names. The normal elevated rerun completed successfully. No exploit payload or pressure/leak loop was generated or executed. Full backend coverage, independent review, final project acceptance and any lock publication remain root responsibilities.

