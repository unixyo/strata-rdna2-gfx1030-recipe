# Patches

## `engine/` (apply on Strata `v0.1.42`, in order)

| Patch | What it does |
|---|---|
| 0001 | Ports the local RDNA2 runtime guards onto 0.1.42, and adds a soft Han-character penalty to the native sampler (`han_penalty`, bitset in `src/kernels/cuda/han_soft_mask.inc`, generator `tools/han_soft_mask.py`). The penalty only marks tokens whose decoded text contains Han characters; Korean, emoji and byte-fallback pieces are left alone. Useful when a Korean conversation drifts into Chinese characters. |
| 0002 | Backport of [Strata PR #1151](https://github.com/Niko1221/Strata/pull/1151) by @Vop3p: gfx1030 QSA select SIMT tiling (`STRATA_SELECT_SIMT=1`) |
| 0003 | Backport of [Strata PR #1167](https://github.com/Niko1221/Strata/pull/1167) by @Vop3p: rocBLAS-tuned FP16 prefill GEMMs for gfx1030 (`STRATA_ROCBLAS_TUNING`, table in `tools/hip/`, tuner `tools/hip/tune_rocblas.cpp`) |
| 0004 | Provenance notes for the rocBLAS table |
| 0005 | Backport of [Strata PR #3381](https://github.com/Niko1221/Strata/pull/3381) by @Vop3p: `STRATA_PROMPT_ATTN_RDNA2` one-block online-softmax prompt attention for gfx103x with int8 KV |

The three backported changes are @Vop3p's work. On 2026-10-30 #1151 and #1167 were closed without a merge and #3381 was still open. Each patch's commit message links the original PR.

```bash
git clone https://github.com/Niko1221/Strata.git && cd Strata
git checkout v0.1.42
git am /path/to/strata-rdna2-gfx1030-recipe/patches/engine/*.patch
```

Checked on 2026-10-30: all five apply with `git am` on a clean `v0.1.42` export. Commit authors show who made the local commit (a placeholder identity for 0001-0004), not who wrote the backported change.

## `serve/` (apply after the engine patches)

`0001-serve-repeat-cycle-guard-and-han-penalty.diff` changes `serve/server.py` and its tests: a repeat-cycle guard (stop or restart the engine when the output loops), reasoning-loop recovery, a stall warning, and the `han_penalty` request field.

## What is not included

- The measured binary was built from these commits plus a few uncommitted, opt-in diagnostic switches (`STRATA_PHASE_IO`, `STRATA_WINDOW_TRACE`, `STRATA_POOL_PHASE_TIMING`, `STRATA_IO_PF_GATE`, `STRATA_PCIE_MMAP_BOUNCE`). None of them is set in `config/engine.example.json`, so they are left out.
- Local benchmark scripts and promotion manifests.

Upstream Strata is MIT licensed; these patches are derived from it and carry the same license.
