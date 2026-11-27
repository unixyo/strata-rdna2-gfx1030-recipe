# 2026-11-27 v3 Results — gfx1030 / Zen 4 Exact Kernel Stack (`0005-v3-rdna2-zen4-exact-kernels.patch`)

Built on top of the hardened Phase 2 + AVX-512 base (`2af30ccaa` + `patches/v2/000[1-4]`) by adding [`patches/v2/0005-v3-rdna2-zen4-exact-kernels.patch`](../patches/v2/0005-v3-rdna2-zen4-exact-kernels.patch). All new v3 switches are **opt-in (default OFF)** and preserve arithmetic exactness with their parent paths.

Measured on the same machine (`RX 6900 XT 16 GB` / `gfx1030`, `Ryzen 7 7800X3D`, `64 GB DDR5`, `SC117-IQ3_XXS`, `--kv k8v4`, `--max-context 262144`, `--vram-reserve-mib 896`, `--spec 6`, text-only / `--vision` OFF) with the model pack moved to a dedicated PCIe Gen4 x4 NVMe SSD (`WD_BLACK SN850X`, `0` I/O on the secondary SSD, `0 ms` GPU pauses, max NVMe temp `41.9°C`).

---

## 1. Opt-In v3 Switches & Component Verification

All switches default to `0` / OFF and are registered in `terminal/data/settings-register.json` (with synchronized Metal `stubs_neon.cpp` and SYCL signatures):

| Switch | Scope | Exactness | Component Verification (Synthetic) |
|---|---|---|---|
| `STRATA_GDN_RDNA2=2` (`1`=GT4, `2`=GT8) | gfx1030 Wave32 GDN HEAD recurrence DPP8 quad-lane layout | **Bit-exact** (FP16 output & state hash match `T=1..16384`) | `T=8192` recurrence `6.794 → 6.213 ms` (`-8.56%`); stage `8.513 → 7.936 ms` |
| `STRATA_QSA_RDNA2_LDS=1` | gfx1030 pre75 `G=12`, `k8v4` QSA query LDS bijective permutation | **Bit-exact** (`73,701,504` nonzero outputs across 160 fixtures) | `cap=2051` `n_q=64..256`: resident `1.037–1.045×`, masked `1.055–1.070×` |
| `STRATA_MMVQ_RDNA2_ROWS=1` | gfx1030 `Q6_K` `K=2560` exact one-row decode dispatch (`NC=6..8` large, `NC=5..8` `N=512`) | **Bit-exact** (selects existing one-row kernel) | `T=6` `1.423–1.594×` across Q6 projections (`2.593 → 1.801 ms`, `-0.793 ms` weighted over 38 actual Q6 tensors) |
| `STRATA_IQ512_EXACT_DOWN=1` | Zen 4 AVX-512 EVEX/VNNI exact CPU `IQ4_NL` Down (`NT>=2`, 18/48 layers) | **Bit-exact** (ISA + first-use byte parity guard; `752,640` values) | 7 workers, 192 experts, `2560×640`: `NT=4` `-12.19%`, `NT=6` **`-24.11%`** (`8.217 → 6.236 ms`), `NT=8` `-21.75%` |
| `STRATA_I8_RDNA2_SINGLE=1` *(keep `STRATA_I8_RDNA2=0`)* | gfx1030 OWN-I8 `128×128` tile single LDS buffer (`IQ3_XXS`/`IQ3_S` GU × `Q2_0`/`IQ4_NL` Down, `LM_I8=1`) | **Bit-exact with existing OWN-I8** (does not convert exact decode) | 128 groups × 320 rows (209–284 MiB weights), `unpack=0`: **`1.036–1.050×`** (`-3.43% to -4.74%`) across all 4 pairs |
| `STRATA_EXP_MODE=10` | gfx1030 `max_group_entries==1` singleton `TN=1` specialization (29/48 layers, exact fallback when `entries>=2`) | **Bit-exact** (144 bounded cases) | 10 singleton groups: `1.041–1.062×` |
| `STRATA_IQ512_EXACT_GU=1` *(from `0004`)* | Zen 4 AVX-512 exact CPU IQ Gate/Up | **Bit-exact** (`921,600` outputs) | First full live E2E evaluation in the v3 bundle below |

- **Automated validation on the v3 build:** serial synthetic CTest **28/28 PASS** (`0` skipped), `tools.test_settings_register` **8/8 PASS**, Metal `stubs_neon.cpp` strict C++20 `-Wall -Wextra -Werror` syntax **PASS**, `nvme_watchdog` **7/7 PASS**.

---

## 2. Live End-to-End Warm ABBA on PCIe Gen4 NVMe (`SN850X`, Text-Only)

Both baselines (`*_V2`) and candidates (`*_V3`) ran on the **exact same v3 binary**, `--vram-reserve-mib 896` (`5,868` expert cache slots, `1,016 MiB` free VRAM so `STRATA_LM_I8=1` reliably engages on `16k_r1`), `--spec 6`, and engine-default stager concurrency. Every decode figure sums **all** generation segments.

- **`V2` env:** Phase 2 flags (`EXP_MODE=9`, `RDNA2_HEAD=1`, `SKIP_ZERO_PCIE=1`, `HC_REQ8=1`, `GR_RDNA=1`, `PF_DIRECT_HYBRID=1`, `LM_I8=1`, `I8_DEFER=1`, `PREFILL_CPU_SHARE=auto`, `MTP_ADAPT=6,0.40,0.15,1.35,0.55`), all v3 flags OFF (`0`).
- **`V3` env:** identical + `STRATA_EXP_MODE=10`, `STRATA_IQ512_EXACT_GU=1`, `STRATA_IQ512_EXACT_DOWN=1`, `STRATA_MMVQ_RDNA2_ROWS=1`, `STRATA_GDN_RDNA2=2`, `STRATA_QSA_RDNA2_LDS=1`, `STRATA_I8_RDNA2=0`, `STRATA_I8_RDNA2_SINGLE=1`.

### 2.1 Routing-Off Exact Track (`EXACT_V2` vs `EXACT_V3`, `STRATA_ROUTE_SMART=0`)

One cold prewarm run (`[00] EXACT_V2`) discarded to eliminate first-run page-cache cold bias, followed by symmetric warm ABBA (`[01] V2, [02] V3, [03] V3, [04] V2`, `MemAvailable = 54.7–55.5 GiB`, total `165.61 GiB` OS reads across all 5 runs):

| Case | Decode `V2 → V3` (Mean of 2) | Prefill0 `V2 → V3` | Wall `V2 → V3` | Draft Acc (`V2 → V3`) & Notes |
|---|---|---|---|---|
| `warmup` | `43.25 → 48.12 tok/s` (**`+11.26%`**) | `1,083.5 → 923.0 ms` (**`-14.81%`**) | `2.83 → 2.50 s` (**`-11.74%`**) | `0.83 → 0.83`, output identical across all 4 runs |
| `short` | `49.48 → 56.80 tok/s` (**`+14.82%`**) | `784.5 → 746.0 ms` (**`-4.91%`**) | `5.66 → 5.09 s` (**`-10.07%`**) | `0.67 → 0.72` |
| `4k_r1` | `51.59 → 56.95 tok/s` (**`+10.39%`**) | `4,723.5 → 4,547.5 ms` (**`-3.73%`**) | `9.57 → 8.93 s` (**`-6.76%`**) | `0.78 → 0.77` (`+10.4%` despite slightly lower `acc`) |
| `4k_r2` | `59.77 → 68.32 tok/s` (**`+14.30%`**) | `4,646.0 → 4,543.0 ms` (**`-2.22%`**) | `8.85 → 8.22 s` (**`-7.05%`**) | `0.82 → 0.84` (**`V3` peak `69.19 tok/s` / `8.17 s`**) |
| `16k_r1` | `59.08 → 59.28 tok/s` (`+0.35%`) | `13,433.5 → 13,151.5 ms` (**`-2.10%`**) | `17.71 → 17.36 s` (**`-1.98%`**) | `0.80 → 0.79` (`[04] V2` spiked to `acc=0.83` / `63.86`; `[01] V2` was `54.29`) |

Because routing-off `EXACT` runs at ~74–82% GPU expert cache hit rate, CPU exact expert compute accounts for ~50% of the decode window; combining `STRATA_IQ512_EXACT_GU=1` + `STRATA_IQ512_EXACT_DOWN=1` with the RDNA2 exact GPU kernels delivers **`+10.4% to +14.8%` decode** and **`-2.1% to -14.8%` prefill** without changing routing.

### 2.2 Approximate-Routing Production Track (`MTP6_V2` vs `MTP6_V3`, `STRATA_ROUTE_SMART=0.15,3.0,2,1`)

Symmetric warm ABBA immediately following §2.1 (`[00] V2, [01] V3, [02] V3, [03] V2`, `MemAvailable = 54.1–54.3 GiB`, total `88.45 GiB` OS reads):

| Case | Decode `V2 → V3` (Mean of 2) | Prefill0 `V2 → V3` | Wall `V2 → V3` | Draft Acc (`V2 → V3`) & Notes |
|---|---|---|---|---|
| `warmup` | `68.48 → 70.96 tok/s` (**`+3.61%`**) | `672.5 → 601.5 ms` (**`-10.56%`**) | `1.66 → 1.55 s` (**`-6.34%`**) | `0.77 → 0.77`, output identical across all 4 runs |
| `short` | `74.87 → 76.48 tok/s` (**`+2.16%`**) | `785.5 → 749.5 ms` (**`-4.58%`**) | `4.08 → 3.98 s` (**`-2.44%`**) | `0.69 → 0.71` |
| `4k_r1` | `85.72 → 89.25 tok/s` (**`+4.13%`**) | `4,693.0 → 4,760.0 ms` (`+1.43%`) | `7.59 → 7.55 s` (`-0.58%`) | `0.82 → 0.83` |
| `4k_r2` | `95.71 → 89.94 tok/s` (`-6.03%`) | `4,321.0 → 4,338.0 ms` (`+0.39%`) | `6.93 → 7.10 s` (`+2.46%`) | `0.78 → 0.75` (high MTP variance: `[00]` `0.84` vs `[02]` `0.71`) |
| `16k_r1` | `93.28 → 92.89 tok/s` (`-0.42%`) | `13,311.0 → 13,017.5 ms` (**`-2.20%`**) | `15.99 → 15.71 s` (**`-1.77%`**) | `0.78 → 0.81` (**`[01] V3` peak `98.76 tok/s` / `15.60 s`**) |

Under `STRATA_ROUTE_SMART`, GPU cache hit rate is already **92–97%**, so CPU exact experts fire far less often than in `EXACT`. The net GPU kernel gain (`+2–4%` decode, `-2.2%` 16K prefill) is consistent on matched-acceptance cases (`warmup` `+3.61%`, `4k_r1` `+4.13%`), while `n = 2` run-to-run MTP acceptance variance (`0.71` vs `0.84`) can mask small gains on individual cells (`4k_r2`).

---

## 3. Linux NVMe / PCIe Power-Management Diagnostic Note

During v3 live testing on Linux 7.3 with a Phison E18 NVMe (`KIOXIA EXCERIA PRO`, `EIFA10.1`, in `M2_1` adjacent to the RX 6900 XT), concurrent GPU+CPU+Strata I/O triggered repeated `CSTS=0xffffffff` / `-19 ENODEV` controller drops even at 4 stager threads, 0 swap, `41.9–43.9°C`, and BIOS `M2_1` Gen3 x4 + ASPM Disabled—whereas a pure 160 GiB `O_DIRECT` read (`3,573 MiB/s`) with the GPU idle passed with `0` errors.

Two mitigations were verified on the same host:
1. Adding all three kernel boot parameters (`nvme_core.default_ps_max_latency_us=0 pcie_aspm=off pcie_port_pm=off`, forcing root-port `power/control=on` and NVMe `pm_qos=0`) allowed the same KIOXIA drive (Gen3) to complete a full 4-arm `EXACT` ABBA (`133.22 GiB` read, max `40.9°C`, `0` kernel warnings; background writer closed).
2. Moving the `112.32 GiB` model pack to the second CPU-direct Gen4 x4 NVMe (`WD_BLACK SN850X` with tall heatsink in `M2_2`) eliminated all KIOXIA I/O and completed 9 consecutive arms (`254.06 GiB` read, max `41.9°C`, `0` errors).
