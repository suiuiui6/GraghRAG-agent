# Minimal Linux CPU installation preflight — 2026-10-29

Scope: private CPU candidate only. No installation, new source build hook, network request, formal GPU/default change or compatibility approval occurred. Root retains docs/memory ownership.

## Confirmed inputs

- CPU uv.lock SHA256 d1434b9b8b46f3d9c061098e15ddaada44e8d0a2d3dfb55d4db4c425a8f60b36, independent graph review PASS; runtime133/all158 retained.
- Existing runtime sha256:ca19e0667a83656165ad4c7edd07ef50b97429fa7aa5932453dac1dc4c16ebe1: actual network-none/read-only probe exit0, x86_64, glibc2.36, Python3.12.16, venv module present. This supports manylinux_2_28 CPU Torch target compatibility, not successful wheel import.
- Existing builder sha256:cd48c100f4e8c0297c2e1a558b7a93d95e41f79ba4f58d5f7d938a71192dff23: actual read-only probe exit0 GCC12.2.0, ld/ar present, Python.h present. Initial probe exit1 because make absent; no compile attempted. setuptools extension builds ordinarily invoke compiler directly, so do not install make merely to satisfy that probe.
- Rehashed all 32 existing deb archives against builder-packages.lock.json: all size/SHA match. Lock provenance snapshot20261020T213255Z; historical transport used bounded mirror acquisition verified by SHA, not immutable current mirror content. Reuse built image; no APT needed.
- Rehashed 49 local LangExtract copied files: all match source manifest; copy these exact files into owned execution scratch, mount input read-only. Its pyproject build-system requires setuptools>=67.0.0 and wheel.

## Two planned sdist builds

oss2 2.19.1 lock archive SHA a8ab9ee7eb99e88a7e1382edc6ea641d219d585a7e074e3776e9dec9473e59c1 (298845 bytes). Existing extracted setup.py statically reads local version/README, imports setuptools with distutils fallback, declares runtime dependencies, no setup_requires. Cache extraction is not proof of archive integrity: acquire/archive-hash-check before executing. setup.cfg only egg_info tags.

crcmod1.7 archive SHA dc7051a0db5f2bd48665a990d3ec1cc305a466a77358ca4492826f41f283601e (89670 bytes). Only metadata cache located in inspected new/old CPU caches; no source setup inspected. Next necessary action: obtain exact locked tar, verify bytes/SHA, safely list/read setup.py, setup.cfg, pyproject.toml if present, C source and imports WITHOUT executing. Check optional-extension fallback: build success alone must not imply native extension compiled. Do not run metadata/build hooks before this source check.

Builder Python requirements: propose setuptools==84.1.0 (already exact runtime lock) plus an explicitly selected wheel artifact version/hash. wheel is not currently locked by this preflight, so exact pin/artifact hash must be recorded during bounded acquisition before builds. Determine any extra dynamic requirement from verified source only; do not assume Windows metadata proves Linux build success. LangExtract reuses same pinned setuptools/wheel if verified source permits.

## Minimal next execution sequence

1. Root independently reviews this preflight; start with exact crcmod archive and oss2 archive acquisition/hash checks plus static source review. Network budget: at most 2 source archives, 388515 bytes total payload; 1 attempt + at most 1 retry per URL, 180s per attempt. Existing full-wheel redownload is not a prerequisite.
2. Select exact wheel build-tool version; acquire setuptools84.1.0/wheel wheels with explicit hash receipts (maximum 2 build-tool wheel artifacts, no unconstrained installation). Stop on mismatches or extra undeclared source requirements and adjust only build plan.
3. Build in disposable pinned builder container, --network none --read-only --cap-drop ALL --security-opt no-new-privileges, read-only source/tool mounts and owned writable /work + bounded /tmp. Create /work/build-venv; install only hash-pinned build tools offline. Build oss2/crcmod with no-deps/no-build-isolation using this separately isolated venv. Record commands, exit codes, source hash, tool versions, wheel SHA/tags, build log and crcmod native-extension result. No apt install, no original image mutation.
4. Runtime container uses pinned runtime image and separate /work/runtime-venv WITHOUT system-site-packages. Install selected Linux CPython312 artifacts from accepted lock with enforced hashes, runtime133 or all158 as explicit scope; for locally built wheels enforce newly recorded SHA plus source/build linkage. Avoid uv lock re-resolution. All newly fetched lock artifacts verify actual SHA as read; bounded per-artifact retries; stop unsupported tag/hash mismatch/unplanned sdist. Retain selected artifact URL/expected+actual SHA receipts. Full-wheel duplicate inventory is unnecessary.
5. Copy verified49 LangExtract inputs to owned scratch and build/install offline with no dependency resolution and pinned build tools. Fixed11 model manifest is referenced by .tmp/vector-backend-runtime-20261020/model-encode-receipt.json; root binds exact revision7999e1d3359715c523056ef9478215996d62a620 and mounts model files read-only. Set HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE, local_files_only=True, trust_remote_code=False/use_safetensors=True. Actual acceptance must load CPU Torch, execute tensor computation and real encode then project chain; this preflight proves none of those results.

No install-success/security/production-admission claim is made. Original runtime image/default/GPU lock/compatibility_not_approved stay unchanged. No goal/Harness/git operations.
