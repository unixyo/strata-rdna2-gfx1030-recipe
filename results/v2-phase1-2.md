# 2026-11-26 v2 Results (Strata `2af30ccaa` / v0.2.21.1 Base, Custom Patched Build)

Measured on the same machine (`RX 6900 XT 16 GB`, `Ryzen 7 7800X3D`, `64 GB DDR5`, `SC117-IQ3_XXS`, `--kv k8v4`, `--max-context 262144`, text-only / `--vision` OFF for all benchmark tables below). **These are non-standard, custom-build measurements** (not stock upstream `v0.2.22` and not the draft `strata bench run` protocol). All new switches in `patches/v2/` are **opt-in (default OFF)**.

> **Config note:** [`config/engine.v2-p1-mtp6.example.json`](../config/engine.v2-p1-mtp6.example.json) and [`config/engine.v2-p2-cal.example.json`](../config/engine.v2-p2-cal.example.json) are **daily-use example configs** (`--vision` ON, `--vram-reserve-mib 896`, `STRATA_IQ512_EXACT_GU=1`), not exact reproductions of the text-only benchmark tables below (`--vision` OFF, reserve `512`/`768`, `STRATA_IQ512_EXACT_GU` OFF).
>
> **Exact vs output-changing switches:** `STRATA_EXP_MODE=9`, `STRATA_RDNA2_HEAD=1`, `STRATA_SKIP_ZERO_PCIE=1`, `STRATA_PF_DIRECT_HYBRID=1`, and `STRATA_MTP_ADAPT` preserve arithmetic/routing, whereas `STRATA_ROUTE_RESIDENT=1.0` (baseline `A`), `STRATA_HC_REQ8=1`, `STRATA_LM_I8=1`, and `STRATA_ROUTE_SMART` (v1/v2) can change output logits/tokens. Accordingly, the `EXACT_P2` arm below is a **routing-off reference** (`STRATA_ROUTE_SMART=0`, with `STRATA_HC_REQ8=1` and `STRATA_LM_I8=1` still enabled), not a bitwise-stock baseline.

Every decode figure below sums **all** generation segments (not just the last segment).

## 1. Local Baseline vs Phase 1 `C` (`v0.2.16` vs `2af30ccaa + Phase 1`, Interleaved `A-C-C-A`)

Interleaved `A-C-C-A` (`n = 2` per arm, fresh server starts, natural page cache, `--no-timing-hooks`, text-only). Note that this comparison bundles multiple changes simultaneously (engine revision `v0.2.16` → `2af30ccaa`, RDNA2 kernel patches, output-changing routing `STRATA_ROUTE_RESIDENT=1.0` → `STRATA_ROUTE_SMART`, expert cache slots `5,782` → `6,101`, and natural page-cache state); it is a composite local before/after observation rather than an isolated patch-only gain:

| Arm (`n = 2`, mean/median of 2 runs) | Expert Cache Slots | 4K Decode | 4K Wall | Short Held-Out Decode |
|---|---:|---:|---:|---:|
| Local pinned `v0.2.16` (`A`, `STRATA_ROUTE_RESIDENT=1.0`) | 5,782 | 35.34 tok/s | 56.37 s | 47.61 tok/s |
| Phase 1 `C` (`2af30ccaa` + `EXP_MODE=9`, `RDNA2_HEAD=1`, `SKIP_ZERO_PCIE=1`, `HC_REQ8=1`, `GR_RDNA=1`, `ROUTE_SMART=0.15,3.0,2,1`) | 6,101 | 79.96 tok/s (2.26× composite) | 17.99 s | 102.07 tok/s (2.14× composite) |

- Standalone kernel microbenchmark — `STRATA_EXP_MODE=9` vs Mode 0 (`native_expert_bench`, 10 real GGUF layers, `G=24, T=4`): **-18.5% to -35.7% kernel execution time** (`-10.0% to -17.7%` vs Mode 8), **0 differing bits** across 2,457,600 floats per comparison (kernel-level timing only, not E2E tok/s).

## 2. Phase 2 Auto-Cache ABBA (`C` vs `P1_MTP6`, `n = 2`) & Single-Run Reference Observations (`n = 1`)

Interleaved `C, P1_MTP6, P1_MTP6, C` (`n = 2` each), followed by separate `n = 1` observations for `P2_CAL` and `EXACT_P2` (routing-off reference), `--no-timing-hooks`, `MemAvailable = 50–52 GiB` (RAM-warm; `16k_r1` OS storage reads were only `25–27 MB`), `0 ms` GPU pauses. `C` used `--vram-reserve-mib 512` (`6,101` slots, `644 MiB` free VRAM); Phase 2 arms used `--vram-reserve-mib 768` (`5,948` slots, `888 MiB` free VRAM with `--vision` OFF). Because `n = 1–2`, reserve/slot counts differ between `C` and `P1_MTP6`, and run-to-run variance is large (e.g., `P1_MTP6` short TTFT `0.80–1.59 s`, `C` 16K decode `91.12–104.39 tok/s`), small differences (~2–8%) are within measurement noise:

| Workload (Actual Prompt Tokens) | `EXACT_P2` (routing-off ref, `n = 1`) | `C` Mean `[r0, r3]` (`n = 2`, 6,101 slots) | `P1_MTP6` Mean `[r1, r2]` (`n = 2`, 5,948 slots) | `P2_CAL` (`SMART v2`, `n = 1`, 5,948 slots) |
|---|---|---|---|---|
| `short` (`71`) TTFT / decode | 0.86 s / 54.2 tok/s | 1.04 s `[1.01, 1.07]` / 80.3 tok/s `[79.5, 81.2]` | 1.20 s `[0.80, 1.59]` / 74.7 tok/s `[73.7, 75.7]` | 0.87 s / 70.3 tok/s |
| `4k_r1` (`4,093`) TTFT / decode | 4.47 s / 50.8 tok/s | 4.70 s `[4.57, 4.82]` / 82.7 tok/s `[82.1, 83.4]` | 4.52 s `[4.46, 4.57]` / 89.4 tok/s `[89.0, 89.8]` | 5.51 s / 63.1 tok/s |
| `4k_r2` (`4,093`) TTFT / decode | 4.30 s / 55.5 tok/s | 4.04 s `[4.03, 4.05]` / 93.4 tok/s `[90.8, 95.9]` | 4.03 s `[3.96, 4.11]` / 95.9 tok/s `[91.8, 100.0]` | 3.95 s / 87.2 tok/s |
| `16k_r1` (`16,387`) TTFT / decode | 12.84 s / 58.9 tok/s | 12.87 s `[12.80, 12.94]` / 97.8 tok/s `[91.1, 104.4]` | 12.82 s `[12.70, 12.95]` / 100.5 tok/s `[100.5, 100.6]` | 13.09 s / 96.0 tok/s |
| `24k_r1` (`30,239`) TTFT / decode | 24.36 s / 50.5 tok/s | 24.55 s `[24.33, 24.77]` / 87.1 tok/s `[86.5, 87.8]` | 24.18 s `[24.16, 24.20]` / 84.0 tok/s `[83.6, 84.4]` | 24.60 s / 75.8 tok/s |

- Within the same `2af30ccaa` build (`EXACT_P2` routing-off ref vs `C` / `P1_MTP6`), most of the decode speedup (`~1.5–1.7×` on 4K–24K) comes from approximate routing (`STRATA_ROUTE_SMART`).

## 3. Matched 16K SSD Prefill I/O (`STRATA_PF_DIRECT_HYBRID=1` + `STRATA_LM_I8=1`)

Single matched pair (`n = 1` each) under ~31 GiB available RAM (`16,387` prompt tokens, `STRATA_ROUTE_SMART=0`):

| Path | Prefill Time (Throughput) | Direct-Path Expert Payload | Total OS Storage Read | 248K Vocab Top-5 (checked logit point) | `KL(chunk‖lm)` |
|---|---:|---:|---:|---|---:|
| Chunk-Major (2 chunks, `HYBRID_DIRECT=1`) | 16.161 s (1,014.0 tok/s) | 53,965.2 MiB | 56,748.0 MB | `[1596, 760, 1421, 22916, 31248]` | 0 (ref) |
| **HIP OWN-I8 Layer-Major (`LM_I8=1`)** | **14.315 s (-11.4% time / +12.9% tok/s: 1,144.8)** | **23,991.9 MiB (-55.5%)** | **25,633.8 MB (-54.8%)** | **Top-5 order match** | **`0.00003548`** |

- Note: `LM_I8` uses alternate quantized prompt arithmetic (not bitwise-equal to chunk-major; max abs logit diff `1.74755` at the checked prompt position). After fixing group-ahead staging (`(fz_l || i8_l)`), a 23,683-token Q4 prompt ran in 2 super-chunks (`20.17 s`, `wait copy = 21 ms / 0.1%`).
- Separate desktop RAM-pressure observations (`31–37 GiB` available, natural page-cache state not held constant): eliminating mmap major-fault thrashing (`1.06M–4.66M` faults → near zero) coincided with observed 4K/16K TTFT dropping from `19.5–44.9 s` / `52–146 s` down to `4.5–6.1 s` / `14.3–16.2 s`.

## 4. Routing Drift & Task-Completion Check (808 Tokens + 8-Prompt Suite)

Teacher-forced drift over one 808-token set (4 domains, no confidence intervals; measured against the routing-off `EXACT_P2` reference rather than stock upstream) plus an `n = 1` 8-prompt automated check (math CRT, Python unit tests, JSON schema, 23.6K hop, Korean rubric, 3-turn chat; requires both task rubric pass and `finish_reason == "stop"`):

| Candidate | PPL (vs `EXACT_P2` ref) | Excess `ΔNLL` (vs ref) | Approx Top-32 KL | Top-1 Agree (mismatches / 808) | Forced Decode | 8-Task Automated Check (`n = 1`, wall sum) |
|---|---:|---:|---:|---|---:|---|
| `EXACT_P2` (routing-off ref) | 1.20963 | `+0.000000` (by def.) | `0.000000` (by def.) | 100.00% (`0 / 808`, by def.) | 53.78 tok/s | 8/8 — 173.37 s |
| `C` (`SMART v1`) | 1.22268 | `+0.010729` | `0.013140` | 96.04% (`32 / 808`) | 81.38 tok/s | 8/8 — 149.22 s (`P1_MTP6`: `129.51 s`) |
| `P2_CAL` (`SMART v2` calibrated) | 1.21403 | `+0.003633` (-66.1% vs `C`) | `0.011889` (-9.5% vs `C`) | 96.41% (`29 / 808`) | 78.91 tok/s | 8/8 — 124.22 s |
| `smart_v2_qual` | 1.21277 | `+0.002592` (-75.8% vs `C`) | `0.008139` (-38.1% vs `C`) | 96.04% (`32 / 808`) | 70.32 tok/s | — |

- Limits: Top-1 difference between `C` and `P2_CAL` is 3 tokens out of 808 (`32` vs `29` mismatches). In the initial 1,536-token budget run, all four arms hit `finish_reason == "length"` on Q3/Q5 (6/8); raising the token cap (3,072/4,096) yielded 8/8 rubric + stop completion on all arms (`n = 1`, wall-time ranking subject to single-run variance). All runs configured `--max-context 262144` (longest actual inputs: `23,683` tokens here, `30,239` in §2; full 256K-filled stress was not run).

## 5. Zen 4 AVX-512 Exact IQ Gate/Up Integration (`STRATA_IQ512_EXACT_GU=1`, Component-Only)

**Not enabled in any benchmark table in §1–§4 above.** Cherry-picked cleanly onto the hardened Phase 2 branch (`0004-integrate-avx512-exact-iq-gu.patch`, 0 C++ merge conflicts; standalone patch `0000-standalone-iq512-exact-gu.patch` for plain `2af30ccaa`):
- **Component verification (CPU-only, 0 SSD/GPU load):** `iq512_exact_gu_test` (`921,600` outputs bit-identical across all 5 IQ types, 1–8 tokens), `native_arithmetic_parity_mt1`, `isa_guard_check`, `window_rule_test`, `mapped_pages_test`, and `tools.test_settings_register` (8/8) all PASS.
- **1-core RAM synthetic microbench:** `IQ3_XXS` 1–3 tok **-34.6% to -39.3% time**, `IQ3_S` **-25% to -26%**, `IQ2_XXS`/`IQ2_XS` **-16% to -22%**.
- **Not yet run:** Full GPU+SSD end-to-end A/B. Under `STRATA_IQ_MT_MIN=1`, missed CPU experts have mean group width `1.21–1.37` tokens; theoretical E2E ceiling is small on warm `P1_MTP6` (~2–3%, within run noise) and larger on routing-off `EXACT_P2` (where CPU accounts for `50.1–52.1%` of the decode window).

## 6. Storage Mitigations & Fail-Closed Hardening

During Phase 2 prototyping, sustained 12-thread `O_DIRECT` scanning (~6.89 GB/s) coincided with a KIOXIA EXCERIA PRO NVMe controller drop (`CSTS=0xffffffff`, `-19 ENODEV`). Mitigations implemented and verified via synthetic fault injection (note: coincidence does not establish root cause, and 4-thread concurrency is a queue-depth mitigation rather than a long-term hardware durability guarantee):
1. Default `STRATA_PF_DIRECT_HYBRID` stager concurrency lowered to **4 threads** (`6,598 MB/s` = 95.8% peak at 1/3 queue depth).
2. `FileExpertSource::copy_blob_hybrid` and `Prefill::Stager` are **fail-closed** on `EIO`/`ENODEV`/`ENXIO`/unexpected EOF (no mmap `SIGBUS` fallback, no `std::abort()`), falling back to buffered `copy_blob` only for `EINVAL`/EOF-tail compatibility.
3. [`scripts/nvme_watchdog.py`](../scripts/nvme_watchdog.py) provides continuous 1 s read-only sysfs monitoring (`state == "live"`, `< 65°C`, fail-closed on missing sensor or cooldown timeout; verified 7/7 in [`scripts/test_nvme_watchdog.py`](../scripts/test_nvme_watchdog.py)).
4. **Host rule:** Never place active Linux swap on the same NVMe holding 40 GiB read-heavy model packs.
