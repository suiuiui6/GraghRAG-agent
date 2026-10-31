# Independent Linux CPU lock review — 2026-10-29

Decision: PASS as a real resolver-generated private CPU lock/graph, with stated limits. It is suitable input for an isolated fixed-lock Linux installation now, with installer-enforced artifact hashes and retained actual-artifact/build receipts. It is not evidence of a completed Linux installation, all-wheel integrity verification, security clearance or production admission. No lock/graph correctness blocker found. Missing historical complete-wheel copies are not a reason to redownload indefinitely or stop an otherwise hash-enforced install. The controls below can be fulfilled as part of that installation.

## Independently verified

- Candidate backend uv.lock SHA d1434b9b8b46f3d9c061098e15ddaada44e8d0a2d3dfb55d4db4c425a8f60b36 differs from unchanged main seed6168a2319f7b2964b7f325ab700444c5974b7c2c6fbc4ee95bb0c5eefdca1b90. Actual authorized resolver result exit0; this is not the earlier static/manual draft.
- Root's normal online uv lock --check completed exit0 in46.641seconds, reports159 packages resolved in42.79seconds, lock SHA identical before/after. Source command/result/stdout/stderr read directly. Reviewer did not rerun network or install. Offline --check failure remains retained and explicitly distinct from this successful online check.
-159 lock records include a virtual backend root; independent CPython Linux x86_64 marker closure yields133 runtime nodes (131registry+1Torch URL+1editable langextract),158 all-group nodes (156registry+1Torch URL+1editable). All active graph edges independently equal actual-graph-diff.json. No active cuda-/nvidia-/triton nodes. Runtime/main comparison removes19 GPU nodes, adds none. All-lock comparison removes22 nodes (additional platform-inactive colorama/httpx2-jsfetch/tzdata); these are not all GPU removals.
- Only retained package version change is torch2.14.0 ->2.14.0+cpu. Every retained non-Torch source is byte-structure equal to main lock; every retained non-Torch wheel/sdist URL+hash pair occurs in main lock. GPU removal is a real resolver graph result. CUDA names still present as inactive constraints do not imply installed or selected nodes.
- Candidate pyproject adds one explicit hash-qualified PEP508 Torch dependency, narrows requires-python from>=3.12,<3.13 to==3.12.*, sets Linux/x86_64 environments and preserves main versions as constraints (Torch constraint changes to+cpu). Original project dependencies and dev groups remain unchanged; local langextract pyproject bytes unchanged. C source inputs still match inputs-before.json and baseline copies.

## Torch identity and platform boundary

Exact lock source URL:
https://download-r2.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl

Declared SHA256:a09987c95ec4cffdb6df798d3d641558110a334cfccce22f2f046d83142bc260.

Independently checked the previously captured official https://download.pytorch.org/whl/cpu/torch/ index HTML hash afbb7e04f36d5c3d8b7141bcf10682954f05bb4d5f0297876127ffbb93f015f8 and exact link/hash fragment occurrence. Index receipt and candidate direct requirement agree; lock canonical source drops the fragment but wheel record retains identical hash. This establishes consistency with publisher declaration, not independent digest verification of complete local wheel bytes.

Supported measurement target here is CPython3.12 Linux x86_64 with compatible glibc>=2.28, as encoded in the cp312/cp312/manylinux_2_28_x86_64 wheel. Lock environment markers only say Linux/x86_64 and Python3.12.*, so do not overclaim musl, PyPy, aarch64 or Windows compatibility. Independent closure was calculated explicitly at Linux CPython3.12.16 (also checked same node sets at3.12.0/8/20). Actual resolver and root check executed on Windows CPython3.12.8; this is legitimate declared-target resolution, not an actual Linux3.12.16 installation/run.

## Cache and wheel verification limit

Initial sources.url with fragment was rejected, so author used normal PEP508 direct requirement. Real resolver succeeded with hash-bearing request. Subsequent offline --check fails requesting canonical fragment-free URL not found in cache. That is a reproducibility/cache-identity limitation, not a version conflict and not proof the lock is invalid; the ordinary online --check subsequently succeeds without rewriting lock. Do not manufacture cache entries or hand-edit the lock to hide this mismatch. A fully prepared target cache/artifact set must be demonstrated before claiming offline install/check readiness.

No complete .whl files were found in this candidate's uv-cache inventory. UV may stream/extract wheel or obtain metadata while resolving; extracted wheel cache, successful resolution and a declared hash do not by themselves show a separately retained complete-wheel byte digest. No full-wheel hash verification receipt was found in reviewed inputs. The project explicitly labels this hash publisher evidence until complete local bytes are hashed. Therefore all-wheel integrity, artifact completeness and installed distribution inventory remain UNVERIFIED, not passed. Existing oss2/crcmod cached metadata is not target Linux build/install evidence.

## Controls for the bounded installation

1. Pin and record the actual disposable Linux CPython3.12 target/runtime image and verify architecture/glibc compatibility. Keep production/default GPU metadata and C source unchanged; use independent environment/cache/install outputs.
2. Use ordinary fixed-lock installer/download support with enforced lock hashes and provenance. Verify selected complete-wheel bytes against lock hashes (including Torch) or retain equivalently auditable installer full-artifact verification during installation. Do not claim all wheels verified from this metadata-only review. Demonstrate canonical-URL/offline cache readiness if offline install is required.
3. Explicitly handle sdist-only oss2==2.19.1 and crcmod==1.7. Resolver metadata guards allowed only existing verified metadata and prohibited new sdist execution; cached Windows metadata does not authorize or prove Linux compilation. The installation plan must explicitly isolate and record build requirements/toolchain and retain source-lock-hash verification plus build outputs/logs, or use verified compatible wheels. A blanket no-build install cannot install these two from current lock artifacts. Do not silently execute new build hooks or replace versions to bypass them.

After installation, independently compare actual installed runtime/dev names, versions, CPU Torch identity and sources against this graph, run applicable Python/native/security checks and Linux model/backend integration. Those are subsequent acceptance checks; none has been performed here. Full safety/SBOM/production approval remains separate. No extra user approval flow is introduced by this review; parent retains the task's existing authorization boundary.

## Evidence and ownership

Independent scripts: review.py and check_project_delta.py; actual host commands python <script> both exit0, logs and numeric exit files retained. receipt.json contains full active names/edges, platform environment interpretation, CPU Torch lock entry, input SHAs, root check result, offline failure and wheel verification flag. This is a machine-readable independent computation, not a copy of author's graph arithmetic.

Read-only author directory and C tree; no network, install, daemon/settings/default/test/source/lock changes. Only .tmp/linux-cpu-lock-independent-review-20261029 was written. No goal/Harness activation, commit/push/deploy or migration. Root owns final docs/memory integration.

Installation decision clarification: root may proceed with a disposable fixed-lock install that verifies selected artifact hashes as it reads them and records resulting identities. There is no demand for a second complete wheel copy solely for this review. Actual blockers are an artifact hash mismatch, unsupported target tag, lock mutation, unresolved/offline-required missing artifact, or an unplanned sdist build outside the isolated installation plan. Ordinary download/cache reuse and planned isolated oss2/crcmod builds need their genuine verification receipts; they are not reasons to alter package versions or the accepted graph. If these controls hold, there is no independent-review blocker to beginning the installation.
