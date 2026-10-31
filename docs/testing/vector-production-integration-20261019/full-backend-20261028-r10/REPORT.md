# R10 complete Windows backend Python verification — 2026-10-28

Result: Python source gate PASSED (audit-only-windows). All2201 tests passed, zero failures/errors/skips. Original2187 R9 and2157 R7 identities retained. Production source/coverage scope120/120, missing/extra empty, excluded_lines0.

| Metric | Raw counts | Percentage |
|---|---:|---:|
| Python lines | 16624/17802 | 93.382765981% |
| Python branches | 5481/6086 | 90.059152152% |

Both original-integer90% checks pass. The mixed percent_covered field is not used as either metric. Existing source/omit/thresholds unchanged; no test skip or old-case removal.

The new14 tests were independently executed (14passed, exit0). An unpublished redundant NULL-handle fixture was removed by independent review; invalid-handle post-close probes were replaced with observation of actual successful CloseHandle exactly once. Valid owner query, real child exit, failure/timeout and sanitized CLI assertions remain. No old2187 test was changed for this measurement.

Collect/tests/export exit0; collection10.610s, full test command361.094s, pytest333.14s, export3.672s. Original default60s/command1200s budgets retained. Dependency-library preparation precedes pytest inside coverage; no cold-start SLA improvement is claimed.

Fixed-model HTTP ingest→query→update→delete→fresh-process restart recovery passed (JUnit44.041s); additional fresh reopen10.316s and fixed encode0.304s passed. Independent review recomputed raw totals, complete identity Counters, source scope and current258 captured inputs/3426 selected Python/SQLite/msgpack/tool runtime hashes. All matched before/after/current. Whole site-packages is not claimed rehashed by the runner.

Python3.12.16 / SQLite3.54.0 / msgpack1.2.3 candidate. This report does not replace first-party Rust coverage, formal Linux runtime/model/container reconstruction or native security acceptance. Default production compatibility gate remains closed. No Git commit/push, deployment or real-data migration. R9 below-threshold and earlier failures retained.

Machine reports and explicit derived JUnit identity artifact are archived here; original full logs/JUnit remain private. No captured raw output is copied by this archive.
