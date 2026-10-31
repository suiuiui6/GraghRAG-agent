# Windows uv_loop_t layout diagnosis — 2026-10-29

Root cause established for the observed 464 → 472 difference: upstream Windows header version change, not a compiler/CRT layout difference required to explain the symptom. In official v1.40.0 include/uv/win.h:219, UV_MSAFD_PROVIDER_COUNT is 3; signed-source v1.53.0 same line is 4. The uv_loop_t private poll_peer_sockets array uses that count. AMD64 SOCKET is 8 bytes, so this adds exactly 8 bytes and moves every subsequent member. No candidate runtime, Torch, loop initialization, handles, callbacks, or Windows executable was run by this diagnosis.

## Direct evidence

One actually executed experiment compiled the same constant-only fixture with the same fixed x86_64-w64-mingw32-gcc-win32 compiler/image, changing only official header trees. Docker network none, read-only root/input, non-root 1000:1000, cap-drop ALL, no-new-privileges, memory512m, CPU1, pids64, 40s inner/50s outer timeout. Exit0 in run.json. No link/run; COFF .layout constants were dumped via objcopy and independently unpacked as little-endian 64-bit integers in layout.json. Objects, raw sections, objdump text and exact argv retained. Fixed image sha256:25bfa2429b8a0a91049e2e1de1b4fdd985922a25819c0ae716d02d5ec7415c87.

| property / offset | v1.40.0 | v1.53.0 |
|---|---:|---:|
| sizeof / alignof loop | 464 / 8 | 472 / 8 |
| sizeof SOCKET / mutex / async | 8 / 40 / 224 | 8 / 40 / 224 |
| poll_peer_sockets offset / size | 144 / 24 | 144 / 32 |
| active_tcp_streams | 168 | 176 |
| active_udp_streams | 172 | 180 |
| timer_counter | 176 | 184 |
| wq | 184 | 192 |
| wq_mutex | 200 | 208 |
| wq_async | 240 | 248 |

All enumerated loop member offsets before and including poll_peer_sockets stay equal. Queue representation void*[2] → struct uv__queue does not change these offsets. v1.40 fixture size matches actual old DLL public-size baseline464, while v1.53 fixture matches actual candidate472, with same MinGW compiler. Thus a version change alone reproduces the full measured delta. This does not prove all MSVC-vs-MinGW ABI details equal, nor establish the unknown wheel build headers.

src/win/poll.c has four real provider GUIDs, uses ARRAY_SIZE(uv_msafd_provider_ids) to find index, and indexes loop->poll_peer_sockets[index]. Hard-setting the count to3 would either conflict with initializers or invalidate required storage/indexing semantics; falsely returning464 from uv_loop_size cannot change writes or protect a consumer's 464-byte allocation. Allocation based on the old compiled sizeof can lose8 bytes at the tail, while direct accesses after the array use wrong offsets.

## Minimal viable routes

1. Recover exact original Torch wheel build/source/libuv header mapping and inspect how its loop storage is allocated; matching uv_version1.40.0 alone is insufficient provenance. If preserving that prebuilt consumer is required, start from its exact ABI-compatible source baseline and backport the required security fix in isolation, using a matching MSVC/UCRT toolchain where feasible. A backport requires its own design/security review and full consumer validation; none was attempted here.
2. If using unmodified1.53.0 is required, rebuild all consumers that embed/allocate/access uv_loop_t against the new headers, then validate matching compiler/CRT, offsets, signatures and actual consumer behavior. This is more invasive but avoids pretending the unchanged old consumer is compatible.
3. A switch to MSVC/UCRT may address an independent CRT/toolchain risk but does not remove the source-declared fourth SOCKET. It is not a standalone remedy for this size failure. A dynamic-allocation consumer might be adaptable only after exact source inspection; sizes of all handles matching does not establish that.

Current candidate stays blocked from Torch/production ABI acceptance. No unsupported-CRT conclusion is established by this layout experiment; CRT mismatch remains a separate unresolved gate.

## Trust, scope and failures

v1.53 include tree was read from the previously GPG-verified tar SHA cb0d6dd2128d5a95bd242c6cc982a24fe608fa93da57b6b4ec763b0018c53e64. Six v1.40 files fetched over HTTPS from exact official raw.githubusercontent.com/libuv/libuv/v1.40.0 paths; URLs/bytes/SHA retained in header-source.json. These old header contents were not signature-verified or proven to be the original wheel's inputs. Official-tag content is a reference counterfactual, not wheel provenance.

First bounded header fetch hit network sandbox10013; exact fetch succeeded after tool escalation. First Docker call failed pipe permission before any container ran; identical single experiment succeeded with tool escalation. failed-attempts.json preserves observed failures; successful run.json is authoritative final command/result. The wrapper exits0 while explicitly recording Docker exit; exit0 claim here uses actual recorded Docker exit0, not wrapper alone. Only the assigned .tmp directory was written. Root workspace was already dirty; no cleanup, candidate config change, source patch, commit/push, deployment or full upstream tests.
