# Independent numeric bridge review, 2026-10-20

Scope: isolated MVP only; no production code edited. Input source/executable manifest unchanged (14/14 SHA256 checks). Cargo build --offline --locked exit 0; cargo tree --offline --locked -e features exit 0 confirms std only/no float_roundtrip/arbitrary_precision; Python unittest test_bridge exit 0 (6 tests). Review script exit 0 independently checks archive identity, 14 endpoint/tag/zero probes and actual RustSec scan. These finite checks validate wiring, not whole-domain equivalence.

## Closeable boundary: formatter/parser algorithm and typed scalar mapping

Official GitHub API fixed Chroma tag 1.5.9 resolves to commit 11f3c7435e71024aa0a2b53710a28d3289d922d1. metadata source fetched both by tag and by commit has identical SHA256 32cc67b10eea1db964f1f8d1a00fd0955f05934cd51c9b54192ea4009e357f95. Original Cargo.lock confirms serde/serde_derive 1.0.228, serde_json 1.0.149 and zmij 1.0.21. Sources are preserved beside this report. Raw download failed (7 ordinary, 56 escalated); API retry succeeded (0), so typed source availability is no longer blocked.

metadata.rs 326-354 and 618-646: both UpdateMetadataValue and MetadataValue derive Deserialize/Serialize with serde(untagged), in Bool, Int(i64), Float(f64), Str... order. PyO3 extraction checks bool, i64 then f64 (357-402, 649-691). MetadataValue -> UpdateMetadataValue maps Int and Float unchanged (942-956). Serde derive enum_untagged.rs 45-60 buffers Content once then tries variants in declaration order. Serde private/de.rs 2006-2039 accepts only integer Content variants for integer decoding and accepts F64 unchanged for float decoding. serde_core 1.0.228 de/impls.rs 399-404 confirms i64 does not accept F64 and range-checks U64. Value's numeric visitor stores those same parser-produced F64/I64/U64 values (serde_json src/value/de.rs 36-73).

For every finite input binary64 payload, original Float serialization and bridge record_f64 serialization call identical serde_json::serialize_f64 -> Formatter::write_f64 -> zmij::Buffer::format_finite. Zmij's zero branch and fixed-format branches emit a decimal point; other branch emits exponent notation (src/lib.rs ~1030-1108). Hence every successfully parsed float token yields F64 Content. Original typed Bool/Int reject that Content, Float accepts its bits unchanged. Bridge ValueVisitor accepts the same parser-produced bits and emits them as hex. If the shared parser rejects a token, both paths reject. This is a source-based all-input stage argument, not a statistical inference.

For every signed I64 input, identical integer serialization yields exact integer token. Nonnegative tokens parse U64 <= I64_MAX and typed Int accepts exactly; negative tokens parse I64. Bridge record_i64 deliberately maps either to I64 exactly. No serialized record float can accidentally enter the integer case. Positive where tokens retain U64, including >I64_MAX, for the existing where compiler's later rules; outside-U64 and outside-negative-I64 numeric tokens follow the same parser float fallback. Where input must be canonical Python json.dumps numeric token; raw whitespace variants are outside wrapper-generated token scope.

Signed zero survives formatter/parser and hex transport. SQLite REAL canonicalization occurs only after replay; bridge.decode(sqlite_record=True) agrees with real SQLite test. Public readback must consume stored values directly; calling record bridge a second time would change values for non-idempotent formatter/parser examples and remains forbidden.

This closes the isolated algorithm/typed-scalar mapping gap conditional on the already established original default-parser feature identity. It does not close entire production R5 admission, PyO3 arbitrary Python object/subclass behavior, bool/string/array metadata, where predicates, packaging, consumer wiring or cross-platform behavior.

## Production gates still open

- bridge.py fixes a developer Windows debug exe path but does not verify binary SHA/signature at runtime. A source manifest is evidence, not authenticity enforcement. Secure package ownership, build identity and tamper rejection remain required.
- subprocess.run bounds child wait to 10 seconds, shell=False and minimal environment; no arbitrary command/file interface or payload echo found. However validation/join run before timeout and stdin lines, batch length and captured stdout/stderr are unbounded in memory. Child BufRead::lines also allocates an unbounded line. Host CPU/memory budget and supported-size semantics require explicit production design and behavior tests. Process creation itself may not honor the communicate timeout immediately. Do not claim hard resource isolation.
- Protocol requires exactly three validated fields and row count; finite f64 and integer ranges are checked. Child errors recover for following requests. Generic exchange/decode are trusted private helpers, not ready-made public endpoint validators; production should wrap timeout, missing binary, encoding, malformed output and child failures without leaking input or operational paths.
- Linux/macOS executable selection, architecture/toolchain locks, distribution installation, native CRT/MSVC/stdlib inventory, service lifecycle, concurrent/batch performance and real production consumer regression remain unverified. Do not copy the MVP as a production helper unchanged.

## Actual dependency audit

Recovered official cargo-audit/v0.22.2 asset 439294720 through GitHub API (exit 0), isolated unpack only. Zip SHA256 0a7316540862c13d954f648917ceacca593747baed6eec180fafa590be2710ab and exe SHA256 0157f5ce1ce9fd4fb0a1f7c79af1229771d1f80b6c2613ddb0d9200a8ba73946 match preserved official API digest/receipt; --version exit 0 reports 0.22.2. Direct release URL ordinary failed7 and escalated timed out28; API succeeded. No global install/system configuration change.

Fixed RustSec tar SHA256 0c3e3b16dc0bdf62a446b2b7808a567bfcaab9f52fad6336899c1306eecbef2c (recorded commit edb58f5974b83eb8302332821cb6d389777aa351) was checked byte-for-byte against all archived files in actual local db-fixed. Run actual MVP Cargo.lock, no synthetic inventory:

`cargo-audit.exe audit --file <MVP>/Cargo.lock --db <db-fixed> --no-fetch --no-yanked --json --deny warnings`

Exit 0, 1329 advisories, dependency-count 12 including workspace root, vulnerabilities 0, warnings {}. No ignore, severity or target filters. Scope is this exact lock against fixed historical database; dynamic yanked state NOT_RUN; native CRT/MSVC/stdlib not covered. It closes NOT_RUN for this fixed-lock/fixed-DB RustSec scan only. See review-results.json, audit-lock.stdout and audit-lock.stderr for actual arguments/result.

Available cached crate archives were checksum-checked against Cargo.lock and every archived file compared to registry source actually used; six archives available including unused syn. The five compiled crates are serde_core, serde_json, zmij, memchr, itoa. Missing bookkeeping sources still prevent complete offline source distribution/full metadata; this does not invalidate the actual locked offline build.
