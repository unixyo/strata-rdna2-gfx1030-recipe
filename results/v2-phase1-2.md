# 2026-11-26 v2 Results (Strata `2af30ccaa` / v0.2.21.1 Base)

Measured on the same machine (`RX 6900 XT 16 GB`, `Ryzen 7 7800X3D`, `64 GB DDR5`, `SC117-IQ3_XXS`, `--kv k8v4`, `--max-context 262144`). All new features are **opt-in (default OFF)** and separated into exact/target-preserving paths vs approximate routing paths.

All Phase 1 and Phase 2 results below were independently audited (every decode figure sums **all** generation segments, not just the last segment; strict quality requires `finish_reason == "stop"`).

## 1. Independent Pinned-Production A/B (Phase 1 `C` vs Pinned `v0.2.16`)

Interleaved `A-C-C-A` (`n = 2` per arm, fresh server starts, natural page cache, timing hooks OFF, text-only):

| Arm | Expert Cache Slots | 4K Decode Median | 4K Wall Median | Short Held-Out Decode Median |
|---|---:|---:|---:|---:|
| Pinned `v0.2.16` (`A`, `STRATA_ROUTE_RESIDENT=1.0`) | 5,782 | 35.34 tok/s | 56.37 s | 47.61 tok/s |
| **Phase 1 Balanced `C`** (`EXP_MODE=9`, `RDNA2_HEAD=1`, `SKIP_ZERO_PCIE=1`, `HC_REQ8=1`, `GR_RDNA=1`, `ROUTE_SMART=0.15,3.0,2,1`) | 6,101 | **79.96 tok/s (2.26×)** | **17.99 s** | **102.07 tok/s (2.14×)** |

- Standalone `STRATA_EXP_MODE=9` vs Mode 0 (`native_expert_bench`, 10 real GGUF layers, `G=24, T=4`): **-18.5% to -35.7%** (`-10.0% to -17.7%` vs Mode 8), **0 differing bits** across 2,457,600 floats per comparison.

## 2. Phase 2 Auto-Cache Symmetric ABBA (`C` vs `P1_MTP6` / `P2_CAL` / `EXACT_P2`)

Interleaved `C, P1_MTP6, P1_MTP6, C` + `P2_CAL` (`n=1`) + `EXACT_P2` (`n=1`), `--no-timing-hooks`, `MemAvailable = 50–52 GiB` (RAM-warm), `0 ms` GPU pauses. `C` used `--vram-reserve-mib 512` (`6,101` slots); Phase 2 arms used `--vram-reserve-mib 768` (`5,948` slots; note: use `896` with `--spec 6` to engage `LM_I8` on 16K/24K):

| Workload (Actual Prompt Tokens) | `EXACT_P2` (Routing OFF) | `C` Mean `[r0, r3]` | **`P1_MTP6` Mean `[r1, r2]`** | `P2_CAL` (SMART v2) |
|---|---|---|---|---|
| `short` (`71`) TTFT / decode | 0.86 s / 54.2 tok/s | 1.04 s / **80.3 tok/s** | 1.20 s / 74.7 tok/s (`r2`: 0.80 s / 75.7) | 0.87 s / 70.3 tok/s |
| `4k_r1` (`4,093`) TTFT / decode | 4.47 s / 50.8 tok/s | 4.70 s / 82.72 tok/s | **4.52 s / 89.38 tok/s (+8.1%)** | 5.51 s / 63.1 tok/s |
| `4k_r2` (`4,093`) TTFT / decode | 4.30 s / 55.5 tok/s | 4.04 s / 93.35 tok/s | **4.03 s / 95.89 tok/s (+2.7%)** | **3.95 s / 87.2 tok/s** |
| `16k_r1` (`16,387`) TTFT / decode | 12.84 s / 58.9 tok/s | 12.87 s / 97.75 tok/s | **12.82 s / 100.53 tok/s (+2.8%)** | 13.09 s / 96.0 tok/s |
| `24k_r1` (`30,239`) TTFT / decode | 24.36 s / 50.5 tok/s | 24.55 s / **87.13 tok/s** | **24.18 s** / 83.97 tok/s | 24.60 s / 75.8 tok/s |

## 3. Matched 16K SSD Prefill I/O (`STRATA_PF_DIRECT_HYBRID=1` + `STRATA_LM_I8=1`)

Under ~31 GiB available RAM (`16,387` prompt tokens, `STRATA_ROUTE_SMART=0`):

| Path | Prefill Time (tok/s) | Direct-Path Expert Payload | Total OS Storage Read | 248K Vocab Top-5 | `KL(chunk‖lm)` |
|---|---:|---:|---:|---|---:|
| Chunk-Major (2 chunks, `HYBRID_DIRECT=1`) | 16.161 s (1,014.0) | 53,965.2 MiB | 56,748.0 MB | `[1596, 760, 1421, 22916, 31248]` | 0 (ref) |
| **HIP OWN-I8 Layer-Major (`LM_I8=1`)** | **14.315 s (1,144.8, -11.4%)** | **23,991.9 MiB (-55.5%)** | **25,633.8 MB (-54.8%)** | **100% Top-5 order match** | **`0.00003548`** |

- Note: `LM_I8` uses alternate quantized prompt arithmetic (not bitwise-equal to chunk-major; max abs logit diff `1.74755`). After fixing group-ahead staging (`(fz_l || i8_l)`), a 23,683-token Q4 prompt ran in 2 super-chunks (`20.17 s`, `wait copy = 21 ms / 0.1%`).
- Under desktop RAM pressure (`31–37 GiB` available), eliminating mmap major-fault thrashing (`1.06M–4.66M` faults → near zero) cut observed 4K/16K TTFT from `19.5–44.9 s` / `52–146 s` down to `4.5–6.1 s` / `14.3–16.2 s` (observed end-to-end numbers also reflect natural page-cache state differences).

## 4. Held-Out Teacher-Forced PPL / KL (808 Tokens, 4 New Domains) & Strict 8/8 Quality

| Candidate | PPL (ref `1.20963`) | Excess `ΔNLL` | Approx Top-32 KL | Top-1 Agree | Forced Decode | Strict 8/8 (`fin=stop`) Wall Sum (`n=1`) |
|---|---:|---:|---:|---:|---:|---:|
| `exact_ref` / `EXACT_P2` | 1.20963 | `+0.000000` | `0.000000` | 100.00% | 53.78 tok/s | 8/8 — 173.37 s |
| `C` (`SMART v1`) | 1.22268 | `+0.010729` | `0.013140` | 96.04% | **81.38 tok/s** | 8/8 — 149.22 s |
| **`P2_CAL` (`SMART v2` calibrated)** | **1.21403** | **`+0.003633` (-66.1%)** | **`0.011889` (-9.5%)** | **96.41%** | **78.91 tok/s** | **8/8 — 124.22 s** |
| `smart_v2_qual` | 1.21277 | `+0.002592` (-75.8%) | `0.008139` (-38.1%) | 96.04% | 70.32 tok/s | — |

- `P1_MTP6` uses the same routing as `C` (`8/8 — 129.51 s`). All quality runs configured `--max-context 262144` (longest tested input `23,683` tokens in quality, `30,239` in ABBA; full 256K-filled stress was not run).

## 5. Zen 4 AVX-512 Exact IQ Gate/Up Integration (`STRATA_IQ512_EXACT_GU=1`)

Cherry-picked cleanly onto the hardened Phase 2 branch (`0004-integrate-avx512-exact-iq-gu.patch`, 0 C++ merge conflicts):
- **Component verification (CPU-only, 0 SSD/GPU load):** `iq512_exact_gu_test` (`921,600` outputs bit-identical across all 5 IQ types, 1–8 tokens), `native_arithmetic_parity_mt1`, `isa_guard_check`, `window_rule_test`, `mapped_pages_test`, and `tools.test_settings_register` (8/8) all PASS.
- **1-core RAM synthetic microbench:** `IQ3_XXS` 1–3 tok **-34.6% to -39.3%**, `IQ3_S` **-25% to -26%**, `IQ2_XXS`/`IQ2_XS` **-16% to -22%**.
- **Where it helps most:** Under `STRATA_IQ_MT_MIN=1`, missed CPU experts have mean group width `1.21–1.37` tokens. On warm `P1_MTP6` (CPU = `16.1%` of window) the ceiling is modest (~2–3%), whereas on `EXACT_P2` (CPU = `50.1–52.1%` of window) and cold/transition `P2_CAL` (`23.7%+`) it directly cuts the dominant non-GPU compute path with zero precision loss.

## 6. Storage Safety & Fail-Closed Hardening

During Phase 2 prototyping, sustained 12-thread `O_DIRECT` scanning (~6.89 GB/s) coincided with a KIOXIA EXCERIA PRO NVMe controller drop (`CSTS=0xffffffff`, `-19 ENODEV`). Mitigations implemented and verified via synthetic fault injection (zero extra SSD stress):
1. Default `STRATA_PF_DIRECT_HYBRID` stager concurrency lowered to **4 threads** (`6,598 MB/s` = 95.8% peak at 1/3 queue depth).
2. `FileExpertSource::copy_blob_hybrid` and `Prefill::Stager` are **fail-closed** on `EIO`/`ENODEV`/`ENXIO`/unexpected EOF (no mmap `SIGBUS` fallback, no `std::abort()`), falling back to buffered `copy_blob` only for `EINVAL`/EOF-tail compatibility.
3. [`scripts/nvme_watchdog.py`](../scripts/nvme_watchdog.py) provides continuous 1 s read-only sysfs monitoring (`state == "live"`, `< 65°C`, fail-closed on missing sensor or cooldown timeout; verified 7/7 in [`scripts/test_nvme_watchdog.py`](../scripts/test_nvme_watchdog.py)).
4. **Host rule:** Never place active Linux swap on the same NVMe holding 40 GiB read-heavy model packs.
