# Actual Rust bridge source coverage — 2026-10-28

Result: isolated same-source diagnostic Rust/LLVM source line and branch metrics pass dual90 with all61 prescribed/added bounded contract cases passing explicit expectations and release differential checks. This is NOT production admission, release binary coverage identity, MC/DC, exhaustive control-flow coverage, Python acceptance or Linux model/backend deployment acceptance.

| Corpus | Unique physical DA lines | LLVM function/closure line instances | Raw branch outcomes | Integer gate |
|---|---:|---:|---:|---|
| Original30 author +19 independent |58/60 (96.6666666667%)|60/62 (96.7741935484%)|21/24 (87.5%)|Branch FAIL, retained|
| Final original49 +12 finite contract cases |59/60 (98.3333333333%)|61/62 (98.3870967742%)|23/24 (95.8333333333%)|Both line metrics + branch PASS|

No denominator reduction: line62 and branch24 remain unchanged. Unique physical first-party line statistics59/60 are reported alongside the unchanged62 instance metric; independent review will confirm the adopted source-line interpretation. Integer checks `59*10 >= 60*9`, `61*10 >= 62*9` and `23*10 >= 24*9`, both denominators nonzero. Complete unfiltered LLVM exports include dependencies; only exactly inventoried first-party `/source/src/main.rs` contributes the bridge gate. Dependency coverage is not pooled into first-party results. Branch count independently recalculated from every raw first-party branch true/false counter and LCOV BRDA:12positions×2 outcomes=24,23 nonzero. Raw JSON, LCOV, human report and source-annotated show are retained for both corpora.

## Measurement identity and scope

Read independent conditional strategy REPORT SHA00d17a600463487174fff56cea0efe25c64ed3aac3d1b9a2ded5495580da03f4. New owned directory only; no C production/source/lock/toolchain/runtime/approval/default-device changes; previous runtime/bridge/CPU/capability evidence remains readonly. Formal production gate stays closed. No install/publish/commit/deploy performed.

Fresh `rg --files backend -g *.rs -g !target/**` read-only inventory found exactly one production Rust source, main.rs. No source omitted or filtered for difficulty. All four C inputs were read and copied byte-exact to this isolated source, then independently rehashed after execution:

| Input | SHA256 |
|---|---|
|src/main.rs|eee79631cc3e7ee8acd2d48485be9a811374d7d04426a49f1368e7b260f65dfe|
|Cargo.toml|02105d1df940431d92ff91bb536eb65aee8e2ba3a7fc19f21e9e0ee624842c2c|
|Cargo.lock|4029ef11d930d910cf4e403134d8f0ade519c144b43eee54fc7ee93cbd880018|
|rust-toolchain.toml|4cb550734bd94d0591c8a84b561c654dd58ddc3b0d67464c2ddeb2962a4cd826|

Existing11 crate archives match every Cargo.lock package checksum. Every447 vendor source file matches `.cargo-checksum.json`; files also compared to original crate archive bytes with only git metadata omission allowed. No download/resolution/feature/serde changes. Vendor files reverified after measurement. Six actually resolved metadata nodes/features match the old release metadata exactly. Every built first-party/dependency fingerprint has same target/profile/features as original release; new rustflags alone differ. Actual features serde_json[std], serde_core[std] in build fingerprints, zmij[], memchr[alloc,std], itoa[], root[]. Metadata may include serde_core[result,std]; record real tool outputs, not a named zmij default feature invented from requested labels.

Fixed image `rust@sha256:a86cada82e36ebd7a9bffed7548792c55a952fdb20718eea9278a936bcb76e62`, rustc1.94.0 commit4a4ef493e3a1488c6e321570238084b38948f6db, LLVM21.1.8. Same GNU targetx86_64-unknown-linux-gnu, edition2021, Cargo release optimized profile. Actual offline locked release command, exact argv/env/mounts/UTC start in `build-container.command.json`; child argv/start/end/exit files and stderr retained. Build25.42seconds exit0. Source/vendor mounts readonly; new CARGO_HOME and target directory private; networknone,CPU1,memory512m.

Only diagnostic additions: `RUSTC_BOOTSTRAP=1`, `RUSTFLAGS=-C instrument-coverage -Zcoverage-options=branch`. No opt-level0, feature mutation, link-dead-code flag or normal release flag/toolchain mutation. This disclosed unstable override is accepted only for this private source-coverage diagnostic strategy; stable direct -Z is unsupported as separately proven. Instrumentation is a different executable:

- Existing release reference SHA20d2166cd218fdd0dff2914939c07e400fa38231f06139b91689ee45279418d0, remains unchanged.
- Diagnostic SHA19f638b1ed0595121a67e272be46b72fec0202a646c56df142bdc707d7c14666.

Private matched tools from frozen capability directory are readonly, official archive SHA cf6b8e1d3e48ffa4db37aa59f55382b991f0d347d9b62eebc9ef1d80dffabef4 rechecked. All extracted member SHAs rechecked. llvm-cov SHA48a327856ee93a645e7efe2ace064a9412d0f42875d9d1b5f124d1939a9e48cb, llvm-profdata SHAb7adef7cb04378425962ecdfb10b0cea02bb7cf44e1b05d5be01f64b2d221744, adjacent186846192byte libLLVM SHAbfa77bb35e70585603f775f9cd3868194f691e86986f3c13b1ef5ba08373014b. Exact llvm tools version outputs retained. No compiler/tools installed into existing image.

## Behavior corpus and raw execution

49 original requests/explicit expected outputs extracted from author `cli-mvp-receipt.json` and independent `partial-cases.json`, including duplicate scenarios as separate prescribed cases. Fresh release+instrumented122 total child processes for61cases; every child timeout3seconds, explicit input bytes, expected stdout/stderr/exit/predicate, actual bytes, argv/env/UTCstart/elapsed/exit retained. Each instrumented process has its own actual nonempty profraw;61total, no overwritten identity or missing abnormal-exit raw.

Run image fixed `sha256:ca19e0667a83656165ad4c7edd07ef50b97429fa7aa5932453dac1dc4c16ebe1`, uid65534, read-onlyroot, networknone,CPU1,memory512m. Release and instrumented binary mounts readonly; only new evidence directory writable. No actual.env/production volumes/services/model data.

Observed original deficiencies were length validation and invalid-hex rejection in record_f64. Added12 finite real contract cases:15hex length; illegalg; uppercasehex; malformed UTF8; missingtab; valid request without newline; empty request; exactly384byte valid whitespace frame; exactly385byte rejected frame; stdin directory EISDIR; stdout `/dev/full` ENOSPC for valid and invalid response. The three OS-handle cases exercise genuine io::Result error propagation with explicit exit1, empty stdout and predeclared kernel error-code/message predicates, then additionally byte-identical release stderr comparison. They are bounded local device/handle failures, not resource pressure. All cases pass, including the original49, expected stdout/exit or error predicates; differential equality is additional and does not replace expectations.

Final remaining zero line12 and branchtrue at11 belong to response() finiteness guard after serde_json Number conversion. They remain in denominator, not excluded. No input/source mutation attempted to defeat serde finite-number invariants. Other compiler-unrepresented exceptional/`?`/match paths remain behavior evidence and limitations; Rust/LLVM branch instrumentation is not all control-flow paths or MC/DC.

## Complete scope, dead code and line-count interpretation

Actual export contains all three lexical Rust functions response/handle/main plus two mapped closures, all5 executed. All their CodeRegion mappings retained, including zero-count error regions. An isolated same-compiler opt-level3 control with unchanged instrumentation flags adds an uncalled dormant function; LLVM export retains dormant count0 and covered/total lines1/2. This verifies unused function/line mapping without adding link-dead-code or changing bridge source.

Important discovered LLVM limitation: dormant control raw FILE branch array retains two zero-count outcomes, while its FUNCTION branch arrays and summary say0. Thus successful summary alone does not prove dead-code branch denominator completeness. For actual bridge, every mapped function executes, full raw FILE array count24 equals both reported24 and independently counted LCOV24, so this observed omission does not affect the actual scope. Raw-array equality and lexical function inventory are mandatory checks, not an assumed property for future sources. Preserve full dead control export as evidence of this limitation.

LLVM line summary is a sum of function/closure line instances: main closure line75 and handle closure line38 each also belong to enclosing function. Raw function CodeRegions independently reproduce62total,60original/61final covered. Distinct physical LCOV DA records number60total,58original/59final covered; this difference is disclosed, never rewritten or used to reduce the required62 denominator. Both physical metric and LLVM instance metric independently exceed90% final. LCOV LF/LH summary uses62/61 while DA unique records use60/59. `coverage-verified.json` retains both. Regions135/126covered are separate, not substituted as line or branch metrics.

## Failures and verification chronology

First runtime command used nonexistent `/opt/mvp-numpy/bin/python` and failed before runner entry (exit127). Failure log/command/exit retained; corrected r1 uses actual `/usr/local/bin/python`, all restrictions unchanged. No tests were counted from that failed invocation.

Initial host checker incorrectly assumed source-show rows equalled LLVM summary lines; it failed. r1 LCOV-only count repeated the same semantic mismatch, also retained. Inspecting raw function regions proved the closure line-instance distinction above; r2 then deliberately failed on an overly broad assumption that dead-function summary includes raw branches. r3 corrects only validator assumptions to require actual raw branches and expose the tool limitation; it does not edit LLVM outputs, source, denominator, corpus or assertions. `verify-final-r3.exit=0` independently verifies real counters, all source identities, fingerprint equivalence and61profile hashes. `identity-after.exit=0` separately checks447 vendor files, exact six metadata feature nodes and official tool component identities after execution.

All original failing87.5% measurement, raw profiles and checker failure logs remain. Final full exports are untouched outputs of matching tools; new machine summary derives from them. Additional LCOV export only read existing binary/profdata, no tests rerun or source changes.

Next: independent reviewer recomputes current frozen artifacts, full scope and diagnostic limitation. Parent owns formal docs/memory handoff. CPU lock, complete Linux backend/model integration, native security/SBOM admission and production release approval remain separate OPEN/BLOCKED work; this Rust diagnostic pass grants no production admission.

Final scope verification r4 additionally checks the only exported /source/ file is exactly main.rs, all83 source-display lines match the unchanged source byte-derived text line-for-line, and every physicalDA line maps to a nonblank actual source line. verify-final-r4.exit=0; no new compilation or cases added after61.

