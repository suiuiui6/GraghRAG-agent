# Independent Linux private CPU persistent-volume recreation acceptance

Result: PASS for the new three-container **service-level** recovery scenario. This is not a new HTTP end-to-end test. The prior complete HTTP lifecycle JUnit was independently parsed: 22 tests, zero failures/errors/skips. It was not rerun or counted as new coverage.

## Inputs and identity

Fixed image: `sha256:f4e637023bdc366728472bcaa271002d2d69ad6065c6bd6e7b706ed9c4d1df83`. Source and 11 BGE-small-zh-v1.5 files are read-only mounts of the staged inputs. All 259 recorded staged hashes independently reread without differences; relevant staged Python/native source hashes compared to their C source paths without differences. Four native source files plus build.py are independently bound in `outputs/native-source-identity.json`. All 158 installer artifact hashes matched artifact-map-all158.json. Installed distribution names normalized by PEP503: 158 unique exact versions, no duplicates, match image expected-packages; independent `python -m pip check` exit0. `outputs/runtime-identity.json` records actual runtime checks and root-owned nonwritable site-packages/native/model paths and their parents.

The staged Linux native manifest has approved=true solely for the separately reviewed private synthetic BUILD IDENTITY. No Linux Chroma semantics or production compatibility approval follows. Formal C/staged build.py still rejects Linux builds with `Linux release build and validation are not yet approved`. No source, model, gate, lock, production defaults or C files were modified.

## Independent new scenario: input → expected → actual

| Container | Input/actions | Expected | Actual |
|---|---|---|---|
| 1 | Allocate marker through genuine SyntheticStorageConfig.create; publish A-v1/B, embed/query both; publish A-v2 with explicit expected_revision=1 | revisions1/2; active A-v2 excludes v1; B intact | PASS; exact returned texts asserted, update active_revision2; exit0,21.4495161s |
| 2 | Fresh same-image container; same owned /fixtures mount; from_root authentic marker; fresh model+store+service | A-v2/B recover; done receipt and active revision2 survive; delete A | PASS; receipt done/revision2 asserted; delete status deleted/cleanup done; exit0,14.1925909s |
| 3 | Fresh same-image container; same volume and fresh model+store+service | A remains absent; B survives | PASS; get_active raises CatalogNotFound, A search empty, exact B text returned; exit0,12.4088035s |

Each phase uses production DocumentPublication publish/search/delete/catalog and VectorStore, actual hardened SQLite, actual pinned local 512-dimension model, no model or storage mock. Text assets are generated synthetic data. CatalogNotFound is a service result whose HTTP mapping is 404; no HTTP request was made by this new runner. No new authentication/docx/provider behavior is claimed; the separate prior HTTP22 provides that existing evidence. No JWT/token persisted. The control file contains only synthetic root/document IDs/profile fingerprint. No contextmanager exit deletes the root; all three phases use actual independently loaded services over the retained volume.

## Container evidence and reproducibility

`run.ps1` records full argv in each `outputs/phase-N-command.json`; `runner.py` is the complete new scenario. Exact actual IDs and inspect configuration are recorded by `receipt.json` and `outputs/container-restrictions-receipt.json`. Every scenario container has distinct ID, fixed image, uid65534, network none, read-only root, cap-drop ALL, no-new-privileges, cpus2,4GiB memory,pids128,1GiB/tmp tmpfs, cwd/source/backend, command timeout240. Source/model and runner remain RO with no writable ancestor alias. Only owned outputs/data/uploads/output are RW. Actual inspect, not intended command alone, was checked. All phase State.ExitCode=0 and OOMKilled=false. Separate fourth short runtime-identity check uses the same restrictions and does not constitute a fourth lifecycle phase.

Executed commands: `audit.ps1` exit0 (259 staged/158 artifacts/JUnit22); `run.ps1` exit0 (all three phase exits0); recorded runtime-command.json exit0; `finalize.ps1` exit0 (actual inspect limits/mounts/identities/native source). Per-phase stdout, inspect, command and exit receipts retained. Initial unprivileged Docker named-pipe access failed before container creation; subsequent authorized elevated execution succeeded. The initial failure text is retained in tool output and setup-failures.txt. No failures/assertions or existing tests were removed or weakened. No package installation or network operation performed. No git commit/push/deploy.

## Boundaries

PASS is scoped to private synthetic service recovery, complete pinned CPU image and tested document lifecycle. Formal Linux release build, Linux Chroma semantic admission, full application new HTTP e2e recovery, native security/SBOM, global coverage and production approval remain outside this acceptance. Existing fail-closed compatibility admission is unchanged. Parent owns integration into authoritative docs/memory; this reviewer only writes this owned scratch directory.

Additional independent cross-check: all158 artifact-map name/version pairs equal installed runtime pairs; previous HTTP actual image/exit/user/mounts captured in outputs/artifact-installed-and-prior-http-identity.json. The lock SHA recorded by artifact-map and patched scan receipt agrees (8a8ef5c4…); actual lock-path byte reread is pending parent handoff, so no independent actual-lock-file hash claim is made yet.

Actual lock identity CLOSED: independently read .tmp/langgraph-security-candidate-20261029/cpu-canonical/backend/uv.lock, SHA256 8a8ef5c4e9327e7f22529eec5f90ea204db3238d19948634da75e4954ed2f786 equals artifact map. outputs/actual-lock-identity.json records this. Earlier pending-path note is superseded. A preceding attempted binding to cpu/backend/uv.lock correctly failed because it is baseline d1434b9b, without writing successful evidence; the correct canonical patched file is independently checked.
