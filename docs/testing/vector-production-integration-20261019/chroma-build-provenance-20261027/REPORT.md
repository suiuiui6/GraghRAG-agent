# Original Chroma 1.5.9 build provenance investigation — 2026-10-27

Conclusion: the original Windows wheel is now cryptographically tied to the advertised source commit and official release workflow. A conservative, complete audit of **declared serde_json feature activation in that original lock graph** found no request for `float_roundtrip`, `arbitrary_precision`, or `unbounded_depth`. This is materially stronger evidence than the candidate helper's feature tree or a finite differential corpus. It supplies a source/build configuration argument for independent review. It is **not** a captured original rustc invocation, reproducible wheel build, or independent authority to open the production gate.

Only this D-drive scratch directory was written. No Chroma library was imported or executed; no C worktree, contract, gate, dependency environment, data, Git index, commit, push or deployment was changed.

## What was already present and reused

`../chroma-build-provenance-20261026/` already contained actual PyPI JSON, the 23,542,454-byte Windows wheel, the sdist, official fixed-source workflow/pyproject/manifests/tree, API response headers, and a nonempty GitHub attestation bundle. These were inspected before fetching any more artifacts. No wheel or sdist was downloaded again.

The exact Windows wheel is `chromadb-1.5.9-cp39-abi3-win_amd64.whl`, SHA256 `4fd0b560e56761b7f3cb4d5c6205fd5f20814484b4a3e4e9af9038c2b428fc6c`. Both existing wheel and sdist hashes match the existing official [PyPI version JSON](https://pypi.org/pypi/chromadb/1.5.9/json). The sdist `Cargo.lock` bytes hash to original Git blob `d8351f18c1bff4c89df1b77b66ab5980ace246a7`; this is the original source lock, not a replacement helper lock.

## Actually verified in this investigation

1. **Attestation signature, subject and source binding.** `gh attestation verify` exited **0** using the existing local bundle and actual wheel. It enforced repository `chroma-core/chroma`, signer workflow `_build_release_pypi.yml`, source digest `11f3c7435e71024aa0a2b53710a28d3289d922d1`, and `refs/tags/1.5.9`. The retained verification result contains a verified Rekor timestamp, certificate identity from `https://token.actions.githubusercontent.com`, exact wheel subject digest, signer/source commit, source ref and run `25357632446/attempts/2`. The independent local verifier additionally asserts the exact certificate SAN and issuer. Files: `gh-verification-network.json`, `decoded-attestation.json`, `bundle.json`, `evidence-verification.json`.

2. **Advertised release command/configuration.** Original fixed-commit [release workflow](https://github.com/chroma-core/chroma/blob/11f3c7435e71024aa0a2b53710a28d3289d922d1/.github/workflows/_build_release_pypi.yml) builds the Windows x64 wheel through `PyO3/maturin-action@v1`, with `--release --out dist`; `--zig` is Linux-only. [Original pyproject](https://github.com/chroma-core/chroma/blob/11f3c7435e71024aa0a2b53710a28d3289d922d1/pyproject.toml) selects `rust/python_bindings/Cargo.toml` and only `pyo3/extension-module`. It does not select parser features, all-features or rustc feature cfg arguments. The fixed-commit Rust composite action was also obtained and inspected: toolchain setup, protoc/cache/nextest, no parser feature arguments. Original tree has no repository `.cargo/config*` entry. These are statements about the declared configuration; see limitations below.

3. **All original workspace manifests, not the sdist's rewritten subset.** Original Git tree has **37 Cargo.toml files**. Of 30 manifests in the sdist, 23 already have identical original Git blob hashes; seven were rewritten by sdist generation and seven original manifests were absent. Existing root Cargo.toml plus 13 newly fetched fixed Git blobs complete all 37. Every final file matches its original Git blob identity. None contains any of the three parser-changing feature names. `sdist-original-manifest-comparison.json` deliberately records the differences; they were not silently treated as original manifests. `original-workspace-results.json` binds all final manifests.

4. **Complete direct consumers of serde_json in original Cargo.lock.** There is a single locked serde_json version, **1.0.149**, checksum `83fc039473c5595ace860d8c4fafa220ff474b3fc6bfdb4293327f1a37e94d86`. Its **51 direct consumers** consist of:
   - **30 registry package/version entries**: each obtained from the official `rust-lang/crates.io-index` GitHub repository; each exact version's crate checksum matches original Cargo.lock. All dependency declarations and feature tables (`features` and `features2`, including disabled/dev/build/platform possibilities) contain no `float_roundtrip`, `arbitrary_precision` or `unbounded_depth` request. The union of explicit serde_json dependency feature requests is `alloc`, `preserve_order`, `raw_value`, `std`.
   - **20 local packages**: all package names are accounted for in the 37 original source manifests above.
   - **One Git package**, `gcloud-auth 1.3.0`, from original locked commit `bd8ec9581e00034363befe7d38146084df018876` in `yoshidan/google-cloud-rust`. Both its root and `foundation/auth/Cargo.toml` fixed Git blobs were fetched and hash checked. Auth declares `serde_json = { version = "1.0" }`; neither manifest requests the three features.

5. **serde_json's own defaults are checked too.** The previously preserved actual `serde_json-1.0.149.crate` has the exact original lock checksum. Its Cargo.toml declares default `std`; `preserve_order` adds `indexmap` and `std`; the other mentioned features do not imply the three parser-changing features. See `serde-json-default-features.json` and the extracted manifest.

This is a conservative upper-bound argument: even including every direct consumer in the original lock, irrespective of whether that dependency participates in the Windows wheel, no declared dependency/forwarding feature activates the three options. Removing inactive dependencies cannot introduce a missing feature into the union. [Cargo's documented feature unification](https://doc.rust-lang.org/cargo/reference/features.html#feature-unification) and [maturin's documented feature/configuration options](https://www.maturin.rs/config.html) support that reasoning. It avoids pretending a helper graph is the original graph, and does not need a universal finite-input enumeration. It should be assessed alongside the prior scalar algorithm identity review, not replace it.

## Exact verification commands and results

Executed from `D:/graghRAG-agent`:

```powershell
gh attestation verify .tmp/chroma-build-provenance-20261026/chromadb-1.5.9-cp39-abi3-win_amd64.whl --repo chroma-core/chroma --bundle .tmp/chroma-build-provenance-20261027/bundle.json --signer-workflow chroma-core/chroma/.github/workflows/_build_release_pypi.yml --source-digest 11f3c7435e71024aa0a2b53710a28d3289d922d1 --source-ref refs/tags/1.5.9 --format json
.tmp/runtime-lock-20261022/.venv/Scripts/python.exe -B .tmp/chroma-build-provenance-20261027/check_index_features.py
.tmp/runtime-lock-20261022/.venv/Scripts/python.exe -B .tmp/chroma-build-provenance-20261027/check_original_workspace.py
.tmp/runtime-lock-20261022/.venv/Scripts/python.exe -B .tmp/chroma-build-provenance-20261027/verify_evidence.py
```

All four final commands exited **0**. Last command checks actual stored artifact hashes, verified certificate/subject/source fields, all 51 consumers, 30 exact registry checksums and all 37 original manifest hashes, and writes machine-readable `evidence-verification.json` with an input SHA256 inventory. It verifies the collected evidence's consistency; it does not independently reimplement Sigstore signature verification.

## Failures, unavailable evidence and precise limitations

- Initial sandboxed gh verification exited **1** because no valid Sigstore verifier initialized. Authorized read-only network retry succeeded; both outputs remain. This is not an unresolved signature failure.
- Downloading 30 crates from `static.crates.io` timed out on connections (curl **28**); none was successfully treated as a verified archive. The official GitHub index exact-version/checksum route succeeded instead. Index metadata authenticates the published declared dependency/feature information, not freshly downloaded byte-for-byte third-party manifests. The source archive for serde_json itself was already available and checksum verified.
- Original run artifacts API returned HTTP **200**, `total_count: 0`; original attempt logs API returned HTTP **403**, `Must have admin rights to Repository`. Do not claim logs expired, hidden environment verified, or no logs exist: they are unavailable through this access path. A first Rust action filename guess `action.yml` returned **404**; original tree located `action.yaml`, whose fixed blob was then obtained successfully.
- The GitHub provenance attestation is generated by the release job over downloaded build artifacts. It binds the release subject and source/workflow identity; it does **not** enumerate the build job's Cargo features, exact maturin/action versions, rustc command, compiler hash or environment. The workflow uses floating action refs, a self-hosted runner and no explicit `--locked`. Hidden runner modifications, unrecorded global cfg flags or a build that changed its lock are not disproved by this static audit. Such limits are normal trust assumptions of this declared workflow/source argument and must be explicit in the independent admission review.
- No complete reproducible build, actual original binary feature extraction, original executable execution, all-domain random proof, or native dependency safety audit was performed. Current dependency advisories, full adapter contract, numeric extraction beyond the reviewed builtin-scalar domain, Linux approval, coverage and production lifecycle remain separate gates.

## Recommended decision boundary

Submit this evidence to the independent formatter reviewer as the requested **source/build configuration argument**. The missing original feature premise now has substantive original-source evidence and a verified artifact/source attestation; it should not be described as simply "unknown because only the helper tree exists."

If the reviewer accepts ordinary trust in the signed official workflow's execution of its advertised original source/lock/configuration, it can decide whether the scalar parser-feature premise is closed without changing the compatibility reference. The parent must then amend only the affected authoritative contract clauses and perform required final-snapshot verification before considering any activation.

If the acceptance requirement instead demands captured original rustc invocations or cryptographically attested resolved dependency features, that evidence remains unavailable here. Keep admission pending. The minimum product choice then is explicit consent to define compatibility against **pinned Chroma 1.5.9 source/default-parser semantics** with the precise supported builtin scalar domain and already accepted differences, instead of promising every opaque historical wheel behavior. This investigator has not made that product choice and has not opened any gate.
