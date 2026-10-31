# Strata on RDNA2 (gfx1030): a recipe for one RX 6900 XT + 64 GB RAM

[한국어](README.ko.md)

This repository records how [Strata](https://github.com/Niko1221/Strata) was tuned to run Qwen3.8-Flash-Next on a single **AMD Radeon RX 6900 XT 16 GB** with **64 GB of RAM** under Linux (ROCm). Strata's own documentation lists the RX 6000 packages as "not tested on a real card" and asks RX 6000 owners for reports; this is one such report, with the settings, patches and measurements in one place.

**Result on this machine:** about 1,200-1,300 tok/s prefill on fresh 9.7K-119K prompts, 50-64 tok/s decode on short follow-up requests, 256K context, vision on. The same box started the day at 382-414 tok/s prefill (9.7K) and 26-37 tok/s decode.

| | |
|---|---|
| [`hardware.md`](hardware.md) | The machine, ROCm build, engine build flags |
| [`results/`](results/README.md) | Every change with its measured effect, VRAM breakdown, real-use request shape |
| [`rejected.md`](rejected.md) | What was tried and lost on this hardware |
| [`config/engine.example.json`](config/engine.example.json) | The server config with paths replaced by placeholders |
| [`patches/`](patches/README.md) | Five engine patches on Strata v0.1.42 (three backport upstream PRs) and a server patch |

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
