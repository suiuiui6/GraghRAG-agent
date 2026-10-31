# Windows backend R12 — audit-only-windows

Final frozen C worktree: codex/safe-snapshot-20261019, HEAD b1e300f1445c48f9f838bcc0d7b91cb39c1171b2 plus protected existing modifications. New Linux build-script v2 integration is included; build.py SHA256 27242d74c351a6d25ed2163d626e7afd3728692df30dfd739a6c2a9c5b8e5082. No C source/runtime modification, commit, push, deployment or production admission was performed by this verifier.

Driver: ../run_backend_20261029_r12.py. Relative to R11, only output directory, baseline JUnit (R11) and purpose text changed. Full exact subprocess commands and exit codes are in commands.json. Execution used the explicitly verified D backend-runtime-20261029/.venv Python, original coverage configuration, model_dependency_bootstrap, all backend/tests and backend/research/test_deepseek_scope_pilot.py. Global 60s, real-model 240s, fresh-child 60s and whole-command 1200s budgets were not changed. Offline model/environment configuration was retained.

- collect: exit 0, 10.469 seconds; actual collection 2223 unique cases.
- tests: exit 0, 383.813 seconds; JUnit 2223 cases, 0 failure/error/skipped.
- coverage export: exit 0, 3.187 seconds.
- R11 baseline: all 2201 Counter identities retained; 22 additional identities. Collection and JUnit identity Counters match exactly.
- Full first-party Python scope: 120 files, missing=[], extra=[], excluded_lines=0.
- Lines: 16669/17848 = 93.39421783953384%; raw integer 90% gate passes.
- Branches: 5506/6114 = 90.05561007523715%; raw integer 90% gate passes.
- 260 source/config inputs and 36704 runtime inputs: before/after equal. Additional actual complete SHA re-read after execution: zero differences (final-recheck.json; exit 0).
- 11 frozen model files: actual size/SHA re-read, zero differences (model-recheck.json; exit 0).

Initial runtime SHA preparation completed at 21:17:21+08, approximately 589 seconds after process start at 21:07:32. Collection began only afterward; preparation was not charged to the pytest subprocess budget. Initial timing is approximate from observed process/artifact timestamps; exact subprocess timing is recorded by the driver.

Compared with R11, runtime keys increased 36682 to 36704: 22 new base Python Lib .pyc caches, the R12 driver added and R11 driver removed. The only common-key SHA change was base Lib/__pycache__/shlex.cpython-312.pyc. Full paths are recorded in runtime-vs-r11-diagnostic.json. No dependency payload/source/native/receipt key changed. These caches were retained and captured rather than excluded.

summary.json and coverage.json hold machine-readable raw counters; before/after and runtime-before/runtime-after bind exact inputs. final-recheck.json additionally verifies the current input bytes. Raw junit.xml and logs remain private because they can contain captured output. junit-identities-only.xml retains only suite metadata and testcase classname/name/time; raw SHA256 3e6a51b6177ef95b18372b76f3af8f1b8e85e51b92559f86dacfabca462f0d36; derived SHA256 29a21183c3912189adad1a2752e2700235e59c659037d8570a6a4e75869dd92e.

This establishes the fixed-scope Windows Python backend test/coverage result for this snapshot. It does not prove native libuv safety, Linux production admission, remote supplier behavior or deployment. The old Windows uv.dll remains unchanged; production compatibility_not_approved stays closed. Independent review remains a separate step.
