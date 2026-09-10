# docs/workload-mooncake-context-length-f6.md — F6: options for a decision

**Date:** 2026-09-10 · **Milestone:** M2 · **Falsifier:** F6
**STATUS: AWAITING USER DECISION. No option has been adopted.**

---

## The problem in one paragraph

Mooncake is our **primary** trace (`PROJECT_SPEC.md` §7) and the evidence base for
**RQ1**. Its requests are long: median 7 255 tokens, p95 40 056, max 126 527. In
M1, running it against a 4 096-token model crashed after 18 minutes of simulation
with `AssertionError: num_new_tokens ... got -24844`. Every way of making it fit
distorts the prefix-sharing structure RQ1 measures — so this is a research
decision about the workload, not a configuration detail.

---

## Measured consequences of each option

All figures from our re-derived trace (12 031 requests, block size 512).
**Baseline: realised prefix sharing 38.19 %.** "Δ" is the change in realised
sharing caused by the option — i.e. **how much the option distorts the
independent variable of RQ1**.

### Option A — DROP requests that exceed a context budget

| Budget | Requests kept | Realised sharing | Δ |
|---|---|---|---|
| 4 096 | 3 873 (32.2 %) | 58.41 % | **+20.22 pp** |
| 8 192 | 6 461 (53.7 %) | 42.35 % | +4.16 pp |
| 16 384 | 9 206 (76.5 %) | 39.11 % | +0.92 pp |
| 32 768 | 11 185 (93.0 %) | 39.59 % | +1.40 pp |

Long requests are the ones that share the most, so dropping them **inflates**
measured sharing. At a 4 k budget we would throw away two-thirds of the trace and
report a workload that shares 20 points more than Mooncake does.

### Option B — TRUNCATE prompts to fit (keep every request)

| Budget | Requests kept | Realised sharing | Δ |
|---|---|---|---|
| 4 096 | 12 031 (100 %) | 51.13 % | **+12.94 pp** |
| 8 192 | 12 031 (100 %) | 44.55 % | +6.36 pp |
| 16 384 | 12 031 (100 %) | 40.78 % | +2.59 pp |
| 32 768 | 12 031 (100 %) | 39.24 % | **+1.05 pp** |

Keeps every request and every arrival, and distorts less than A at the same
budget — truncation removes the *tail* of a long prompt, and reuse concentrates
in prompt *heads*.

### Option C — SCALE all token counts down by a constant factor

| Factor | Max total tokens | Realised sharing | Δ |
|---|---|---|---|
| ×0.25 | 31 631 | 48.96 % | +10.77 pp |
| ×0.125 | 15 815 | 60.07 % | +21.88 pp |
| ×0.0625 | 7 907 | 76.32 % | **+38.13 pp** |

**Worst of the three, and it gets worse the harder you scale.** Shrinking token
counts while keeping the block-hash chains raises the shared fraction of every
request. At ×0.0625 the workload shares twice what Mooncake does. Not viable.

### Option D — Use a model whose profiling data already covers long contexts

The M1 spike concluded that no shipped model configuration has a large enough
context. That was **true of the declared `max_model_len` values and wrong about
the profiling data**, which is the thing that actually determines whether the
timing model is trustworthy. Surveying all 22 shipped profile bundles:

| Model | Device | max `prefill_chunk_size` | max `kv_cache_size` |
|---|---|---|---|
| **`meta-llama/Meta-Llama-3-8B`** | **a100** | 4 096 | **262 112** |
| **`meta-llama/Meta-Llama-3-8B`** | **h100** | 8 192 | **262 112** |
| **`meta-llama/Meta-Llama-3-70B`** | **a100** | 4 096 | **262 112** |
| **`meta-llama/Meta-Llama-3-70B`** | **h100** | 8 192 | **262 112** |
| every other model (Llama-2, Qwen-72B, CodeLlama, InternLM, phi-2) | all | 4 096 | 4 032 |

The two numbers mean different things. With chunked prefill, a long prompt is
processed in chunks bounded by `prefill_chunk_size`; what grows with context is
the **KV cache**, and for the Llama-3 models that is profiled to **262 112
tokens** — comfortably past Mooncake's 126 527-token maximum.

The M1 spike used `Llama-2-7b-hf`, whose KV profiling stops at 4 032. That is why
4 096 was the real ceiling, and why it looked like a universal limit.

**Distortion: 0 pp.** No requests dropped, no prompts truncated, no scaling.

Vidur's own `main` README points the same way: *"All models support a maximum
context length of 4k except Llama3-8B and Llama3-70B which support 16k context
length by passing additional CLI params."*

---

## Recommendation

> **Option D — run Mooncake at native lengths on `meta-llama/Meta-Llama-3-8B`,
> raising `max_model_len` to cover the trace, using the shipped a100/h100
> profiles whose KV coverage already extends to 262 112 tokens.**
>
> Keep **Option B at 32 768** as the documented fallback (+1.05 pp, 100 %
> retention) if D proves unworkable at M4.

Why D over the rest: it is the only option that distorts the independent variable
of RQ1 by **nothing at all**, and its timing model stays inside profiled data
rather than extrapolating. A, B and C all trade fidelity for fit; D pays in
compute instead.

### What Option D costs — stated honestly

1. **A larger predictor grid, and we do not know how much larger.** Vidur
   precomputes prediction tables over a grid bounded by max KV cache and max
   chunk size. On `Llama-2-7b-hf` at 4 k this took a `measured` **4 h 37 m**
   one-time fit producing a 235 MB cache. Extending KV coverage toward 128 k
   could raise that substantially — the grid steps in
   `kv_cache_prediction_granularity` (default 64), so naively ~32× the KV rows.
   This is falsifier **F2** territory: peak RSS was already 4.02 GB on a 7 GB
   machine. **`estimate`, low confidence — this must be measured at M4 before D
   is relied on.**
2. **It changes the model under study** from Llama-2-7B to Llama-3-8B. Not a
   problem — nothing in `PROJECT_SPEC.md` fixes the model — but it should be a
   stated choice rather than a side effect, and it means the M1 spike's timings
   do not transfer.
3. **`max_model_len` would be raised above what upstream declares.** Justified by
   the profiling data, but it is a change to a vendored constant, so it belongs
   in our own config layer, never as an edit inside `simulator/vendor/`
   (`PROVENANCE.md` rule).
4. **Unverified end-to-end.** No long-context run has been executed. Verifying it
   is M4 work; running it now would be a simulator experiment, which M2 excludes.

### What would make me change this recommendation

- The M4 predictor fit for Llama-3-8B at extended KV proves infeasible on
  available hardware (F2 fires) → fall back to **B at 32 768**.
- The Llama-3 KV profile turns out to be sparse or synthetic at the top of its
  range rather than genuinely measured → fall back to **B at 32 768**.

---

## The decision requested

Please pick one:

| | Option | Distortion | Cost |
|---|---|---|---|
| **D** | Llama-3-8B, native lengths *(recommended)* | **0 pp** | unquantified predictor-fit time; changes model to Llama-3-8B |
| **B32** | Truncate to 32 768, any model | +1.05 pp | cheap; discards long-prompt tails |
| **A32** | Drop >32 768 | +1.40 pp, loses 7 % of requests | cheapest |
| **B16 / A16** | Same at 16 384 | +2.59 / +0.92 pp | cheaper still |
| — | Something else | — | — |

Until you choose, `load_mooncake` applies **no filtering and no scaling** by
default, and records any that is applied in the workload manifest. The
independent M2 work — schema, loaders, generator, tests — does not depend on this
decision and is complete.
