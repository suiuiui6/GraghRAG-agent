# Independent LangGraph patch review — 2026-10-29

Scope: private main and cpu-canonical candidates. Static/targeted SDK behavior review passes; commit, push, full acceptance and deployment are NOT approved by this report. No author/source/official lock or default was changed. Parent owns normative documentation and memory updates.

## Independently recomputed

`python review.py` exit 0. `receipt.json` binds reviewed files by SHA256. main has 181 records: 179 third-party, one editable LangExtract and one virtual backend. A count of 180 excludes virtual backend and must not be described as 180 third-party. CPU has 159 records, 157 third-party plus the same two local nodes.

Exactly two third-party records change: langgraph 1.2.11→1.2.14 and langgraph-sdk 0.4.4→0.4.6. The virtual backend metadata also changes, so “only two full records changed” would be inaccurate. Every other complete record, every source and all dependency edges compare equal. Original safety constraint list remains intact, plus SDK minimum on main; CPU exact constraints change only these two versions. requirements bytes change solely `langgraph>=1.0.0` to `langgraph>=1.2.14`. Original source metadata/locks retain their recorded hashes.

CPU canonicalization removes only the PEP508 Torch URL hash fragment. Complete Torch lock record remains identical: version 2.14.0+cpu; URL `https://download-r2.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl`; sha256 a09987c95ec4cffdb6df798d3d641558110a334cfccce22f2f046d83142bc260. Require-hashes installation and this publisher hash clamp remain mandatory. It is a separate private CPU source-identity candidate, not a main/default/GPU change.

Author resolve/check command/result JSONs were inspected: both profiles exit 0 and final after-lock hashes equal reviewed locks; check before/after hashes match. These are inspected actual process receipts, not independent resolver reruns. Original fragment download interruption and partial evidence remain, and are not passing installation evidence. Canonical preparation copies existing wheels-v6 metadata with shutil.copytree and uses real offline uv; no lock-record or cache metadata fabrication is shown in those scripts. Actual distribution integrity still requires the installation/scan gates below.

## Independent real SDK behavior

Own `behavior.py`, existing locked Windows runtime, direct import from SHA-bound official SDK wheel via zip sys.path overlay. No installation, external service, model, real authentication or network. Calls actual sync/async get_tree and _fetch_state with an in-memory immediate-return HTTP fixture; httpx.Request independently normalizes each URL. Expected segment strings are literal test vectors, not calls to the patched helper. Eleven identities × four sites = 44 cases per version, covering ordinary ID, traversal plus query, single/double-dot, slash, existing percent encoding, Unicode, fragment, query, backslash and space. Synthetic authorization presence retained.

Patched 0.4.6 wheel SHA256 57122b02bda41d37a97a5e09eb018aa8c9b3dc85c433880073779bd9324b7eea: exit 0, 44/44 scoped raw paths and inert queries. Baseline 0.4.4 wheel SHA256 39afe416c91742925e6f8a93715f566d499b36e1b636b804a4ffe3190e4f4e64: exit 0 under expected-vulnerable assertions, 40/44 encoding mismatches and traversal/query escape reproduced. Full rows in behavior-patched.json/behavior-baseline.json.

Initial two attempts were stopped with exit 1 without results. Diagnostic bounded retry shows imports succeed, then asyncio.run stalls in Windows socket._fallback_socketpair.accept while creating the event loop; stack-only evidence retained in diagnostic-patched.log. Its fixed 60-second timeout exited 1. Intermediate direct no-I/O coroutine execution passed but was superseded by final original asyncio.run probes run with require_escalated permissions: patched exit 0 in 1.93s, baseline exit 0 in 2.10s, each 44 cases. These cover actual event-loop execution, not fresh-install or real-server integration. Derived rows retain authorization only as a boolean. Author NOT_RUN probe is not counted as a pass.

Independent author evidence-manifest verification checked all 90 hashes with zero mismatches (exit 0).

## Publication decision and blockers

Main's three files are a bounded acceptable patch candidate for guarded copy, followed by final acceptance; CPU's two files remain private and must not change default/GPU behavior. No security exception is granted.

Before commit/push: verify copied final hashes and installed dependency identities; actual full Windows R11 against that final snapshot with separate integer full-production line/branch ≥90% and every prescribed suite; applicable consumers/agent invocation/stream/tool cycle/error and source-session isolation regressions; new-lock distribution vulnerability scans and relevant native evidence; full Linux CPU require-hashes install plus real model/backend acceptance; final independent review of evidence, source stability, and staged secret check. Old R10 or baseline scan cannot certify these updated dependencies. No full acceptance/coverage/security scan is executed by this reviewer. Existing Torch skip and supplementary OSV evidence remain separate, and cannot imply all native dependencies are safe.

No blocking defect was found in the reviewed bounded patch itself. Unexecuted acceptance gates remain release blockers.
