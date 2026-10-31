# Locked tool acquisition receipt

27/27 official snapshot HTTPS packages downloaded and verified: **80,210,796 bytes**. Acquisition exit 0; independent fresh file readback exit 0 confirms each complete size and SHA256 against the unchanged signed-index closure lock (`e16943046dec831e9c653962f9158ca5b0d166cb7c7da88f43e4dfe32efce0bf`).

Command: `python .tmp/windows-libuv-cross-mvp-20261029/acquisition/acquire.py`. Four workers, normal requests.Session verified TLS, 90s/package, 600s scheduling bound; actual elapsed 39.59s. No Range retry needed. Exact locked URLs retained; no mirrors or snapshot changes. No cache reuse claimed.

Initial ordinary-permission attempt failed with ProxyError / WinError 10013 and zero downloaded bytes, exit 1. Its 27 receipts and summary remain in `sandbox-failure/`. The same script then ran through normal platform require_escalated approval. `run.log` retains the requests dependency-version warning; it did not prevent verified TLS acquisition. `run.exit` records 0.

Evidence: `summary.json`, 27 `*.receipt.json`, `readback-verification.json`, actual `debs/` files. Every successful package was size/hash checked before promotion from `.partial`; readback rehashed all 27 final files.

Only this new acquisition directory was written. No installation, build, image/runtime/source/main-lock change, Git stage/commit/archive, publication or deployment. Original sealed evidence and keyring retained. Build stage still requires independent input review approval.
