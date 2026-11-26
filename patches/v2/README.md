# v2 Patches (Base: Strata `2af30ccaa` / v0.2.21.1)

Apply in order on top of upstream [Niko1221/Strata](https://github.com/Niko1221/Strata) commit `2af30ccaa0729177c4725ee2073f72bf550e2f86`. All new features are **opt-in (default OFF)**.

| Patch | Commit / Scope | Exact vs Approx | Notes |
|---|---|---|---|
| `0000-standalone-iq512-exact-gu.patch` | Standalone Zen 4 AVX-512 exact IQ Gate/Up (`STRATA_IQ512_EXACT_GU=1`) | **Bit-exact** | Use alone on `2af30ccaa` if you only want CPU optimization (do not apply together with `0004`). |
| `0001-phase1-rdna2-kernels-and-smart-v1.patch` | Phase 1: `STRATA_EXP_MODE=9`, `STRATA_RDNA2_HEAD=1`, `STRATA_SKIP_ZERO_PCIE=1`, `STRATA_HC_REQ4`, `STRATA_ROUTE_SMART` v1 | Mixed (`EXP_MODE=9`, `RDNA2_HEAD`, `SKIP_ZERO_PCIE` exact; `HC_REQ4`, `ROUTE_SMART` opt-in approx) | `EXP_MODE=9` verified 0 differing bits across 10 real GGUF layers. |
| `0002-phase2-hybrid-odirect-lm-i8-smart-v2-mtp.patch` | Phase 2: `STRATA_PF_DIRECT_HYBRID=1` (4-thr default), `STRATA_LM_I8=1`, `STRATA_ROUTE_SMART_V2`, `STRATA_ADAPT_COLD_CAP`, `STRATA_MTP_ADAPT` | Mixed (`HYBRID_DIRECT`, `MTP_ADAPT` exact; `LM_I8` `KL=3.55e-5`; `SMART_V2` opt-in approx) | Apply after `0001`. |
| `0003-phase2-hardening-fail-closed-metal-stubs-register.patch` | Fail-closed `copy_blob_hybrid`/`Prefill::Stager` on `EIO`/`ENODEV`/`ENXIO`, Metal stubs (`stubs_neon.cpp`), 10-flag `settings-register.json` | Hardening / integration | Apply after `0002`. `tools.test_settings_register` 8/8 PASS. |
| `0004-integrate-avx512-exact-iq-gu.patch` | Integrates `STRATA_IQ512_EXACT_GU=1` onto `0003` (with merged `settings-register.json`) | **Bit-exact** | Apply after `0003` (replaces `0000` in the full stack). |

```bash
git clone https://github.com/Niko1221/Strata.git && cd Strata
git checkout 2af30ccaa0729177c4725ee2073f72bf550e2f86
git am /path/to/strata-rdna2-gfx1030-recipe/patches/v2/000[1-4]-*.patch
```

Note: `patches/engine/*.patch` (for Strata `v0.1.42`) are preserved untouched for historical reproducibility; upstream `2af30ccaa` already includes `#1151` (`STRATA_SELECT_SIMT`) and `#1167` (`STRATA_ROCBLAS_TUNING`). All patches carry Strata's MIT license.
