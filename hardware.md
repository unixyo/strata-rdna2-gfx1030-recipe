# Hardware and software

Everything in this repository was measured on one desktop. Numbers from other machines are not mixed in.

| Part | Value |
|---|---|
| GPU | AMD Radeon RX 6900 XT 16 GB (Navi 21, gfx1030), PCIe 4.0 x16 from the CPU |
| CPU | AMD Ryzen 7 7800X3D (8 cores / 16 threads) |
| RAM | 64 GB DDR5 (2 x 32 GB), run at 5200 MT/s, no EXPO profile |
| Board | MSI MAG B650 TOMAHAWK WIFI |
| Storage | PCIe 4.0 NVMe. Experts on one drive (KIOXIA EXCERIA PRO), PLE table on another (WD SN850X) |
| OS | Ubuntu 26.04.1 LTS, kernel 7.0 |
| ROCm | AMD TheRock `gfx103X-all` 10.0.0 tarball, unpacked in a user directory (HIP 7.15.26333). The system ROCm was not replaced. |
| Engine | Strata v0.1.42 + the patches in `patches/engine/` |
| Model | ISTA-DASLab SC117 `Qwen3.8-Flash-Next-GSQ-RCO` abliterated IQ3_XXS (experts.bin 39.97 GiB) |

## Build

```bash
source <rocm10-gfx103X>/env.sh        # sets ROCM_PATH, HIP_PATH, PATH, LD_LIBRARY_PATH for this shell only
cmake -S . -B build-hip-gfx1030 \
  -DCMAKE_BUILD_TYPE=Release \
  -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF \
  -DCMAKE_HIP_ARCHITECTURES=gfx1030 \
  -DSTRATA_NATIVE_EXPERTS=ON -DSTRATA_PREFILL_MMQ=ON
cmake --build build-hip-gfx1030 -j
```

These are the cache values of the build that produced the measured binary. Other options were left at their defaults.

## Why the memory size matters

The machine has 64 GB of RAM. The IQ3_XXS experts (about 40 GiB) fit in the page cache; the IQ3_S experts (about 47 GiB) do not fit well, and that alone explains most of the IQ3_XXS vs IQ3_S gap in `results/`. Every setting that pinned more RAM was slower here (see `rejected.md`).
