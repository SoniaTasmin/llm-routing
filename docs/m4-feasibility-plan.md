# docs/m4-feasibility-plan.md — bounded M4 feasibility plan, for approval

**Date:** 2026-09-11 · **Milestone:** M4 · **Status: PLAN ONLY. Nothing run.**
**No predictor fit launched. No GPU. No spend.**

M4's job per `MILESTONES.md`: *"Simulator (chosen base) validated against real
single-replica measurements."* With M3 deferred (D-009) there are no new real
measurements, so M4 narrows to what can be established with the **shipped
profiles** and the **D′ workload** — which turns out to be most of the gates.

---

## 1. Gate G4 — mapping specified and measured at the workload level; **NOT resolved**

**The problem.** Mooncake hashes prefixes at **512 tokens**. Vidur's KV block
size is **16**, and it is forced: `_load_attention_df` filters training rows on
`block_size` and every shipped profile carries 16 only, so 512 leaves the
predictor with no data. Passing 512-granularity ids to a 16-token cache makes
each id cover 16 tokens instead of 512 — a **32× under-count** of the cached
region, biased toward making cache-aware routing look worse than it is.

**The mapping.** Implemented as `workload.transforms.expand_block_hashes`:

```
child(h_i, j) = h_i * 32 + j          for j in 0..31,  for each coarse id h_i
```

**Why this invents nothing.** Prefix hashes are *chained*: `h_i` identifies the
whole prefix through coarse block `i`. If two requests agree on their first `k`
coarse ids, their first `512k` tokens are byte-identical, therefore their first
`32k` 16-token blocks are identical too. The expansion states exactly that. The
map is deterministic in `(h_i, j)` alone, so agreement transfers and
**disagreement cannot create agreement** — verified by test
(`test_expansion_does_not_invent_sharing_between_unrelated_requests`).

**What it cannot know, and how that is handled.** A prompt's tail below a
512-token boundary is never hashed upstream, yet contains up to 31 whole
16-token blocks. Their sharing is genuinely unknown. They receive **unique,
never-matching** ids from a disjoint range, so they can never count as reuse.
The mapping therefore **under-counts** sharing; it does not fabricate it.

**Measured workload-level cost of that conservatism** (CPU, today):

| Workload | Blocks after expansion | Tail blocks (unknown) | Sharing @512 | Sharing @16 | Δ |
|---|---|---|---|---|---|
| native | 9 044 013 | 196 301 (**2.17 %**) | 38.19 % | 37.36 % | **−0.83 pp** |
| **D′ (trunc 65 536)** | 8 674 135 | 196 727 (**2.27 %**) | 38.63 % | **37.76 %** | **−0.88 pp** |

### Why this does **not** resolve G4

An earlier version of this section was headed "resolved". **It is not, and the
−0.88 pp does not bound what matters.** It is a property of the *workload*
computed under `measure_realised_sharing`'s stated assumptions: arrival order,
**infinite cache, no eviction**. Three things stand between it and any claim
about results:

1. **Cache-hit rate ≠ sharing ratio.** The simulator runs a *finite* block pool
   with LRU eviction. Changing block granularity from 512 to 16 changes eviction
   behaviour, fragmentation and the admission path independently of which ids
   are shared. The realised-sharing ceiling moves by −0.88 pp; the achieved hit
   rate could move by more, less, or the other way.
2. **Latency ≠ cache-hit rate.** A hit-rate change propagates through prefill
   work, batch composition and queueing before it reaches TTFT, and
   `PROJECT_SPEC.md` §11's thresholds are stated in p95 TTFT and cost, not in
   sharing.
3. **Routing bias is a separate question entirely.** B3 and B4 route on
   `get_cached_prefill_length`, which returns *tokens* derived from the block
   walk. At 16-token granularity that estimate has 32× finer resolution, so the
   router can make **different decisions** — not merely slightly-worse ones.
   A difference in routing decisions is a difference in the experiment's
   independent variable, and its effect on the headline comparison against
   B2-tok is unmeasured and not obviously small.

**G4 therefore splits into three sub-gates:**

| | Sub-gate | Status |
|---|---|---|
| **G4a** | Mapping specified and implemented **without inventing prefix information** | **DONE** — tested, §1 above |
| **G4b** | Workload-level sharing bias quantified | **DONE** — −0.88 pp on D′ |
| **G4c** | **System-level** consequence: change in simulated cache-hit rate, p95 TTFT, and **routing decisions** | **OPEN — unmeasured** |

G4c is the one that matters for RQ1 and it cannot be settled by arithmetic on
the workload. It needs paired simulator runs — the same workload at 512- and
16-token hashes through the same policy — comparing hit rate, TTFT and the
per-request `replica` assignment. Run A can do that at 4 096-token context on the
cached predictor; whether the answer transfers to 65 536 is itself open.

**Still to do at M4:** adopt the expansion, then run the paired comparison that
G4c requires.

---

## 2. The smallest end-to-end run

**The key enabler: M1's predictor cache survives.** `.spike/vidur-canary/cache`
holds **1.3 GB, 24 `.pkl`** for `a100 / meta-llama/Llama-2-7b-hf / TP=1`.
`measured` at M1: a warm run of that configuration completed in **1 min 2 s**.

So the smallest useful run costs **nothing** and needs **no fit**:

> **Run A — pipeline smoke test (free, ~2 minutes).**
> Workload: D′ Mooncake, expanded to 16-token blocks, further restricted to
> requests that fit Llama-2-7b's 4 096-token context. Config: `a100`,
> `Llama-2-7b-hf`, TP=1, 4 replicas, `vllm_v1` scheduler, prefix caching on,
> a cache-aware global scheduler.

**Run A is a basic integration check. It is not a feasibility result.**

What it can establish: that the unified schema reaches Vidur; that the G4
expansion is accepted and accounted; that prefix-cache metrics, multi-replica
routing and per-request output (`replica`,
`request_num_prefill_tokens_cached`) behave; that two identical invocations are
bit-identical. It is the cheapest thing that can **falsify** the integration.

**What Run A cannot establish, and must not be reported as establishing:**

- **Nothing about Llama-3.1-class feasibility.** It runs `Llama-2-7b-hf` — a
  different model, a different profile, a different predictor, 4 096-token
  context against D′'s 65 536. Its timings, memory and fit cost say nothing
  about the configuration D-008 actually specifies.
- **Nothing about G1.** Whether a Llama-3-8B fit completes inside our limits is
  exactly what Run B tests and Run A cannot.
- **Only a partial answer on G4c.** It can give a paired 512-vs-16 comparison at
  4 096 tokens. Whether that transfers to 65 536 — where cache pressure, batch
  sizes and eviction all differ — is open.

> **Run B — long-context feasibility (expensive, gated).**
> Same pipeline at `Meta-Llama-3-8B`, 65 536-token budget. Requires a **new
> predictor fit** — the one thing explicitly not authorised.

---

## 3. Predictor-fit requirements, limits and stop conditions

Applies to Run B only. Run A uses the existing cache and fits nothing.

**What a fit involves.** Vidur trains a random forest per operation over the
profiled rows (grid search across `n_estimators` / `max_depth` /
`min_samples_split`), then materialises a prediction table over a grid of
**2 622 080** rows — `prediction_max_batch_size` 512 × `max_tokens_per_request`
262 144 ÷ `kv_cache_prediction_granularity` 64, plus the prefill product. **That
grid is model-independent**, so it does not grow when the model changes.

**What does change** is the training set: a100 TP=1 attention rows go
**14 650 → 65 268 (4.46×)** from Llama-2-7b to Llama-3-8B, post-TP-filter.

**No wall-clock estimate is offered.** M1's 4 h 37 m covered 11 trained
operations, but the surviving log was captured with `tail` and shows only 4,
accounting for ~10 m 43 s. ~4 h 26 m is unattributed, so the run cannot be
decomposed and an extrapolation from it would be invention. This is the third
time an estimate built on an unexamined aggregate has been wrong; the correct
output here is a **measurement with a stop condition**, not a number.

**Machine limits** (`measured`, this host): 8 cores, **7 GB RAM**. M1 peak RSS
was **4.02 GB** for a 512-request run — 57 % of total. Parallel runs will be
memory-bound before CPU-bound.

**Bounds for any authorised fit:**

| Bound | Value | Rationale |
|---|---|---|
| Wall clock | **6 h hard cap**, checkpointed progress logged | M1's comparable run was 4 h 37 m at 4.46× fewer rows; exceeding 6 h means the extrapolation is wrong and we should stop and re-plan |
| Peak RSS | **5.5 GB**, monitored | 7 GB host; beyond this the machine swaps and the timing is meaningless |
| Log capture | **full log to file**, never `tail` | the exact failure that made M1's cost unattributable |
| Concurrency | **1 fit at a time** | memory-bound |
| Disk | ≥ 10 GB free for `cache/` | M1 produced 235 MB; `canary`'s grew past 1 GB |

**Stop conditions — any one halts the run and reports:**

1. Wall clock exceeds 6 h.
2. Peak RSS exceeds 5.5 GB or the host begins swapping.
3. Any operation's fitted MEAP exceeds **5 %** (M1's were 0.0–0.78 %); a sudden
   jump means the training data does not support the grid.
4. `cache/` exceeds 5 GB.

---

## 4. What can proceed now, and what is blocked

| Work | Status | Depends on |
|---|---|---|
| G4 mapping specified, implemented, tested, bias measured | **DONE** (this document, §1) | — |
| Adopt the expansion in the workload build | **READY** — CPU only | approval |
| **Run A** pipeline smoke test | **READY** — free, ~2 min, uses M1's surviving cache | approval |
| Determinism re-check across two Run A invocations | **READY** — free | Run A |
| G2: does the random forest flat-line outside its training range? | **READY** — CPU only, can be probed directly on the **existing** Llama-2-7b cache by querying the predictor beyond 4 032 kv. **No fit needed.** | approval |
| **Run B** long-context feasibility (**G1**) | **BLOCKED** | an authorised predictor fit |
| G3 proxy fidelity | **BLOCKED**, and moved to **M11** by D-009 | real vLLM + GPU |
| Reconsidering D′ | **BLOCKED** | M3 profiling (deferred), then G4 + G1 + a superseding decision |

**G2 is the pleasant surprise.** It does not need a fit at all. The Llama-2-7b
cache already exists and its decode training data stops at 4 032; querying the
loaded predictor at kv values beyond that shows directly whether it flat-lines,
extrapolates linearly, or does something else. That answers the question D-008
flagged, for free, on this laptop.

---

## 5. What I am asking for

| | Item | Cost | Effect |
|---|---|---|---|
| **1** | Adopt the G4 expansion in the workload build | free | closes the mapping half of G4 |
| **2** | **Run A** — pipeline smoke test on the surviving M1 cache | free, ~2 min | proves the integration end to end, or falsifies it cheaply |
| **3** | **G2 probe** on the existing cache | free, ~2 min | answers the extrapolation question without a fit |
| — | Run B / G1 | **not requested** | needs the long fit; out of bounds |

Items 1–3 are free, bounded, and use only what is already on disk. They would
close or advance **G2 and half of G4** without a single authorised expense.

**Not requested, and not to be started without a separate decision:** the Run B
predictor fit, any GPU rental, any M3 profiling.
