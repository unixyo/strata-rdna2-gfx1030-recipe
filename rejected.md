# Tried and rejected on gfx1030 + 64 GB

Measured on the machine in `hardware.md`. "Rejected" means it was slower, unstable or did not run here; it may still help on other hardware.

| What | Result |
|---|---|
| `--resident-budget-gib 32` (pin experts in RAM) | MemAvailable fell to 6.5-9.9 GiB, warm 9.7K +55% slower (21-23 s vs 14 s), warm 19.8K and 119K ended in HTTP 503 / timeouts, boot 3x longer. Pinned memory blocks the page cache from giving memory back. Lower budgets (16-24 GiB) are not recommended either. |
| Decode bundle: `Q8_PACKED`, `Q6_PACKED`, `MMVF_ROWS`, `ATTN_LANECELL`, `EXPERT_V2`, `TSUM`, `LFUSE`, `GDN_SPLIT`, `QFUSE`, `PLE_BATCH` | No decode gain (49-51 either way), warm prefill consistently -4 to -7%. The gains reported on gfx1151 did not carry over. Measured as one bundle, not switch by switch. Notes from the source: `EXPERT_V2` only acts on IQ3_S gate/up, so it does nothing on IQ3_XXS layers; `Q8_PACKED` and `Q6_PACKED` allocate a second VRAM copy of the packed weights, which takes room from the expert cache (a likely, unconfirmed cause of the prefill loss). `MMVF_ROWS` alone was 9-43% slower than the default kernel on its own benchmark (bit-identical output). |
| `STRATA_PF_PAD=1` + `STRATA_PF_GEMM=1` | Boots, then every request returns 503. Does not run on this card. |
| `--kv-resident 20480` / `32768` | Decode -18 to -21% and RAM pressure |
| `--adapt-swaps 192`, `--adapt-every 2` | Decode dropped |
| `STRATA_ROUTE_TAIL_SKIP=7` | Within noise |
| `STRATA_SH_STREAM=1` | No effect |
| `STRATA_HC_PERSIST=1` (backport of the upstream persistent HC kernel) | On hold, not adopted. The operator alone was 1.35-2.1x faster (bit-identical), but a whole-model A-B-B-A (one run per cell) showed no repeatable decode gain. By the share of the decode window it touches, the ceiling is about 3%. The backported runtime path also has no fail-closed handling when its grid barrier times out. |
| `STRATA_HIP_ADAPT_KERNEL_COPY` | Present in 0.1.42 (upstream #884). It is a workaround for an SDMA stall during adaptive swaps, not a speed switch. Not used here. |
| QSA K8V4 prompt attention (lets the #3381 kernel read k8v4 KV) | Withdrawn. The attention stage was 24-28% faster and the kernel output matched, but whole-request 119K prefill stayed in the old band (about 1,319 vs 1,258-1,316 tok/s), and the first cold 119K request after promotion died with a GPU memory fault (page not present, HTTP 503). That is the only GPU fault in this server's logs. |
| Conversation cache | Promoted, then withdrawn in favour of `STRATA_PREFILL_CPU_SHARE=auto` |
| `--kv-grow` | Not available in the 0.1.42 HIP build. Upstream added a HIP path in 0.2.0-beta; not tested here. |

General lesson for this machine: any setting that takes more RAM away from the page cache lost. With 64 GB the remaining big levers are more RAM, a newer engine, or more VRAM.

## 2026-11-26 additions (Strata `2af30ccaa` / v0.2.21.1)

| What | Result |
|---|---|
| `STRATA_IO_PREFETCH=0` | Severe cold-decode regression (`19.9 tok/s`, `CPU 97.2 ms/win`, `124,952` major faults for `519.6 MB`). Disabling `STRATA_IO_PREFETCH` turns off `io_fill_` 1.6 MiB demand `pread`s even when `PF_AHEAD=0`. Always keep `STRATA_IO_PREFETCH=1 STRATA_IO_PF_AHEAD=0 STRATA_IO_PF_STAGE=0`. |
| `STRATA_SPEC_COST=1` | Cold-miss windows (`70–80 ms`) poisoned its per-width EMA cost estimates for `T=5,6`, leaving `avgT = 2.30–2.48` (slower than fixed `--spec 4` `3.06–3.62`) even after VRAM warmed up. Replaced by `STRATA_MTP_ADAPT`. |
| `STRATA_EXPERTS_SEQ_READAHEAD=1` (`MADV_SEQUENTIAL`) alone | Insufficient under ~31 GiB available RAM (`4k_r1` `43.4 s` / `1.06M` major faults, `16k_r1` `92.5 s` / `2.12M` faults) because buffered readahead still thrashes the LRU page cache across a 40 GiB scan. |
| `STRATA_ADAPT_OVERLAP=1` with `STRATA_SKIP_ZERO_PCIE=1` | Automatically disabled by the engine when on-device residency planning is active. |
| `STRATA_PF_DIRECT_HYBRID=1` at 12 stager threads | Sustained ~6.89 GB/s scanning coincided with a KIOXIA EXCERIA PRO NVMe controller drop (`CSTS=0xffffffff`, `-19 ENODEV`). Lowered default to **4 threads** (`6,598 MB/s` = 95.8% peak, 1/3 queue depth), made `copy_blob_hybrid`/`Prefill::Stager` **fail-closed** on `EIO`/`ENODEV`/`ENXIO`, added continuous read-only sysfs watchdog (`scripts/nvme_watchdog.py`), and removed swap from the model SSD. |
| `STRATA_LM_I8=1` with `--spec 6`, `--vision`, and `--vram-reserve-mib 768` | Left `736 MiB` free VRAM after graph capture (50 MiB short of the `786 MiB` 16K super-chunk threshold), silently falling back to chunk-major. Raising to `--vram-reserve-mib 896` leaves `874 MiB` free and reliably activates `LM_I8` (with `--vision` OFF, `768` left `888 MiB` free). |
| `STRATA_IQ4NL_PAIR_ROWS=1` (CPU IQ4_NL down two-row; experimental, not in `patches/v2/`) | Bit-exact, but multi-core 7-worker pool A/B regressed down-phase time by **+5.99% slower** (`1.852 -> 1.963 ms`). Not adopted. |

## 2026-11-27 additions (Strata v3 exact-kernel study)

| What | Result |
|---|---|
| QSA paired-score attention candidate | Bit-exact, but regressed `n_q=256` to **0.866×** (resident) / **0.822×** (masked). Removed from production flags (diagnostic only). |
| OWN-I8 `64×64` smaller tile (`STRATA_I8_TM=9`) | Raised queried occupancy `1 → 2`, but lost data reuse / arithmetic intensity and ran **19.45–26.52% slower**. Replaced by `STRATA_I8_RDNA2_SINGLE=1` (keeps `128×128` tile, halves LDS buffers). |
| `STRATA_I8_RDNA2_SINGLE=1` combined with `STRATA_I8_RDNA2=1` | On large 128-group cache-exceeding weights (`IQ3_XXS / Q2_0`), enabling both regressed by **-2.21%** (`0.9784×`). Keep `STRATA_I8_RDNA2=0` when enabling `STRATA_I8_RDNA2_SINGLE=1`. |
| Unconditional `STRATA_EXP_MODE=10` `TN=1` / global `STRATA_NO_MMVQ_ROWS2` | `TN=1` regressed `2+`-entry groups to **0.45–0.79×** (restricted to `max_group_entries==1` supported pairs); global 1-row MMVQ regressed `Q8_0` out / `Q3` projections and large `Q6_K` `NC=5` (restricted to measured `Q6_K` `K=2560` geometries). |
