# Exact Torch consumer / old libuv header mapping

The installed version.py is read as text only: 2.14.0+cpu, git08187d9e0fba026dc8217405802ab5381dc88d90, cudaNone. Exact official commit TCPStore consumer was found at torch/csrc/distributed/c10d/store/TCPStoreLibUvBackend.cpp (the older location returned404). Source SHA c7e4dddb05699ee8145a8c03805604ea59f8610f50d052ce136125361687a12e.

## Storage is embedded, not dynamically sized

- line19 includes uv.h under TORCH_USE_LIBUV.
- line706: `uv_loop_t loop_{};` is a by-value private class member.
- line707: `c10::intrusive_ptr<UvTcpServer> tcpServer_;` follows it.
- line1289 passes `&loop_` to uv_loop_init;1292 passes it to uv_async_init.
- line1633 uses make_unique<LibUVStoreDaemon>, so compiled C++ class layout determines storage.
- No uv_loop_size call occurs anywhere in this source file. A replacement DLL returning its own new size cannot resize this embedded member.

## Official Windows build dependency resolved to the exact original DLL bytes

Same-commit `.ci/pytorch/windows/build_install_deps.py`:58 specifies https://s3.amazonaws.com/ossci-windows/libuv-1.40.0-h8ffe710_0.tar.bz2. Lines86-105 extract it into python_prefix and return python_prefix/Library;130-133 call that function and export libuv_ROOT. Same-commit build_wheel.py describes this as its dependency setup. This is official build intent, not a retained execution log for this particular wheel.

Exactly one dependency archive fetched,337434bytes, SHA e22158feea790e9c4e9f14a3dd85d9fdba8dcdc9b4a7b998e6adadfe8dee3865, ordinary HTTPS verification, no installation or execution. Its Library/bin/uv.dll SHA fa569e682fc5fb7a8eb94c6829af9f30a569748dbbc6bce39735d48bc960bcf8 is byte-identical to the installed original DLL (fresh read-only hash in binding-receipt.json).

Its Library/include/uv/win.h SHA7f378fa6d8fce51b4999344818731b40b7cac7a3d84d9ba60a9629dfece2ebab and uv.h SHA253cfea345971c78dbb15853fe0c1df960bbef6af8eeb78c85525bc9ff1553bf equal the official1.40 tag headers used in the prior constant experiment. Its win.h:219 has UV_MSAFD_PROVIDER_COUNT3. Package recipe metadata says libuv1.40.0/h8ffe710_0, VS2017/VC14.1, upstream1.40 source with an MSVC install-layout patch; those metadata claims are not independently reproduced compiler provenance.

Thus original DLL identity, same-archive headers, exact Torch source commit and official dependency URL form a strong concrete mapping to the old464-byte embedded layout. This is stronger than inference from uv_version alone. The official script has no embedded archive hash, S3 content can change, and no wheel-specific build attestation/PDB or compiler include trace was recovered. The last exact-binary-to-compiled-header attestation remains unproven; it must not be phrased as cryptographic proof of every wheel input. CMake location guesses returned404 and fetched CMake files did not close actual include-resolution execution; no more search was pursued.

## Compatibility decision

For the recovered exact consumer source built with its official dependency headers, unmodified1.53 is concretely incompatible: the consumer embeds464 bytes, while candidate fields require472. Old wq_async occupies240..463; new occupies248..471. In candidate Windows uv_loop_init (core.c:294), uv_async_init initializes the embedded wq_async. Candidate async.c assigns handle->pending=0 and async_cb. Their declared suffix is uv_req_t async_req, uv_async_cb async_cb, int pending (win.h:571-574). With the already measured handle96/req112/pointer8 layout, pending is at async offset216, hence loop-relative464: the first four bytes past the old loop member. This is a source/layout inference, not an observed crash or a new offset compilation. The class next member is tcpServer_; exact outer class offsets were not compiled.

Therefore this candidate must remain blocked from the old Torch LibUVStoreDaemon smoke/load path. The residual wheel attestation gap does not justify testing a source-proven incompatible layout in the old process. No claim is made that a live memory corruption was executed.

## Minimum next route

Preserve this prebuilt Torch consumer: evaluate a reviewed security-fix backport on the exact old ABI source/header baseline and matching MSVC/UCRT environment. Source changes must retain semantic correctness and all offsets, not simply force provider count3 on new source. Security sufficiency of a backport is still a design task, not approved or implemented here.

Use unmodified1.53: rebuild Torch consumers against new headers with consistent compiler/CRT, then validate actual TCPStore operation. Switching only the DLL toolchain toMSVC/UCRT cannot remove the fourth source-declared SOCKET. Dynamic loop allocation would require changing/rebuilding the consumer and is not offered as a binary-only fix.

## Execution and boundaries

Only this new torch-header-mapping directory was written. All40 parent-sealed files were freshly checked against their existing manifest, all true. No parent manifest was regenerated. Official bounded queries and404 failures remain in fetch.json/list-fetch.json/fetch2.json/fetch3.json; one archive in package-fetch.json. Source paths/API listings downloaded only, no remote code ran. No DLL load, Torch import/run, compiler, environment install, source patch, fork, commit/push or runtime replacement. Total fetch interval stayed within the authorized five-minute bound. Independent source pointers are the exact URLs retained in those receipts.
