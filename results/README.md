# Results

All numbers are tokens per second on the machine in `hardware.md`, measured in October 2026 through the Strata server (OpenAI-compatible API). "Warm" means the expert pages were already in the page cache; "fresh" means no prefix was reused. Each A/B ran the two arms in A-B-B-A order with a new server start per arm unless stated otherwise. Most cells come from two to four runs, so treat differences under about 3% as noise.

## Before and after (one day of changes, 2026-10-24)

| | Before | After |
|---|---|---|
| Model | IQ3_S | IQ3_XXS |
| Context | 147,456 (144 Ki), int8 KV | 262,144 (256 Ki), k8v4 KV |
| Prefill, 9.7K fresh | 382-414 | about 1,200-1,300 |
| Prefill, 119K fresh | 954-972 | about 1,240-1,300 |
| Decode, short follow-up requests | 26-37 | 50-64 |

For comparison, the RDNA2 section of Strata's `docs/AMD_HIP.md` reports an RX 6900 XT on engine 0.1.30 at 330-339 tok/s prefill (8K/16K) and 38-42 tok/s decode. That machine and setup differ from this one.

## Step by step

| Step | Change | Measured effect |
|---|---|---|
| 1 | Backport of upstream PR #3381 (`STRATA_PROMPT_ATTN_RDNA2=1`, int8 KV, IQ3_S, 144K) | 9.7K 382.0 -> 414.2 (+8.4%); 19.8K 376.6 -> 365.0; 119K 972.4 -> 956.1 (within noise, B had 2 runs, A had 1) |
| 2 | IQ3_S -> IQ3_XXS, warm 147K | 9.7K 345-579 -> 1,200-1,217; 119K 734-1,112 -> 1,242-1,302; decode 22-41 -> 40-45; expert slots 3,408 -> 4,184 |
| 3 | int8 KV -> k8v4 KV at 192K (IQ3_XXS) | Same speed (prefill 1,113-1,241, decode 41-51); expert slots 3,737 -> 4,068. With k8v4 the #3381 kernel falls back to the split path; no speed change was seen. |
| 4 | Context 144K -> 256K (IQ3_XXS, k8v4) | Boots and runs at 262,144. Slots 144K 4,184, 192K 4,068, 224K 3,825, 256K 3,584. 119K fresh prefill stays near 1,200. Decode at 256K about -10% (37-42). |
| 5 | `STRATA_GDN_HEAD=1 STRATA_GDN_PP=2` | 339-token follow-up +11.9%, 119K +5.8%, 9.7K/19.8K unchanged. Operator alone: about 2x for chunks of 64 tokens or more, slower below 32 tokens (absolute loss about 0.01 ms). |
| 6 | `STRATA_GDN_CONVL2=1 STRATA_GDN_NOY=1 STRATA_CVEC_FUSE=1` | Warm 9.7K +5-8%, 19.8K equal or better, 119K and decode unchanged |
| 7 | `STRATA_ROUTE_RESIDENT=1.0` | Decode +8-18% on short requests (44.8-49.2 -> 54.2-64.6), prefill unchanged (1,226-1,309). **This switch changes the output.** A five-question probe at temperature 0 matched the baseline, but that probe only checked substrings, so it is a narrow check, not a quality guarantee. A later sampled recheck (temperature 1.0, one boot per arm) gave 43.9 tok/s on vs 40.6 off, with a small difference in strict-JSON answers; cause and effect were not established. |
| 8 | `--spec-min-p 0.7` | Chosen on a temperature-0 repeat benchmark |
| 9 | `STRATA_PREFILL_CPU_SHARE=auto` | Sampled A/B on a real-use request pattern: whole-turn time -17%, short reads -9 to -12% |
| 10 | `STRATA_IO_PREFETCH=1 STRATA_IO_PF_AHEAD=0 STRATA_IO_PF_STAGE=0` (demand-only pread) | **Not proven.** Median short-turn API time 4.296 s vs 4.315 s. The unscored 60K warm-up dropped from about 109 s to 63-69 s. Kept as a reversible experiment. |

Step 1 note: the #3381 kernel needs int8 KV. From step 3 on the config uses k8v4, so `STRATA_PROMPT_ATTN_RDNA2=1` in the example config has no effect (it is harmless and left in).

Step 8 note: `--spec-min-p 0.7` was picked at temperature 0, while the server samples at temperature 1.0. Upstream setup uses 0.5. Sampled runs here only compared 0.5 with 0.65, so 0.7 has not been checked under sampling.

## Settings in the example config without a measured effect here

These came over from earlier engine versions or from upstream advice. They have no A/B on the final setup.

| Setting | Why it is there | Evidence |
|---|---|---|
| `--short-read 0` | On 0.1.40.1 the default `short_read=64` turned a reply after a 15-token fresh tail into a repetition loop | One incident on 0.1.40.1; not rechecked on 0.1.42. Cost: a 41-token tail took about 2 s instead of under 1 s |
| `--mtp-window 8192` | Faster than 32768 at 64K context | 0.1.40.1, IQ3_S, two pairs (49.5/48.1 vs 45.8/39.0 tok/s); not rechecked at 256K |
| Korean MTP draft vocabulary (65,536 ids) | Smaller draft head, more expert slots, better acceptance on Korean | 0.1.40.1, IQ3_S, short tasks: 37.9 -> 43.9 tok/s (+15.7%); not rechecked on IQ3_XXS |
| `STRATA_IQ_MT_MIN=1` | Upstream opt-in that makes CPU expert output independent of how many drafts a window holds | Upstream notes -1 to -3% decode on AVX-512. A-B-B-A here (2026-10-31, 1 vs the default 2, 6 turns per boot, temperature 1.0): median decode 34.1 vs 34.5 tok/s, same total turn time, quality 7/8 vs 8/8. No difference beyond noise. That run had other desktop apps open and read 1-3.6 GB from disk per turn, so the CPU share of decode was smaller than on an idle machine |
| `GPU_PINNED_MIN_XFER_SIZE` | Carried over from an earlier audit | No isolated measurement |

## Real-use request shape

A re-analysis of 1,754 requests from this server: 93.8% of all prompt tokens were reused prefix, the median fresh read was 237 tokens, 85% of reads were under 2K tokens and 2.2% were over 100K (compaction). That is why short-read and decode numbers matter more here than long-prompt peaks.

## VRAM at 256K (from the boot log)

| Part | Size |
|---|---|
| Expert cache (3,581 slots) | 5.84 GiB |
| KV cache (256K, k8v4) + dense weights + buffers | about 7.2 GiB (by subtraction) |
| strata-vision (separate process) | 1.39 GiB |
| MTP draft layer | 1.06 GiB |
| Verify buffers + draft head | 0.18 GiB |
| Free | about 0.28 GiB |

The prompt path's "borrows 2,996 slots" line is not a separate allocation; it reuses expert-cache slots for the prefill chunk.

## Not verified

- End-to-end answer quality of IQ3_XXS, k8v4 and the 256K (beyond native range) setting.
- Long-term stability, tool calls and vision quality under real clients.
