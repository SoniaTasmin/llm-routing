# docs/workload-mooncake-context-length-f6.md — F6: corrected analysis

**Date:** 2026-09-10 (rev 3) · **Milestone:** M2 · **Falsifier:** F6
**STATUS: D′ ADOPTED PROVISIONALLY as the workload policy (D-008). Native trace
preserved unmodified. Simulator feasibility and fidelity gates remain OPEN.**

> **Revision history.** Rev 1 recommended raising `max_model_len` on
> Meta-Llama-3-8B; a user audit found six errors and it was withdrawn. Rev 2
> proposed D′ but reported profiling counts that did not reconcile — 512 batch
> sizes × 644 KV values implies 329 728 decode rows against a stated 100 738 —
> and overstated three claims. **Root cause of the arithmetic: I aggregated
> across the `num_tensor_parallel_workers` column without noticing it existed.
> 322 (TP=1) + 322 (TP=8) = the 644 I reported, and 176 distinct batch sizes
> became "512" because I read `prediction_max_batch_size`, a *predictor*
> default, instead of the data.** Rev 3 audits coverage per device and per TP,
> and qualifies the claims. What was wrong and why is in `NOTEBOOK.md`.

---

## 1. Is Option D a real model, or a hypothetical one?

**Rev 1 proposed a hypothetical model and did not say so.** Released
Meta-Llama-3-8B has a context window of **8 192** tokens. Raising
`max_model_len` to 131 072 would simulate a model that does not exist.

There is a legitimate model behind the same numbers. **Llama-3.1-8B is real,
released, 131 072 context.** Comparing Vidur `canary`'s `Llama3_8BModelConfig`
against the published Llama-3.1-8B `config.json`:

| Parameter | Vidur `Meta-Llama-3-8B` | Llama-3.1-8B | Match |
|---|---|---|---|
| `num_layers` | 32 | 32 | ✓ |
| `embedding_dim` / `hidden_size` | 4 096 | 4 096 | ✓ |
| `num_q_heads` | 32 | 32 | ✓ |
| `num_kv_heads` | 8 | 8 | ✓ |
| `mlp_hidden_dim` / `intermediate_size` | 14 336 | 14 336 | ✓ |
| `rope_theta` | 500 000 | 500 000 | ✓ |
| `vocab_size` | 128 256 | 128 256 | ✓ |
| `max_position_embeddings` | config says 4 096; **profile swept at 262 144** | 131 072 | — |
| `rope_scaling` | absent | factor 8 from 8 192 | differs |

### The qualification rev 2 failed to make

Rev 2 called this "architecturally exact" and concluded "timing model valid:
yes, no new profiling needed". **All three claims were too strong.**

What the architecture match establishes: every parameter that determines **FLOPs
per token** and **KV bytes per token** is identical, so there is a principled
reason to expect the timing to transfer. That **supports** the substitution.

What it does **not** establish: that the shipped `Meta-Llama-3-8B` profile
*measures* Llama-3.1-8B's behaviour. It does not. The profile was swept at
`max_model_len = 262 144` on a model whose released window is 8 192 — so it is
already a measurement of *something other than the released model*, most likely
attention kernels driven at shapes the released weights would never produce.
Kernel time is a function of shape, which is why the data is meaningful at all;
but "meaningful" is not "validated".

**Correct status: the Llama-3 profile is an UNVALIDATED TIMING PROXY for a
Llama-3.1-8B-class model.** Recorded as an `assumption` in every manifest that
depends on it.

| Need | Status |
|---|---|
| New GPU profiling | **Unknown, not "none".** No new profiling is required *to run*; whether any is required *to be believed* is what M3/M11 must determine. |
| Config declaring the substitution | Ours, outside `simulator/vendor/` |
| Correctness gate | **M4 — OPEN.** No long-context run has been executed. |
| Fidelity validation | **M11 / E8 — OPEN.** Compare against real vLLM on Llama-3.1-8B. If it fails, additional profiling becomes necessary. |

---

## 2. `kv_cache_size`: semantics, and joint coverage per device and TP

### The quantity, traced through the code

`vidur/profiling/attention/attention_input.py`:

```python
def is_valid(self, max_seq_len: int):
    if self.is_prefill:
        if self.batch_size != 1:                                   return False
        elif self.prefill_chunk_size == 0:                         return False
        elif self.prefill_chunk_size + self.kv_cache_size > max_seq_len:
            return False                     # <-- per-SEQUENCE context bound
    else:
        if self.kv_cache_size > max_seq_len:                       return False

def is_under_memory_limit(self, max_num_tokens: int):
    return self.batch_size * (self.kv_cache_size + self.prefill_chunk_size) <= max_num_tokens
```

`attention_wrapper.py:95-103` sets `total_len = num_tokens_per_seq +
kv_cache_size`, `processed_len = kv_cache_size`.

**`kv_cache_size` is the per-sequence already-processed context.** The aggregate
quantity is separate — `batch_size * (kv + chunk)` — and is used only to bound
what the profiler was permitted to sweep. On the predictor side the grid is a
`product(batch_size_range, kv_cache_size_range, prefill_chunk_size_range)`
(`sklearn_execution_time_predictor.py:745-779`), so the two are independent axes.

### Actual profiling inventory (reconciled)

The profiling CSVs carry a `num_tensor_parallel_workers` column. Rev 2 ignored
it and summed across TPs. Per device and TP:

| Device | TPs present | Rows/TP (prefill + decode) | Device total |
|---|---|---|---|
| **a100** | **1, 8 only** — no TP=2, no TP=4 | TP1: 21 524 + 43 744 = 65 268 · TP8: 21 524 + 56 994 = 78 518 | 143 786 ✓ |
| **h100** | 1, 2, 4, 8 | TP1: 21 860 + 43 733 = 65 593 · TP2: 72 740 · TP4: 76 854 · TP8: 78 854 | 294 041 ✓ |

Both totals reconcile exactly. All rows: `block_size = 16`,
`attention_backend = FLASHINFER`, `max_model_len = 262 144`.

**a100 TP=2 and TP=4 have no timing data at all.** Rev 2's memory table listed
them; that was a MemoryPlanner calculation with no profile behind it.

### Joint coverage — a100 TP=1, the reference configuration for D′

**Decode** — **43 744 rows**, 176 distinct batch sizes. The grid is **not** a
full cross product, and rev 2's "322 KV values each" implied one (176 × 322 =
56 672, against 43 744 actual). Actual structure:

| batch_size | KV values sampled | max kv_cache_size |
|---|---|---|
| 1 – 64 (71 batch sizes) | **320** | **65 536** |
| 96 | 253 | 48 384 |
| 128 | 206 | 36 352 |
| 192 | 158 | 24 064 |
| 256 | 135 | 18 176 |
| 384 | 111 | 12 032 |
| 512 | 99 | 8 960 |

Reconciliation: summing distinct `(batch, kv)` pairs gives **43 184**; the file
holds 43 744 rows, so **560 pairs are repeated measurements**, which
`_load_attention_df`'s `drop_duplicates()` collapses only when the whole row
matches. Row counts and pair counts are different quantities and are now
reported separately.

**Directly sampled vs. interpolated.** The 320 KV values at batch ≤ 64 are not
uniformly spaced: step 32 for the first 31 intervals, then 64 for 48, then 256
for the remaining 240 — spanning 32 … 65 536. So a request decoding at, say,
kv = 40 000 sits **between** sampled points and its cost is **interpolated by the
random forest within audited coverage**, not directly measured. That is a normal
and intended use of the predictor — it is what the model is for — but it is a
different epistemic status from a measured point, and "inside coverage" should be
read as "inside the convex hull of sampled points", not "measured".

Above batch 64 the sweep is pruned by the aggregate-token limit. **That pruning
is not a gap for us**: MemoryPlanner gives this configuration 483 328 KV tokens,
so every memory-feasible point is inside coverage —

| batch | memory allows kv ≤ | profile covers kv ≤ | covered? |
|---|---|---|---|
| ≤64 | 7 552 (at 64) | 65 536 | ✓ |
| 96 | 5 035 | 48 384 | ✓ |
| 512 | 944 | 8 960 | ✓ |

**Prefill** (batch 1 only, by construction — chunked prefill profiles one
sequence): 17 chunk values from 32 to 4 096. At `chunk = 4 096`, 128 KV values
spanning 0 … 258 048, with `chunk + kv` reaching 262 144 throughout.

Chunk-prefilling a 65 536-token prompt at chunk 4 096 needs KV steps
0, 4 096, …, 61 440 — **16 steps, 0 missing from the profile.**
h100 TP=1 at chunk 8 192: 8 steps needed, 0 missing.

### Verdict on coverage

**For a100 TP=1 (and h100 TP=1/2/4/8, a100 TP=8), a 65 536-token budget is fully
covered in both phases**, across the entire batch-size range memory permits.
The binding profiled ceiling is **65 536 per-sequence, set by decode** — the
262 112 rev 1 quoted is prefill-only.

Above 65 536, the decode training data stops while the *prediction* grid
continues to `prediction_max_tokens_per_request = 262 144`. A random forest
cannot extrapolate; beyond its training range it returns the nearest leaf, i.e.
flat-lines. Decode attention cost grows with context, so predictions above
65 536 would systematically **under-estimate** the longest requests.
`hypothesis`, to verify at M4 — inferred from how random forests behave, not
measured in Vidur.

---

## 3. Context budget and KV-memory capacity

**The budget is prompt + generated.** `kv_cache_size` at decode step *t* is
`prefill + t`, so peak context is `num_prefill_tokens + num_decode_tokens`:

| Threshold | Requests exceeding | Share |
|---|---|---|
| 8 192 | 5 570 | 46.30 % |
| **65 536** | **257** | **2.14 %** |
| 131 072 | 0 | 0.00 % |

Largest request: prefill 126 195 + decode 332 = 126 527. Largest decode alone: 2 000.

### MemoryPlanner-derived capacity — an upper bound, not observed concurrency

`vidur/utils/memory_planner.py`, fp16, 80 GB, 10 % margin. **These are static
capacity ceilings computed from KV bytes per token. They are not measured
serving concurrency**: achieved batch size depends on the arrival process, the
replica scheduler's admission policy, chunked-prefill interleaving and
preemption, none of which this calculation models.

| Device | TP | Profile exists? | Max KV tokens | Seqs @65 536 (**D′ max**) | @8 192 |
|---|---|---|---|---|---|
| a100 | 1 | ✓ | 483 328 | **7** | 59 |
| a100 | 8 | ✓ | (not computed — TP=8 not a candidate config) | — | — |
| a100 | 2, 4 | ✗ **no timing data** | 1 073 152 / 2 252 800 | 16 / 34 | 131 / 275 |
| h100 | 1 | ✓ | 483 328 | **7** | 59 |
| h100 | 2 | ✓ | 1 073 152 | 16 | 131 |
| h100 | 4 | ✓ | 2 252 800 | 34 | 275 |

**For D′ the relevant figure is 7, not 3.** Rev 2 quoted 3, which is the capacity
at the *native* 126 527-token maximum — a workload D′ does not produce. Under
D′ the largest sequence is 65 536 tokens.

Seven concurrent maximum-length sequences at TP=1 is a real constraint on the
operating point, but it applies only to the 2.14 % of requests near the cap;
the median request is 7 255 tokens, where capacity is ~66.

---

## 4. Audit of the transformation analysis

### 4a. B does **not** distort less than A at every budget

Correct. Rev 1 asserted a general ordering; the data contradicts it at 8 192 and
16 384. Corrected table, now with **absolute counts** because the ratio's
denominator changes under every transformation:

| Option | Requests | Blocks | Reused | Ratio | Δ ratio | **Blocks kept** | **Reuse kept** |
|---|---|---|---|---|---|---|---|
| baseline | 12 031 | 276 491 | 105 592 | 38.19 % | — | 100 % | 100 % |
| A: drop >8 192 | 6 461 | 37 266 | 15 782 | 42.35 % | **+4.16** | **13.5 %** | 14.9 % |
| B: truncate 8 192 | 12 031 | 119 580 | 53 276 | 44.55 % | +6.36 | 43.2 % | 50.5 % |
| A: drop >16 384 | 9 206 | 97 551 | 38 155 | 39.11 % | **+0.92** | 35.3 % | 36.1 % |
| B: truncate 16 384 | 12 031 | 184 409 | 75 207 | 40.78 % | +2.59 | 66.7 % | 71.2 % |
| A: drop >32 768 | 11 185 | 182 595 | 72 296 | 39.59 % | +1.40 | 66.0 % | 68.5 % |
| B: truncate 32 768 | 12 031 | 235 609 | 92 445 | 39.24 % | **+1.05** | 85.2 % | 87.5 % |
| A: drop >65 536 | 11 774 | 232 347 | 90 847 | 39.10 % | +0.91 | 84.0 % | 86.0 % |
| **B: truncate 65 536** | **12 031** | **264 919** | **102 342** | **38.63 %** | **+0.44** | **95.8 %** | **96.9 %** |
| A or B @131 072 | 12 031 | 276 491 | 105 592 | 38.19 % | +0.00 | 100 % | 100 % |

**The deeper error rev 1 made was ranking options by Δ ratio at all.** At 8 192,
A has the *smaller* ratio change (+4.16 vs +6.36) while discarding **86.5 %** of
all prefix blocks against B's 56.8 %. A ratio can look stable precisely because
numerator and denominator fell together. Absolute retention is the honest
instrument; the ratio is a secondary check.

### 4b. The sharing metric, stated precisely

`workload.sharing.measure_realised_sharing`:

- **Chronology:** requests in **arrival order**; a block counts as reused only if
  its id was emitted by a **strictly earlier** request.
- **Numerator:** count of prefill blocks whose chained hash id has been seen before.
- **Denominator:** count of **all** prefill blocks emitted, whether reused or not.
- **Partial blocks:** excluded from both. `len(block_hash_ids) == prefill // block_size`;
  a trailing partial block is never hashed and is always recomputed.
- **Decode tokens:** excluded entirely — a router at admission cannot know them.
- **Assumes infinite cache, no eviction.** It is an **upper bound** on any
  achievable hit rate, and characterises the *workload*, not a workload-plus-system.

Because both numerator and denominator change under A and B, cross-option ratio
comparisons are weak. Hence the absolute columns above.

### 4c. Option C's reported distortion was an artifact of an invalid transformation

You were right to suspect this. Rev 1 scaled token counts by `f` but **kept
`block_size = 512` and truncated each hash chain to `prefill // 512`**. That is
not "scaling the trace" — it deletes each request's unique tail blocks while
keeping its shared head, which inflates the ratio mechanically.

Done **consistently** — scaling tokens *and* `block_size` by the same factor, so
chain lengths are preserved:

| Factor | Rev 1's C (block_size fixed) | **Consistent C** |
|---|---|---|
| ×0.25 | 48.96 % (+10.77 pp) | **38.19 % (+0.00 pp)** |
| ×0.125 | 60.07 % (+21.88 pp) | **38.19 % (+0.00 pp)** |
| ×0.0625 | 76.32 % (+38.13 pp) | **38.19 % (+0.00 pp)** |

Sharing is **exactly invariant** under consistent scaling, at every factor. The
+38 pp rev 1 reported was entirely my own transformation error.

**This does not make C a good option, and the reason matters** — see §5.
Two corrections to how rev 2 put it:

- Scaling does **not** destroy the timing model's validity. A scaled request is
  priced correctly for the request it now is. What scaling costs is **external
  validity**: the workload is no longer Mooncake.
- Preserving the sharing **ratio** is not the same as preserving the **trace**.
  Consistent scaling changes every request's prompt length, block size, KV
  footprint and batch occupancy. One summary statistic is invariant; the workload
  underneath it is materially different. Rev 2's "0.00 pp" line invited exactly
  the conflation this document keeps having to correct.

### 4d. "Long requests share the most" — **false**

Rev 1 inferred this from aggregates. Measured directly, per-request reuse
fraction by length quintile:

| Quintile | n | Median total tokens | Mean per-request reuse | Blocks | Reused |
|---|---|---|---|---|---|
| Q1 shortest | 2 406 | 1 343 | **81.84 %** | 3 661 | 2 699 |
| Q2 | 2 406 | 3 635 | 44.41 % | 14 201 | 5 869 |
| Q3 | 2 406 | 7 255 | 37.93 % | 31 861 | 12 206 |
| Q4 | 2 406 | 13 574 | 37.21 % | 61 426 | 23 009 |
| Q5 longest | 2 407 | 27 723 | 38.33 % | 165 342 | 61 809 |

**Short requests share the most**, by a wide margin; Q2–Q5 are flat at ~37–44 %.

The real mechanism is **head/tail**: reuse concentrates in prompt *heads* (a
shared system prompt — every request's first hash id is the same block), and a
short request is almost entirely head. Dropping long requests (A) keeps the
high-reuse short ones; truncating (B) keeps every request's head and discards its
unique tail. Both inflate the ratio, for the same structural reason — and neither
does so because "long requests share more".

### 4e. B32 is not model-agnostic

Correct. Rev 1 wrote "truncate to 32 768, **any model**". Wrong twice: the model
must *declare* ≥32 768 context, **and** have profiles covering it. Of the 22
shipped profile bundles, decode coverage reaches 65 536 only for
`Meta-Llama-3-8B` and `Meta-Llama-3-70B`; **every other model stops at 4 032**.
So B32 requires exactly the same model substitution as D — it is not an
independent, cheaper alternative.

---

## 5. Preserving the trace ≠ validating the timing model — with the right reason

Rev 1 presented "0 pp distortion" as though it settled the question. It does not.
But rev 2's correction was itself sloppy: it wrote "timing model valid: **no**"
for consistent scaling, which is wrong.

**Consistent scaling does not invalidate the timing model.** If every request's
lengths are scaled and the simulator prices the scaled request, it prices it
correctly — the timing model is perfectly valid *for the transformed workload*.
What scaling destroys is **external validity**: the scaled workload is no longer
Mooncake. Its prompts, KV footprints, batch occupancies and prefill/decode ratios
are all different, so it exercises a different operating regime, and conclusions
drawn on it do not transfer to the trace it came from.

The three axes are distinct and rev 1 collapsed all of them:

| | Trace structure preserved? | Timing model valid *for what is simulated*? | Represents Mooncake's operating regime? |
|---|---|---|---|
| Consistent scaling | **ratio only** — the sharing ratio is 0.00 pp, but lengths, block size and resource demands all change, so the *trace* is not preserved | within coverage, if the scaled shapes fall inside it | **no** — different lengths, resource demands, regime |
| Native, decode beyond 65 536 | **yes** — 0.00 pp | **outside audited coverage** for 2.14 % of requests — RF extrapolation | yes |
| **D′ — truncate at 65 536** | mostly — +0.44 pp, 95.81 % of blocks | **within audited profile coverage; timing-proxy fidelity unvalidated** | mostly — alters 2.14 % of requests |

"0 pp" establishes only that we did not alter the trace. Scaling is rejected for
losing the operating regime, not for breaking the simulator.

---

## 6. Recommendation, and what was adopted

> **D′ — simulate a Llama-3.1-8B-class model using the shipped
> `Meta-Llama-3-8B` profile as an *unvalidated timing proxy*, on a workload
> variant truncated to a 65 536-token context budget.**

**Adopted provisionally as the workload policy — see `DECISIONS.md` D-008.**

### Measured result of the adopted transformation

| | Native | **D′ variant** |
|---|---|---|
| Requests | 12 031 | **12 031** (0 dropped) |
| Requests altered | — | **257** (2.14 %) |
| Prefix blocks | 276 491 | 264 919 (**95.81 % retained**) |
| Reused blocks | 105 592 | 102 342 (96.92 % retained) |
| Realised sharing | 38.19 % | 38.63 % (**+0.44 pp**) |
| Arrival times | — | **preserved exactly** |
| Output lengths | — | **preserved exactly** |

### Why this is the cheapest defensible path

1. **Every request sits inside audited profile coverage**, prefill and decode,
   across the whole memory-feasible batch range (§2). No random forest
   extrapolates — though many points are interpolated within coverage rather than
   directly sampled, and the timing proxy itself remains unvalidated (§1).
2. **No new profiling is required to run.** Whether any is required to *believe*
   the result is for M3/M11 to decide (§1).
3. **It distorts less than every alternative except native**, and native buys its
   0 pp by moving 2.14 % of requests outside the timing model's evidence —
   trading a measured workload distortion for an unmeasured timing one.
4. **Reversible.** The native trace is preserved unmodified beside the variant.
   Adding decode profiling above 65 536 at M3 would let us run native later at
   no cost incurred now.

### Remaining uncertainty

| # | Uncertainty | Status |
|---|---|---|
| U1 | **Predictor fit cost — point estimate WITHDRAWN.** Rev 2's "11–14 h" came from whole-device row totals (143 786 / 58 632 = 2.45×). `_load_attention_df` **filters training rows by `num_tensor_parallel_workers`**, so the relevant comparison is post-filter: a100 TP=1 attention **14 650 → 65 268 rows = 4.46×** (compute/mlp rows 261 → 456 = 1.75×). Worse than rev 2 claimed. But no replacement point estimate is defensible either: M1's surviving log was captured with `tail`, so only 4 of 11 trained operations are visible, accounting for ~10 m 43 s of a 4 h 36 m 47 s run. The remaining ~4 h 26 m is **unattributed**. Prediction grid is model-independent (2 622 080 rows). | **not reliably estimable — measure at M4**, F2 |
| U2 | Random-forest flat-lining beyond the training range — inferred, not measured. | **unverified**, M4 |
| U3 | That the Llama-3 profile represents real Llama-3.1-8B at long context. Architecture supports it; nothing measures it. | **`assumption`**, M3/M11 |
| U4 | No end-to-end long-context run performed. | **OPEN**, M4 gate |
| U5 | Achieved batch sizes under D′. §3's figures are static capacity ceilings, not observed concurrency. | **unmeasured**, M4 |

### G4 — block-size mismatch between workload hashes and profiling data

**A compatibility gate found during this pass, not previously recorded.**

Two different block sizes are in play and they are not the same quantity:

| | Value | Set by |
|---|---|---|
| **Workload hash granularity** | **512 tokens** | Mooncake's own `hash_ids`; verified on 12 031 / 12 031 records |
| **Simulator KV block size** | **16 tokens** | `CacheConfig.block_size`, and **forced** by the profiling data |

It is forced, not merely defaulted. `_load_attention_df`
(`sklearn_execution_time_predictor.py:187-200`) filters training rows on

```python
df["block_size"] == self._block_size
```

and **every** shipped attention profile carries `block_size = 16` only. Setting
the simulator's block size to 512 filters the attention dataframe to **zero
rows**, and the predictor has nothing to train on. So 16 is not a tunable here.

**Why this is a correctness gate and not a detail.** `hash_request_tokens`
(`vidur/kv_cache/utils.py`) returns one `BlockHashType` per supplied id when a
request carries `block_hash_ids`. The cache manager then pairs each id with one
`block_size`-token block. Handing it 512-granularity ids while it runs 16-token
blocks would make a 126 195-token prompt with 246 hashes look like
246 × 16 = 3 936 tokens of cacheable prefix — a ~32× under-count of the cached
region. **Silently wrong, in the direction of under-reporting cache benefit,
which is the direction that would bias RQ1 toward "routing sophistication does
not pay".**

**Intended mapping, to be implemented and validated at M4 — not now.**
Expand each 512-token Mooncake hash into 32 derived 16-token ids, deterministically
from the parent id, **for whole 512-blocks only**:

```
child_ids(parent p) = [f(p, 0), f(p, 1), ..., f(p, 31)]        # f deterministic
```

Why this is a sound refinement rather than invention: chained hashes make sharing
a **prefix relation**. If two requests share the first *k* 512-token blocks, their
first 512*k* tokens are identical, so their first 32*k* 16-token blocks are
identical too. The expansion states something the coarse hashes already imply.

Why it is nonetheless **conservative and must be labelled so**: a request's
prompt tail below a 512-token boundary is not hashed upstream, so up to 31 whole
16-token blocks per request carry **no** sharing information. We leave them
unhashed rather than guess. Any sharing in that region is invisible to us, so the
mapping **under-counts** — it never fabricates.

**What we must not do**, and this gate exists to prevent:

- assign shared ids to sub-512 tail blocks — that would invent finer-grained
  sharing the source does not contain;
- assume block size has no timing effect. It demonstrably does: `block_size` is a
  filtered column in the profiling data, and paged-attention kernel time depends
  on page size. Nothing here licenses treating 16 and 512 as interchangeable.

**Gate G4 (M4):** implement the expansion, verify that realised sharing measured
at 16-token granularity on the expanded workload is consistent with the 38.63 %
measured at 512-token granularity, and quantify the conservative bias from the
unhashed tails.

### On the smoke-test exception

**Not used, and not usable within the limits set.** Any Vidur run on a new
`(model, device)` pair must first fit the predictor — the full fit that was
excluded. There is no cached artefact for Llama-3-8B and no partial-fit mode that
answers anything. Inside the bounds I ran Vidur's `MemoryPlanner` (seconds) and
audited the profiling CSVs and predictor code directly. The end-to-end run is the
**M4 gate** on U2, U4 and U5.
