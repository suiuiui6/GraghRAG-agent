# Independent startup-order review — 2026-10-27

Decision: no blocking code finding in the two hash-bound test-only candidates. Root may publish them and run the actual focused acceptance followed by the complete fixed-scope backend verification, with the execution conditions below. This is neither a passing model receipt nor permission to commit or release.

## Reviewed inputs

- Target checkout: `C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent`, branch independently read as `codex/safe-snapshot-20261019`.
- Existing target lifecycle SHA256: `f4b9b3475b53e15d33e5aa89e456fa95afb189562ef70c929055e71e4deb3528`.
- Candidate `D:/graghRAG-agent/.tmp/model-startup-order-20261027/test_vector_http_lifecycle.py`: SHA256 `de99fcbef358c8c430a1832aebe4aa2648d4e9b3dfd363a5b3182e0dccde5914`.
- Candidate `D:/graghRAG-agent/.tmp/model-startup-order-20261027/model_dependency_bootstrap.py`: SHA256 `3dda3ed4fb6949f6bd121a374e1d7b031607f0b062890d63b6b7319ea7f5072c`.
- Existing full driver `D:/graghRAG-agent/.tmp/vector-resume-20261022/run_backend_20261026_r4.py`: SHA256 `320ce772dfb81426c9f6dad47daf9d6424b634185ded8775a0dc7ba4f256d2d4`.
- Reviewed new driver `D:/graghRAG-agent/.tmp/vector-resume-20261022/run_backend_20261027_r5.py`: SHA256 `c2e04edc8e125bc8f948487c93e80f01b9392b0777710972ef494a4b9863019a`.
- Read project AGENTS, memory index and target 2026-10-27 record; applied requesting-code-review checklist to the supplied candidate. Existing model-budget review and debugger report were read. No target file was modified.

## Findings and limits

The lifecycle diff contains exactly the early stdin parse and conditional trusted SentenceTransformers import, removing the later duplicate stdin parse. The real profile still recreates its store, reads the actual receipt, verifies/loads the pinned model through the original production function and performs the original HTTP assertions. No assertion, fresh process, model identity, manifest check or 240/60/35 setting is removed. Crucially the fresh child's 60-second subprocess boundary still contains library cold import, application import, model validation/loading and HTTP work. Importing a dependency earlier within that same process is a legitimate ordering change, not an already-loaded parent model inherited by a fresh child.

The parent bootstrap changes the timing boundary: library preparation now happens before pytest collection and therefore outside the 240-second test marker. It must not be described as identical cold-start timing or a model performance improvement. Accept it as explicit test dependency preparation: it imports no model bytes or application module directly, stays inside coverage tracing, and the existing driver has a 1200-second whole-command timeout. Preserve that overall timeout in both the reviewed full-run driver and the focused runner, or supply an equally explicit bounded runner; do not execute the bootstrap indefinitely and then call the outcome unchanged-budget acceptance. Record the preparation wall time and actual complete command wall time, including failed preparations. The 240-second marker continues to bound the actual lifecycle after dependency preparation; it does not prove the old parent cold-start chain passed in 240 seconds.

The wrapper forwards the existing pytest arguments through `sys.argv[1:]` when `runpy.run_module('pytest', run_name='__main__')` executes pytest. It catches no failure or SystemExit, so pytest's failure status remains visible. Its receipt condition only activates dependency preparation; the original acceptance still decides receipt contents and model identity. Retain the runner's preexisting HF/Transformers offline flags before invoking it.

The unchanged coverage configuration starts with `source = backend`, branch tracking, namespace-package discovery and no pragma exemptions; tests are already outside the production denominator. Running the new file under coverage starts the tracer before preparation and before any direct first-party application import. Adding this test executor does not justify excluding any production module. Keep all 119 original production files, unchanged omit/config rules, exact missing/extra checks, independent integer line/branch >=90 gates, failure/error/skip zero and before/after input stability. The actual new driver and resulting reports remain to be checked; this review does not assert they already pass.

The isolated model-first probe reported 50.219 seconds at process level, with dependency import 43.610 seconds and actual 512-dimensional encode observed. It supplies bounded feasibility evidence for the proposed child ordering. It is not a full HTTP lifecycle run, a clean repeated A/B experiment or proof of the import/ntpath causal mechanism. Earlier failures and instrumented native crash remain separate evidence and must be retained. No host-independent startup guarantee is established.

## Smaller alternative considered

The child-only import reorder is the smallest actual application-independent change and is acceptable on its own. It cannot change the parent's collection order: application modules already enter through test imports before test execution. To exercise the same dependency-first parent order, a small pre-collection executor inside coverage is narrower and more transparent than production startup preloading or global conftest behavior. Neither candidate calls for thread-count changes, sys.modules substitution, model caching across process boundaries or further timeout increases.

## Actual reviewer verification

- `git diff --no-index` between current C lifecycle and D candidate: only the import-order diff described above (exit 1 means files differ).
- Locked runtime `D:/graghRAG-agent/.tmp/security-lock-patch-20261026/.venv/Scripts/python.exe -B -c ...compile(read_bytes(), path, 'exec')...`: exit 0, syntax valid for both candidates; no module execution or pycache writing.
- SHA256 values read independently with `Get-FileHash`.
- Read original driver: entire coverage command timeout 1200 seconds; unchanged full source/zero-skip/dual-percentage/input-stability gates observed.
- No complete model test, full suite, coverage export or security scan was run by this reviewer. Root owns those runs on the final published snapshot. No C mutation, commit, push, migration or deployment occurred.

## Final driver follow-up

Independently diffed the new R5 driver against R4. Only the output directory, time import/elapsed recording, three extra authoritative document hashes, replacement of `-m pytest` with the coverage-traced bootstrap script and explicit purpose text change. The complete tests command still has its original 1200-second subprocess timeout. Offline flags, pytest arguments, coverage configuration, production enumeration, raw integer line/branch gates, zero failure/error/skip checks and input-stability checks remain byte-equivalent in their logic. Additional document hashes do not enter the `.py` production denominator. This closes the planned-driver review condition for the SHA above; actual execution and its scope results are still pending.

Proceed only with the bounded preparation interpretation stated above. On any actual timeout/failure, retain it and diagnose; this review supplies no automatic relaxation.

## R5 collection failure / R6 entry-point correction

Root reports R5 stopped in collection with ten `ModuleNotFoundError: backend` errors; it did not execute the tests. The initial static review missed the entry-point search-path difference: `coverage run -m pytest` supplies the working-directory package root, whereas executing a script below `backend/tests` changes the entry-point directory. Preserving argument strings alone did not establish equivalent import resolution. R5 remains failed evidence, not superseded passing evidence.

Independently diffed `run_backend_20261027_r6.py` against the reviewed R5. Exactly two changes occur: output directory becomes `full-backend-20261027-r6`, and `str(ROOT)` is explicitly added to PYTHONPATH after the existing coverage runtime path and before langextract/backend. This restores discovery of the real target `backend` package while retaining current first-party source paths. There is no sys.modules replacement, application-code edit, source/omit change, timeout change or gate change. Both root-qualified `backend.tests` and existing top-level application imports remain resolvable through the intended directories.

R6 driver SHA256: `4f5c29b99669640577feaed28206e0693a783d2a00e834a095dea0db1993dd8f`. Locked Python in-memory syntax compilation exited 0 without executing it or writing bytecode. No model or full suite was run by this reviewer. The two-line correction has no blocking finding and root may run R6; the actual complete run, unchanged 119-file scope and every original gate still require resulting evidence. The parent-preparation timing interpretation above remains unchanged.
