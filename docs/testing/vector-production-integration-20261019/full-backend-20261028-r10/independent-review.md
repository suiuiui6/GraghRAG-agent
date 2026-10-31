# Independent final R10 evidence review — 2026-10-28

Verdict: **Windows backend Python source gate passes** for the exact R10 snapshot. This does not close first-party Rust coverage, CPU lock, Linux/model-container recovery, complete native/uv risk or overall production/delivery admission. No commit/push/deploy/activation claim.

## Actual evidence verification

Read-only recomputation command, executed after R10 completed:

```text
D:/graghRAG-agent/.tmp/backend-runtime-20261028/.venv/Scripts/python.exe -B D:/graghRAG-agent/.tmp/git-identity-independent-review-20261028/check_r10_evidence.py
```

Final execution exit **0**; output `r10-evidence-check.log`; machine result `r10-recomputed.json`. No unnecessary full test rerun and no changes to captured input files. R10 summary SHA256 independently read: `b091b1a360c5c3d0a3c55b085c596f74f3d4db412942dc1e40dac2084cf4c502`.

The reviewer script had two initial local normalization assertion failures while converting collected node IDs to JUnit identities (IPv6 parameter `::`, then parameter backslash preservation). The parser was corrected to split class separators only before the parameter bracket and normalize only source-path separators. No source, test or evidence input changed; final exact Counter comparison passes.

## Test and scope findings

- Collected node IDs: **2201 unique**, exact identity Counter equals all **2201 JUnit** cases; **zero failure/error/skip**. Current parametrized names are retained verbatim.
- Every original R9 **2187** identity retained with Counter multiplicity, baseline SHA matches receipt. Separately compared every original R7 **2157** identity to current JUnit; all retained.
- Independent current first-party production Python inventory = recorded production inventory = coverage file inventory: **120**, missing/extra empty. Worker is included; no exclusion added. Coverage config uses unchanged Python backend scope and no pragma exclusions. Rust source is outside this Python report and remains a separate required evidence question.
- New test file on C hashes to `19cbabcd3a74249650d31696139e7a1caf380d140c83b5d57a0ba138e676b431`, exactly the independently reviewed 14-case revision. No production edit was needed to add these tests.
- All **258 source snapshot** entries and **3426 selected-runtime snapshot** entries match before/after and actual current files at final verification. This includes the captured design/plan/Docker inputs and actual R10 driver/coverage tooling. It is not a claim that every installed site-packages byte was inventoried.

## Raw coverage counts and timing

Independently summed per-file counters, confirming report totals and summary:

| Metric | Covered / total | Separate percentage | Result |
|---|---:|---:|---|
| Python executable lines | 16624 / 17802 | 93.3827659814% | PASS |
| Python branches | 5481 / 6086 | 90.0591521525% | PASS |

Both checks use integer multiplication by100 against denominator times90. Branch required count is5478, current result is three above threshold; no rounding used. The report's mixed `percent_covered=92.5360013396` is not the line metric.

Recorded collect/tests/export exits are **0/0/0**. Tests command elapsed **361.094 seconds** within unchanged whole-command1200 seconds; pytest reports **333.14 seconds**. Per-test timeout remains60 seconds except existing explicit markers. This is successful execution timing on the current prepared environment, not a cold-start performance comparison to older runs.

Fixed-model HTTP evidence in successful JUnit:

- `test_fixed_local_model_http_upload_update_delete_restart`: pass, **44.041 seconds** including fixture/setup accounting; pytest call duration43.93 seconds.
- `test_fresh_process_http_reopen_after_update_and_after_delete`: pass, **10.316 seconds** including fixture accounting; pytest call duration9.89 seconds.
- `test_real_offline_fixed_model_encodes_synthetic_input`: pass, **0.304 seconds**.

The tests retain real fixed offline model/HTTP lifecycle and restart behavior; these pass results do not establish an unexecuted Linux container deployment. Source/runtime equality, command gate, scope gate, test gate and both Python raw-count coverage checks independently agree with `backend_gate=true`.

R9 remains a historical failed dual90 snapshot; this review does not rewrite its89.861978% branch result. Subsequent code/test/coverage-input changes require fresh applicable validation. Windows remains **audit-only-windows**, with no assertion of mechanically enforced CI/branch protection.
