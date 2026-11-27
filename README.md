# Strata on RDNA2 (gfx1030): a recipe for one RX 6900 XT + 64 GB RAM

[한국어](README.ko.md)

This repository records how [Strata](https://github.com/Niko1221/Strata) was tuned to run Qwen3.8-Flash-Next on a single **AMD Radeon RX 6900 XT 16 GB** with **64 GB of RAM** under Linux (ROCm). Strata's own documentation lists the RX 6000 packages as "not tested on a real card" and asks RX 6000 owners for reports; this is one such report, with the settings, patches and measurements in one place.

**Result on this machine:** about 1,200-1,300 tok/s prefill on fresh 9.7K-119K prompts, 50-64 tok/s decode on short follow-up requests, 256K context, vision on. The same box started the day at 382-414 tok/s prefill (9.7K) and 26-37 tok/s decode.

> **2026-11-27 v3 Update (`patches/v2/0005-v3-rdna2-zen4-exact-kernels.patch`, [`results/v3-exact-kernels.md`](results/v3-exact-kernels.md)):** Adds 6 opt-in exact RDNA2/Zen 4 kernels (`STRATA_GDN_RDNA2=2`, `STRATA_QSA_RDNA2_LDS=1`, `STRATA_MMVQ_RDNA2_ROWS=1`, `STRATA_IQ512_EXACT_DOWN=1`, `STRATA_I8_RDNA2_SINGLE=1`, `STRATA_EXP_MODE=10`) combined with `STRATA_IQ512_EXACT_GU=1` (CTest 28/28, settings 8/8, Metal `stubs_neon.cpp` strict syntax PASS). In warm symmetric ABBA on a dedicated PCIe Gen4 NVMe (`--vram-reserve-mib 896`, `LM_I8` ON, text-only), routing-off **`EXACT_V3`** reaches **`56.8–68.3 tok/s`** (`+10.4% to +14.8%` vs `EXACT_V2` on `short`/`4k_r1`/`4k_r2`, peak **`69.19 tok/s`**, prefill `-2.1% to -14.8%`), while approximate-routing **`MTP6_V3`** improves matched cases by `+2.2% to +4.1%` decode and `-2.2%` 16K prefill (peak **`98.76 tok/s` / `15.60 s`**; `4k_r2` within MTP acceptance noise).
>
> **2026-11-26 v2 Update (Custom Patched Build on Strata `2af30ccaa` / v0.2.21.1):** Opt-in Phase 1/2 RDNA2 patches ([`patches/v2/`](patches/v2/README.md), [`results/v2-phase1-2.md`](results/v2-phase1-2.md); non-standard text-only runs, `n=1–2`) show **50–59 tok/s** warm 4K–16K decode with approximate routing OFF (`EXACT_P2` routing-off ref) and **89–101 tok/s** with approximate routing ON (`P1_MTP6`, output-changing `STRATA_ROUTE_SMART`), cut matched 16K direct SSD reads by **-55.5%** (`53.97 → 23.99 GiB`, `-11.4%` prefill time / `+12.9%` tok/s via `STRATA_LM_I8=1`), add lower-drift `P2_CAL` (`-66.1%` excess NLL vs `SMART v1` on one 808-token check, 8/8 rubric + `finish_reason=="stop"`), bundle a CPU-only verified Zen 4 AVX-512 exact IQ Gate/Up patch (`STRATA_IQ512_EXACT_GU=1`, not run in E2E tables), and add fail-closed `O_DIRECT` error handling + a read-only NVMe watchdog ([`scripts/nvme_watchdog.py`](scripts/nvme_watchdog.py)).

| | |
|---|---|
| [`hardware.md`](hardware.md) | The machine, ROCm build, engine build flags |
| [`results/`](results/README.md) | Historical v0.1.42 measurements, VRAM breakdown, real-use request shape |
| [`results/v3-exact-kernels.md`](results/v3-exact-kernels.md) | **2026-11-27 v3:** 6 new exact RDNA2/Zen 4 kernels (`0005`), synthetic verification, Gen4 NVMe warm ABBA (`EXACT_V3` +10–15%, `MTP6_V3`), and Linux NVMe/PCIe PM notes |
| [`results/v2-phase1-2.md`](results/v2-phase1-2.md) | **2026-11-26 v2:** custom-build Phase 1/2 ABBA (`n=1–2`), 16K `LM_I8` I/O, 808-tok routing drift & 8-task completion check, CPU-only AVX-512 verification, and storage mitigations |
| [`rejected.md`](rejected.md) | What was tried and lost on this hardware (updated 2026-11-27) |
| [`config/`](config/engine.v3-exact.example.json) | Sanitized example configs (`engine.example.json` v0.1.42; `engine.v2-p1-mtp6.example.json` & `engine.v2-p2-cal.example.json` v2; **`engine.v3-exact.example.json` v3**) |
| [`patches/`](patches/README.md) | v0.1.42 patches (`patches/engine/`, `patches/serve/`) and **v2/v3 opt-in patches on `2af30ccaa`** ([`patches/v2/`](patches/v2/README.md)) |
| [`scripts/nvme_watchdog.py`](scripts/nvme_watchdog.py) | Continuous read-only sysfs NVMe health/temperature watchdog + unit tests (`test_nvme_watchdog.py`) |

Related: the [RDNA2 gfx1030 AI optimization handbook](https://github.com/unixyo/rdna2-gfx1030-ai-handbook) collects operator-level measurements from the same machine. Its §9.18 covers later Strata prefill research (typical-J tiles, the warm bottleneck), which builds on this recipe and does not change its settings.

## Quick start

1. Install a ROCm runtime that knows gfx103x. This machine used AMD's TheRock `gfx103X-all` 10.0.0 tarball unpacked in a user directory, with no `HSA_OVERRIDE_GFX_VERSION`.
2. Check out Strata `v0.1.42`, apply `patches/engine/*.patch` (and `patches/serve/*.diff` if you use the Python server), build with HIP for gfx1030 (`hardware.md`).
3. Get the ISTA-DASLab SC117 IQ3_XXS files and build the expert pack with Strata's tools. No model files are included here.
4. Copy `config/engine.example.json`, fill in the `<...>` paths, start the server.

## What mattered most

1. **IQ3_XXS instead of IQ3_S.** With 64 GB of RAM the 40 GiB IQ3_XXS experts stay in the page cache and the 47 GiB IQ3_S experts do not. Prefill went up 1.1-3.5x and decode went from 22-41 to 40-45 tok/s from this alone.
2. **gfx1030 prompt paths:** FP16 prompt GEMMs with a rocBLAS tuning table (`STRATA_HIP_PROMPT_F16`, `STRATA_ROCBLAS_TUNING`) and SIMT QSA select. The #3381 prompt attention backport (patch 0005) only runs with int8 KV; with the k8v4 KV of the final config it falls back to the split path and does nothing (see `results/` step 3).
3. **GDN switches** (`STRATA_GDN_HEAD/PP/CONVL2/NOY`, `STRATA_CVEC_FUSE`): +5-12% depending on prompt length.
4. **`STRATA_ROUTE_RESIDENT=1.0`:** +8-18% decode, but it changes the model's output. Check quality on your own tasks.
5. **Leave RAM to the page cache.** Pinning experts in RAM or growing the resident KV made everything slower.

## Limits

- One machine, one model. Run counts are small (mostly two to four per cell).
- Engine base is v0.1.42; upstream has moved on (v0.2.8 at the time of writing). Some of this may already be upstream or no longer apply.
- Answer quality at IQ3_XXS, k8v4 and 256K has not been measured end to end.

## License

MIT. The patches are derived from Strata (MIT, Niko1221 and the Strata contributors). Patches 0002, 0003 and 0005 backport Strata PRs #1151, #1167 and #3381 by @Vop3p; the credit for those changes is theirs.
