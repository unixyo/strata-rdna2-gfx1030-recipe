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
