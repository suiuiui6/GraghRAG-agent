# Security patch independent review — 2026-10-26

Verdict: PASS for copying the three reviewed candidate dependency files into the 1019 working tree and beginning final R3 in the reviewed Windows environment. No blocking correctness or evidence-integrity finding in this bounded patch review. This is not approval for commit, push, deployment, migration, Linux support, or whole-project acceptance.

Reviewer did not change C: sources, install packages, repeat network audits, run the full suite, or submit anything. Read AGENTS.md, memory index/current record, requesting-code-review skill, candidate scripts/logs/reports and relevant FileLock consumers. C: branch/head read as codex/safe-snapshot-20261019 / b1e300f1445c48f9f838bcc0d7b91cb39c1171b2.

## Bound candidate SHA-256

- backend/pyproject.toml: `e9e1c26db6e42966f9bbea3b9274d95d065919c3931c88a57bcf3d37c8b420a8`
- backend/requirements.txt: `a2f13bc4eb914c602cc9b45294340ecdc55334d99f5b585d78d006f6f9f50688`
- backend/uv.lock: `50bb993c6aff56335edd92875d764013d4d91339140c548a79111b1cc2d69a30`

Semantic review: same package names, only registry versions filelock 3.32.7→4.2.1, opentelemetry-api 1.44.0→1.45.1, setuptools 84.0.0→84.1.0. Backend package metadata changes its filelock lower bound; existing uv constraint mechanism gains two transitive lower bounds. No transitive package is falsely promoted to a direct application dependency. Candidate text has LF instead of source CRLF in pyproject/requirements; no additional semantic change identified.

## Independently executed evidence

`review.py` executed using candidate `.venv/Scripts/python.exe -B`, exit 0; final `receipt.json` binds the hashes above. Independently recomputed all 32706 copied file hashes against both the old source environment and new environment: no drift. None overlaps files owned by the three patched distributions. All hash-bearing RECORD entries of the installed patches verified: filelock 29, opentelemetry-api 48, setuptools 344. Distribution enumeration is unique (159 distributions, no duplicate names), equals the old expected installation except the three patched versions, and every installed registry version equals the candidate lock. sys.path and .pth inspection found the new site-packages and its intended derived Python base, with local LangExtract editable finder; no old environment site-packages path injected.

`contract_probe.py` independently executed on actual `WindowsFileLock` 4.2.1, exit 0, `contract-receipt.json`: reentrant counter/release, timeout exception, real cross-process exclusion, thread_local=False cross-thread release, reacquisition, and killed-owner recovery all passed. Four production FileLock consumers were inspected (kg_store, document_catalog, vector_ingest, routes/ingest); used constructors/acquire(timeout)/context-manager/release contracts remain compatible in the exercised Windows domain.

The first reviewer script run exited 1 because the reviewer initially expected 158 installed audit rows. Actual audit contains 159: 158 registry packages plus local LangExtract 1.5.0. The assertion was corrected to require the entire installed set, not relaxed to a subset. The final report records both total and registry count. No product or package change was made in response. The subsequent successful run was repeated only to correct the output's total-count label; all hash checks remained active.

## Inspected author evidence

`commands.json` records lock --check, export, local install, dependency check, both audits and four complete application test modules. No ignore-vulnerability option is used. Independent JSON set comparison confirms the all-lock audit scans exactly all 179 candidate registry package/version pairs, and installed audit exactly all 159 installed package/version pairs; all vuln arrays empty, exits 0. The local editable package's name/version audit row is not a source-code security review of that package.

Application regression JUnit independently parsed: 54 testcases, zero failures, errors or skips, matching log and exit 0. Covers ingest recovery, publication backup, document publication and startup recovery; all under candidate Python, with C: application/test sources. These tests and the native probes are meaningful compatibility evidence, not full project coverage.

Author installation failures remain explicit: initial official-wheel network install timeout exit 1, two full offline attempts exit 1 (missing torch / absl-py). The chosen env is a verified clone of unchanged prior payload plus newly installed patches/local editable package, not a successful clean full reinstall. Author receipt's first boolean.py/boolean-py normalization failure is preserved; PEP503-normalized full-set comparison now succeeds. RECORD consistency does not independently prove the wheel download's publisher identity, but no copied-old-patch overlap or mixed-version footprint was found.

## R3 and release conditions

Root may apply exactly the bound three dependency files and run final R3. Read back destination hashes after copying. Any further dependency/environment/code/config change invalidates the applicable old evidence; final R3 must bind final code/test/config snapshot and preserve failures. Full first-party line and branch coverage separately ≥90%, all required functional/integration/adaptive checks and security checks remain independent acceptance/commit prerequisites under AGENTS.md. No commit/push gate is waived here. Scope remains audit-only-windows; original native/production acceptance limitations do not disappear from a clean Python advisory scan.

## Deployment-config static appendix

Inspected candidate Dockerfile.backend and docker-compose.yml against C: originals, ignoring line-ending-only noise. Exact functional diff is health check /api/v1/health→/api/v1/ready; add graphrag_uploads:/app/uploads and corresponding named-volume declaration. No extra functional edit identified. Hashes:

- Dockerfile.backend: `9d190d9344dac424fc576e23855e296533ef2d16d432c631304b4f027834fd67`
- docker-compose.yml: `001c5da5dc775c5e44b88e7891a7ea8d4731ce02b1569163642eac2807a0193c`

These preparation changes are statically coherent: readiness becomes an actual health requirement, and uploaded revision assets gain a named volume. Root reports compose config --no-env-resolution --no-interpolate --no-path-resolution --quiet exit 0; reviewer did not execute a container engine, read .env, build or deploy. This appendix approves only the bounded config diff as preparation. Linux derived-runtime compatibility is not established, and default readiness 503 means deployment is not ready. Neither config syntax nor a volume declaration proves restart persistence or recovery acceptance.
