# Tried and rejected on gfx1030 + 64 GB

Measured on the machine in `hardware.md`. "Rejected" means it was slower, unstable or did not run here; it may still help on other hardware.

| What | Result |
|---|---|
| `--resident-budget-gib 32` (pin experts in RAM) | MemAvailable fell to 6.5-9.9 GiB, warm 9.7K +55% slower (21-23 s vs 14 s), warm 19.8K and 119K ended in HTTP 503 / timeouts, boot 3x longer. Pinned memory blocks the page cache from giving memory back. Lower budgets (16-24 GiB) are not recommended either. |
| Decode bundle: `Q8_PACKED`, `Q6_PACKED`, `MMVF_ROWS`, `ATTN_LANECELL`, `EXPERT_V2`, `TSUM`, `LFUSE`, `GDN_SPLIT`, `QFUSE`, `PLE_BATCH` | No decode gain (49-51 either way), warm prefill consistently -4 to -7%. The gains reported on gfx1151 did not carry over. |
| `STRATA_PF_PAD=1` + `STRATA_PF_GEMM=1` | Boots, then every request returns 503. Does not run on this card. |
| `--kv-resident 20480` / `32768` | Decode -18 to -21% and RAM pressure |
| `--adapt-swaps 192`, `--adapt-every 2` | Decode dropped |
| `STRATA_ROUTE_TAIL_SKIP=7` | Within noise |
| `STRATA_SH_STREAM=1` | No effect |
| `STRATA_HC_PERSIST=1` | On hold, not adopted |
| `STRATA_HIP_ADAPT_KERNEL_COPY` | Not in the 0.1.42 source (added in 0.2.x) |
| QSA K8V4 path | Withdrawn after measurement |
| Conversation cache | Promoted, then withdrawn in favour of `STRATA_PREFILL_CPU_SHARE=auto` |
| `--kv-grow` | Not available in the HIP build |

General lesson for this machine: any setting that takes more RAM away from the page cache lost. With 64 GB the remaining big levers are more RAM, a newer engine, or more VRAM.
