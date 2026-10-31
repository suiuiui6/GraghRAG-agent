# LangGraph security patch candidates — author report, 2026-10-29

Status: two real resolver-generated private patch candidates and checks completed. Independent review, patched SDK behavior, re-audit and final WindowsR11/full Linux acceptance remain NOT_RUN. This agent is the candidate author, not its independent reviewer. No formal source/default/lock/gate or previous artifact directory changed.

## Root cause and boundary

New actual audit-all157.json reports langgraph-sdk0.4.4 CVE-2026-118667 / GHSA-3fx2-cqw9-xr3c; it separately skips torch2.14.0+cpu because PyPI has no such version. Original audit and skip are retained, not filtered. The official GitHub advisory read on2026-10-29 is saved in advisory-web-response.json: https://github.com/advisories/GHSA-3fx2-cqw9-xr3c . It identifies SDK0.4.x below0.4.6 and LangGraph1.2.3 through1.2.13 using vulnerable SDK as affected; patches0.4.6/1.2.14. Advisory published to GitHub database/reviewed/updated Oct28, with original repository publication Oct7. Findings are authenticated same-server GET path redirection from raw identifiers; no write primitive is asserted.

Static AST inspection of the actually installed old SDK confirms four unquoted identifier call sites in async/sync get_tree and _fetch_state. candidate-diff.json records exact source files/hashes/method lines and excerpts. Production source searches across backend/integration/langextract (tests/venvs/research excluded) find no RemoteGraph/langgraph_sdk/pregel.remote usage. That does not dismiss package exposure or justify retaining vulnerable versions. Actual consumers include backend routes/query.py's create_agent/GraphRecursionError, backend agentic_rag_mvp.py create_agent, and integration agentic_rag_mvp.py StateGraph/create_agent. No provider/API/model execution happened here.

Hypothesis: pinning only LangGraph1.2.14 and SDK0.4.6 addresses the published dependency flaw without unrelated graph/source changes. Private resolver experiment initially froze every existing third-party version; final main metadata restores original flexible safety bounds plus only new security floor, rather than publishing179 incidental pins.

## Reviewable final candidates

main/backend/{pyproject.toml,uv.lock,requirements.txt}:
- LangGraph dependency floor>=1.2.14 in both dependency declarations.
- Existing seven safety constraint floors retained; add langgraph-sdk>=0.4.6 as a constraint, not a direct runtime dependency.
- Resolver lock181 records =179 third-party +editable LangExtract +virtual backend. Linux3.12.16 runtime/all closure152/177 includes local LangExtract; node names and active edges exactly equal old main graph.

cpu-canonical/backend/{pyproject.toml,uv.lock} plus adjacent langextract/pyproject.toml:
- Original CPU exact version constraints retained; only langgraph1.2.11->1.2.14 and sdk0.4.4->0.4.6 substitutions; direct LangGraph floor raised.
- CPU Torch PEP508 source URL removes only #sha256 fragment to use already captured canonical URL metadata. This is an explicit separate source-identity candidate, not silent removal of integrity controls. Original fragment candidate and failures remain in cpu/ and logs.
- Lock159 records =157 third-party +editable LangExtract +virtual backend. Linux runtime/all closure133/158 names/edges exactly equal old CPU graph.

For both locks, author checker requires exactly two version changes, zero node additions/removals, and complete equality of every other package record/source/artifact. Entire Torch record is unchanged in CPU lock: exact official cp312 manylinux_2_28_x86_64 URL, version2.14.0+cpu and sha256:a09987c95ec4cffdb6df798d3d641558110a334cfccce22f2f046d83142bc260. Before any install, assert this publisher-hash clamp again and use require-hashes; never accept arbitrary newly resolved Torch hash. No lock node or report was hand-edited.

Artifact SHA256:
- main/backend/pyproject.toml dad9964abed69b6dc64394f5abaf166a8a48672397185187aee5ec76725e5bb5
- main/backend/uv.lock ed3d04e415f6e42480ec69d4eaab56b56f783b7b713264d71795f372d2e8e0a5
- cpu-canonical/backend/pyproject.toml c1cae69d7690f5ec5776465bc8c33dc4f5a6d5c303494a44523a964f3c8d37ef
- cpu-canonical/backend/uv.lock 8a8ef5c4e9327e7f22529eec5f90ea204db3238d19948634da75e4954ed2f786
- Requirements and full original-source before/after SHAs are in candidate-diff.json; requirements bytes differ only in the LangGraph floor line. All copied LangExtract metadata remains byte-identical.

## Actual resolver evidence and failures retained

All work uses private copied metadata/cache under this owned directory, uv binary SHA in inputs-before.json, normal official PyPI/TLS, Windows CPython3.12.8 resolver, no environment installation. One original overall180second network deadline, no new network retries after CPU download was interrupted. Initial main --no-build global fails exit1 because oss2 has no wheel; seed unchanged. Corrected per-package guards forbid every unknown source build, permitting only already reviewed oss2/crcmod cached metadata and static LangExtract. Main network resolver r1 exit0/7.21seconds updates exactly two versions; logs show no source build. Then final minimal main metadata re-resolution --offline exit0/4.27seconds and --check exit0/0.06seconds.

CPU fragment resolver unexpectedly requested the full187.2MiB Torch because metadata cache referenced missing archive targets. This exceeded small-metadata candidate scope; own UV+wrapper processes were stopped. First restricted process-inspection attempt was denied; elevated targeted stop succeeded. Raw stderr/partial private output and original candidate are retained. No complete Torch wheel/hash is claimed from this interrupted request. No further network operation was made.

A normal existing archive copy/hash was then started unnecessarily; it was canceled and partial private copies are not verification evidence. Restoring original wheels-v6 metadata bytes and introducing separate canonical-source candidate allowed normal offline resolver exit0/0.51seconds and --check exit0/0.05seconds. This canonical candidate is submitted for independent review; old fragment URL remains reproducibly blocked and is not labeled passed. Cached metadata was copied byte-for-byte, never manufactured. Formal old CPU directory/cache unchanged.

Commands/argv/env/start/exit/before-after lock SHA are retained in *command.json/*result.json and stdout/stderr. verify_candidates.py and final_graphs.py exit0 check full package-record/graph/source identities. Initial checker assumed registry lock records expose metadata.requires-dist and failed; retained log, corrected only to actual dependency graph schema and reran. Early optional search command had incorrect arg index; final source searches saved separately with exact argv/results. No failed process is counted as a passing test.

## Required behavior and final verification plan

1. Acquire/hash actual patched0.4.6 and1.2.14 official artifacts; record wheel metadata requiring SDK>=0.4.6. Re-audit all affected main/CPU distributions from new locks; retain original audit and Torch skip. Root separately supplied exactCPU2.14.0+cpu and public2.14.0 OSV supplementary reports, each one package/0vuln/0skip; those do not rewrite the original skip or establish native-library closure safety.
2. Run test_sdk_four_sites.py in a bounded new patched environment: actual synchronous/asynchronous SDK get_tree and _fetch_state methods, seven identifier cases each (normal UUID, relative/query text, single/double dot, slash, percent and Unicode), explicit expected encoded segment via existing helper, authentication retained, HTTP normalization/raw query checks. Use an in-memory capturing HTTP transport only; no real authenticated service or network. Extend assertions so query remains inert and encoded raw path stays scoped. Baseline reproduction should expose old0.4.4 unencoded paths; patched0.4.6 must have zero mismatches. Existing optional baseline invocation was canceled before a result; this probe is NOT_RUN, not a test pass. Static four-site proof is separate.
3. Production LangGraph consumer regression: exercise route query create_agent construction, graph invocation/stream/tool cycle, recursion/error handling and session/source-isolation routes with real installed patched LangGraph/SDK. Run existing effective HTTP/model tests, preserving provider isolation and all prior assertions; integration StateGraph/create_agent entry checked according to current test strategy.
4. After independent review and guarded publication of all three main files, synchronize isolated Windows environment to final lock, verify installed identities, then rerun complete final snapshot WindowsR11 with all first-party coverage range and separate integer line/branch90; retain raw files/logs/hashes/exit. Old R10 cannot certify new dependency snapshot. Re-run applicable security/native and complete Linux CPU install/model/backend validation on accepted patched CPU profile. This task did not clear any production gate.

Next owner: root requests new-context independent review of main and cpu-canonical, actual patch behavior and candidate graph/clamp semantics. Only then decide formal guarded copy; no commit/push/deploy/migration by this task. Parent owns docs/memory updates. No goal/Harness operation.
