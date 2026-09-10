# docs/workload-mooncake-context-length-f6.md — F6: corrected analysis

**Date:** 2026-09-10 (rev 2, after user audit) · **Milestone:** M2 · **Falsifier:** F6
**STATUS: AWAITING USER DECISION. No option adopted. Native Mooncake unchanged.**

> **Revision note.** Rev 1 of this file recommended "Option D — raise
> `max_model_len` on Meta-Llama-3-8B". A user audit found six errors in it. All
> six were real. This revision corrects them and reaches a **different**
> recommendation. Rev 1's reasoning is not preserved here because it was wrong,
> not merely superseded; what was wrong and why is recorded in `NOTEBOOK.md`
> (2026-09-10, "F6 rev 2").

---

## 1. Is Option D a real model, or a hypothetical one?

**Rev 1 proposed a hypothetical model and did not say so.** Released
Meta-Llama-3-8B has a context window of **8 192** tokens. Raising
`max_model_len` to 131 072 would simulate a model that does not exist, and
`PROJECT_SPEC.md` §11's honesty rules do not permit that to pass unlabelled.

Raising `max_model_len` alone is indeed insufficient — you were right. But there
is a legitimate model behind the same numbers.

**Llama-3.1-8B is real, released, and architecturally identical.** Comparing
Vidur `canary`'s `Llama3_8BModelConfig` against the published Llama-3.1-8B
`config.json` (from LLMServingSim's model catalogue):

| Parameter | Vidur `Meta-Llama-3-8B` | Llama-3.1-8B | Match |
|---|---|---|---|
| `num_layers` / `num_hidden_layers` | 32 | 32 | ✓ |
| `embedding_dim` / `hidden_size` | 4 096 | 4 096 | ✓ |
| `num_q_heads` / `num_attention_heads` | 32 | 32 | ✓ |
| `num_kv_heads` / `num_key_value_heads` | 8 | 8 | ✓ |
| `mlp_hidden_dim` / `intermediate_size` | 14 336 | 14 336 | ✓ |
| `rope_theta` | 500 000 | 500 000 | ✓ |
| `vocab_size` | 128 256 | 128 256 | ✓ |
| **`max_position_embeddings`** | (config says 4 096) | **131 072** | — |
| `rope_scaling` | — | factor 8 from 8 192 | differs |

Every parameter that determines **FLOPs per token** and **KV bytes per token** is
identical. The only difference is RoPE scaling, which changes positional encoding
— i.e. output *quality* at long context — and affects neither compute cost nor
memory footprint. For a **scheduling** study those are exactly the quantities
that matter, and output quality is out of scope.

**So the corrected proposal is not "extend Llama-3-8B". It is: declare that we
simulate a Llama-3.1-8B-class model, and use the shipped `Meta-Llama-3-8B`
profile as its timing source, stating the substitution.**

### What that still needs

| Need | Status |
|---|---|
| New GPU profiling | **None.** The shipped profile already covers the shapes (§2), within the limits §2 establishes. |
| A config declaring the substitution | Ours, outside `simulator/vendor/` — the vendored tree is never edited (`PROVENANCE.md`). |
| Correctness gate | **M4.** A run must actually complete at long context; none has. |
| Fidelity validation | **M11 / E8.** Compare against real vLLM running Llama-3.1-8B. Until then the substitution is an `assumption`, defensible on architecture but unmeasured. |

---

## 2. What `kv_cache_size` actually means, and its joint coverage

**Rev 1 quoted a column maximum. You were right that this establishes nothing.**

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
        if self.prefill_chunk_size > 0:                            return False
        elif self.kv_cache_size == 0:                              return False
        elif self.kv_cache_size > max_seq_len:                     return False

def is_under_memory_limit(self, max_num_tokens: int):
    return self.batch_size * (self.kv_cache_size + self.prefill_chunk_size) <= max_num_tokens
```

`vidur/profiling/attention/attention_wrapper.py:95-103`:

```python
num_blocks = ceil((num_tokens_per_seq + attention_input.kv_cache_size) / self._block_size)
... SequenceMetadataProxy(
        total_len     = num_tokens_per_seq + attention_input.kv_cache_size,
        processed_len = attention_input.kv_cache_size, ...)
```

**Verdict: `kv_cache_size` is the *per-sequence* already-processed context** — one
sequence's KV length, not aggregate batch tokens. The aggregate quantity is a
*separate* concept, `batch_size * (kv_cache_size + prefill_chunk_size)`, used only
to bound what the profiler was allowed to sweep.

The same field is consumed as a per-sequence quantity on the predictor side: the
grid is built as a `product(batch_size_range, kv_cache_size_range, prefill_chunk_size_range)`
(`sklearn_execution_time_predictor.py:745-779`), so `batch_size` and
`kv_cache_size` are independent axes — which they could not be if `kv_cache_size`
were already aggregated over the batch.

### Joint coverage — the thing the column max hid

`meta-llama/Meta-Llama-3-8B`, all 143 786 rows (a100) / 294 041 (h100):

| Phase | batch_size | prefill_chunk_size | kv_cache_size | joint |
|---|---|---|---|---|
| **Prefill** | 1 only | ≤ 4 096 (a100) / 8 192 (h100) | ≤ 262 112 | **`chunk + kv` reaches 262 144** — jointly covered |
| **Decode** | 1 … 512, complete | 0 | **≤ 65 536** | complete grid, 644 kv values at *every* batch size |

**The binding profiled ceiling is 65 536 tokens of per-sequence context, set by
decode — not the 262 112 rev 1 quoted, which is prefill-only.** Rev 1 took a
column maximum across both phases and reported it as the model's reach. That was
the single largest error in it.

Representative rows confirming the decode grid is dense rather than a sparse tail:
every batch size from 1 to 512 carries exactly **644** distinct `kv_cache_size`
values reaching 65 536.

### Why exceeding 65 536 is a fidelity problem, not just a config one

The *prediction* grid extends to `prediction_max_tokens_per_request = 256*1024`
by default, so Vidur will happily emit predictions for `kv_cache_size` up to
262 144. But the *training data* for decode stops at 65 536. A random forest
cannot extrapolate — beyond its training range it returns the value of the
nearest leaf, i.e. it **flat-lines**. Decode attention cost grows with context,
so predictions above 65 536 would systematically **under-estimate** the cost of
exactly the longest, most expensive requests.

`hypothesis`, to verify at M4 rather than assume: this flat-lining is inferred
from how random forests work, not from a measurement of Vidur's predictor.

---

## 3. Context budget and KV-memory feasibility

**The budget is prompt + generated.** `kv_cache_size` at decode step *t* is
`prefill + t`, so a request's peak context is `num_prefill_tokens +
num_decode_tokens`. Measured on our re-derived trace:

| Threshold | Requests exceeding | Share |
|---|---|---|
| 8 192 | 5 570 | 46.30 % |
| **65 536** (decode profiling ceiling) | **257** | **2.14 %** |
| 131 072 | **0** | **0.00 %** |

Largest request: prefill 126 195 + decode 332 = **126 527**. Largest decode alone:
2 000. So the trace fits inside a 131 072-context model **with no transformation
at all** — and only 2.14 % of it sits outside profiled decode coverage.

### KV memory, computed with Vidur's own `MemoryPlanner`

Llama-3-8B, fp16, 80 GB device, default 10 % memory margin
(`vidur/utils/memory_planner.py`, run against the vendored tree):

| Device | TP | Max KV tokens per replica | Concurrent seqs @126 527 | @65 536 | @8 192 |
|---|---|---|---|---|---|
| a100 / h100 | 1 | 483 328 | **3** | 7 | 59 |
| a100 / h100 | 2 | 1 073 152 | **8** | 16 | 131 |
| a100 / h100 | 4 | 2 252 800 | **17** | 34 | 275 |

**Feasible, but it changes the serving regime.** A TP=1 replica can hold three
maximum-length sequences. At native Mooncake lengths the study would be
characterising routing at batch sizes of single digits for the long tail — a real
operating point, but an unusual one, and it should be a deliberate choice rather
than a surprise discovered at M9.

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

**This does not make C a good option** — see §5. Scaling changes every request's
compute and memory cost, so it preserves the workload's *structure* while
destroying the *timing model's* validity. It is rejected for that reason, not the
one rev 1 gave.

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

## 5. Preserving the trace ≠ validating the timing model

Rev 1 presented "0 pp distortion" as though it settled the question. It does not.
These are independent axes, and Option C is the clean demonstration:

| | Workload preserved? | Timing model valid? |
|---|---|---|
| Consistent scaling (C) | **yes — 0.00 pp, exactly** | **no** — every request's compute and KV footprint is falsified |
| Native lengths, decode beyond 65 536 | **yes — 0.00 pp** | **partially** — 2.14 % of requests fall outside profiled decode data; RF flat-lining would under-estimate their cost |
| Truncate at 65 536 | no — +0.44 pp, 95.8 % of blocks kept | **yes** — every request inside profiled coverage |

"0 pp" establishes only that we did not alter the trace. It says nothing about
whether the simulator can price it.

---

## 6. Corrected recommendation

> **D′ — declare a Llama-3.1-8B-class model (using the shipped
> `Meta-Llama-3-8B` profile, architecturally identical), and truncate the
> workload at 65 536 total tokens.**

Cost: **+0.44 pp** on the sharing ratio, retaining **95.8 %** of prefix blocks and
**96.9 %** of all reuse, affecting **2.14 %** of requests.

Why this is the cheapest defensible path:

1. **It requires no new profiling.** No GPU time, no M3 dependency.
2. **Every request stays inside profiled data**, prefill and decode. No random
   forest is asked to extrapolate.
3. **It distorts less than every option rev 1 listed** except native, and native
   buys its 0 pp by moving 2.14 % of requests outside the timing model's evidence
   — trading a measurable workload distortion for an unmeasurable timing one.
4. **The model substitution is architecturally exact**, not a raised constant.

**Native (no truncation) remains available and is the better answer *if* we later
add decode profiling above 65 536** — that needs GPU time and belongs to M3.
Truncation at 65 536 is reversible; a decision to run native later costs nothing
now.

### Remaining uncertainty, stated

| # | Uncertainty | Status |
|---|---|---|
| U1 | Predictor fit cost for Llama-3-8B. Its a100 attention training set is 143 786 rows vs Llama-2-7b's 58 632 (**2.45×**); h100 is 294 041 (**5.01×**). Against M1's `measured` 4 h 37 m, `estimate` **11–14 h** (a100). The *prediction grid* is unchanged — `prediction_max_tokens_per_request` already defaults to 262 144, giving 2 622 080 rows regardless of model. | **unverified**, F2 |
| U2 | Random-forest flat-lining beyond the training range is inferred from how RFs behave, not measured in Vidur. | **unverified**, M4 |
| U3 | That the `Meta-Llama-3-8B` profile is representative of real Llama-3.1-8B at long context. Architecturally exact; empirically untested. | **`assumption`**, M11/E8 |
| U4 | No end-to-end long-context run has been executed. | **open**, M4 gate |
| U5 | KV memory permits only 3 concurrent maximum-length sequences at TP=1. Real, and it shapes the operating point the study characterises. | **measured**, needs a scope decision |

### On the smoke-test exception you authorised

**I did not use it, and it is not usable within the limits you set.** Any Vidur
run on a new `(model, device)` pair must first fit the execution-time predictor —
`estimate` 11–14 h — which is exactly the full predictor fit you excluded. There
is no cached artefact for Llama-3-8B and no partial-fit mode that would produce a
meaningful answer.

What I did instead, inside the bounds: ran Vidur's own `MemoryPlanner` against
the vendored tree (seconds, negligible memory) for §3, and audited the profiling
data and predictor code directly. The end-to-end run belongs at **M4**, as the
gate on U2 and U4.

### The decision requested

| | Option | Sharing Δ | Blocks kept | Inside profiled data? | New profiling? |
|---|---|---|---|---|---|
| **D′** | Llama-3.1-8B-class + truncate 65 536 *(recommended)* | +0.44 pp | 95.8 % | **yes** | none |
| D-native | Llama-3.1-8B-class, no truncation | 0.00 pp | 100 % | **no** — 2.14 % of requests | none, but needs U2 resolved |
| D-native+ | Native, after profiling decode above 65 536 | 0.00 pp | 100 % | yes | **GPU time at M3** |
| B32 | Truncate 32 768 | +1.05 pp | 85.2 % | yes | none (same model substitution) |
| A/B @8 192 | Fit released Llama-3-8B's real window | +4.16 / +6.36 pp | 13.5 % / 43.2 % | yes | none |

Until you choose, `load_mooncake` applies **no filtering and no scaling**, and
records in the manifest any that is applied.
