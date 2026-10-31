# Backup rejection contract candidate — 2026-10-26

Scope: candidate tests only. No production source, shared C worktree, Git index, commit or remote changes.

Source: `C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend/services/vector_backup.py`, SHA256 `50c8b54734df2807649ca34b6c80f1d3b650dd07c84eebe0ec09b6d5c2453f37` before execution; recheck recorded in hashes.json.

Candidate: `test_vector_backup_rejection_contracts.py` (49 cases). Uses the unchanged actual publication service fixture from `test_vector_publication_backup.py`, real hardened SQLite connections, actual on-disk archive bytes and immutable asset files. No mock or production patch. Catalog-corruption tests update the sealed database digest deliberately, proving relationship validation, rather than merely a checksum failure. Manifest failures assert the corrupted archive remains byte-for-byte unchanged, live query returns v1, and no restore target/staging survives. Create failures assert no sealed destination and no leaked catalog pins. Empty-database roundtrip exercises the no-revision pin lifecycle.

Actual execution:

```powershell
$env:TEMP='D:/graghRAG-agent/.tmp/backup-behaviors-20261026/os-temp'
$env:TMP=$env:TEMP
$env:PYTHONPATH='D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012;C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend;C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend/tests;C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/langextract'
$env:PYTHON_DOTENV_DISABLED='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:COVERAGE_FILE='D:/graghRAG-agent/.tmp/backup-behaviors-20261026/.coverage'
& '.tmp/runtime-lock-20261022/.venv/Scripts/python.exe' -B -m coverage run --branch --source='C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend/services' -m pytest .tmp/backup-behaviors-20261026/test_vector_backup_rejection_contracts.py -q -p no:cacheprovider --tb=short
& '.tmp/runtime-lock-20261022/.venv/Scripts/python.exe' -B -m coverage json -o .tmp/backup-behaviors-20261026/coverage.json
```

Workdir `D:/graghRAG-agent`. Required sandbox escalation for real synthetic marker writes. Test exit0: **49 passed in43.82s** (`green3.log`); export exit0. No skips. Prior attempts `green.log`/`green2.log` exit1 at fixture setup (sandbox PermissionError creating synthetic marker), kept as failed environment evidence, not product regressions.

Diagnostic scope above is services only, and does **not** substitute for the complete backend gate. Relative to R2, actual vector_backup executed branches intersect16 previously missing arcs, listed in `branch-delta.json`. Candidate-only vector_backup:220/248lines,86/118branches; its standalone percentages omit existing tests and must not be presented as the final combined gate. No production code or coverage configuration was changed to get these results.

Independent review and root full-suite verification remain necessary before publication to the C worktree. The tests cover currently implemented contract behavior; no claimed production fix or TDD red/green implementation change was made.
