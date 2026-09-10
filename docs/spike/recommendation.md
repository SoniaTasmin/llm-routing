# docs/spike/recommendation.md — M1 recommendation

**Date:** 2026-09-02 · **Milestone:** M1 · **Decision recorded as:** D-006

---

## 1. The recommendation

> **A — extend Vidur, on the `canary` branch, vendored and pinned at commit
> `25e0082dbbfb206fb0477c3ebbededa7ead78949`.**

Rejected: **B** (extend LLMServingSim) and **C** (build a small cluster-level
DES).

This is a recommendation about the *base*, not about the policies. B1/B2/B3/B4
remain unimplemented and out of scope until M5–M8.

---

## 2. Why, against the criteria the user set

### Fit to R1–R8

`canary` fails **two** requirements outright (R4 heterogeneity, R5 replica
failure) and is partial on two (R6, R7). LLMServingSim fails **three** (R5, R6,
R7) and is partial on the one that matters most (R2).

Raw counts favour LLMServingSim (4 PASS vs 3). The counts are the wrong
instrument, and `requirements-matrix.md` §4 states the weighting used instead:

- **R2 is the study.** The routers are the independent variable of every
  experiment E1–E8. Vidur `canary` hands us an abstract `schedule()` returning
  `(replica_id, request)` pairs, a registry, a type enum, eleven worked
  examples, and — critically — `on_batch_end` / `on_prefill_end` /
  `on_request_end` callbacks with matching events, which is what a
  service-time-aware queue estimate (our **B2-tok**, the strong primary
  baseline) needs to stay consistent. LLMServingSim's `CUSTOM` hook *does not
  receive the request*, so **none** of B2-tok, B3 or B4 can be written against
  it until the interface is widened and a registry with per-policy parameters is
  built.
- **R5 is the major result.** E4/H4 is named as such in `PROJECT_SPEC.md` §6.
  On Vidur it is a new event class in a uniform pure-Python event system,
  estimated 3–5 d. On LLMServingSim the instance set is mirrored into ASTRA-Sim's
  NPU topology, written to disk *before* the C++ backend is spawned, and the
  frontend loop is keyed on NPU ids parsed from that backend's stdout —
  estimated 8–15 d with wide variance, across a process and language boundary.
- **R7 is the primary outcome metric** and LLMServingSim has nothing: no price
  table, no cost column. Vidur has a priced GPU table and, in
  `config_optimizer/config_explorer/capacity_search.py`, a working
  binary-search-to-SLO-break harness that E1 can be built from rather than
  invented.
- **E1 throughput — indicative, not controlled.** Vidur `canary` cost
  **~0.18 s per simulated request** and LLMServingSim **~0.97 s**, a ratio of
  roughly **5.5×**. **This is an indicative comparison across two differently
  configured runs, not a controlled like-for-like benchmark.** Enabling prefix
  caching on both sides does not make the workloads equivalent: different
  traces (512 Mooncake requests ≤4 096 tokens vs a 300-request synthetic probe
  with 1 024-token prompts), different replica counts (4 vs 2), different
  batching schedulers, different cache configurations. The honest claim is
  *order-of-magnitude*: Vidur's per-request simulation cost is **single-digit
  times lower** on the configurations we happened to run.

  An earlier draft claimed ~60×, by comparing against Vidur `main` running the
  cheap Sarathi scheduler with no prefix cache at all. That was withdrawn.
  A properly controlled comparison — same trace, same replica count, same cache
  settings on both simulators — was **not** performed, and is not worth
  performing now: it would not change the decision, which rests on R2, R5 and
  R7, not on throughput. Throughput is a contributing consideration only.

### Extension complexity

`estimate`, basis in `requirements-matrix.md` §3:

| Option | Engineer-days to close all gaps |
|---|---|
| **A — Vidur `canary`** | **13.5 – 22.5** |
| B — LLMServingSim | 22 – 38, plus an indicatively higher per-request simulation cost (~5.5× on the configurations tested; not a controlled comparison) |
| C — build our own DES | 17 – 26, plus fidelity risk |

Every Vidur gap is a contained change in one Python process. Two of
LLMServingSim's cross a subprocess boundary into C++.

### Research validity

Three points. The second is the strongest, but it is narrower than an
earlier draft of this file claimed — see the correction inside it:

1. **We inherit a published, validated timing model either way** — Vidur
   (MLSys'24) and LLMServingSim (IISWC'24 / ISPASS'26) both derive execution
   time from real profiling data. Option C would replace that with a model we
   invented, which converts E8 from "validate a published model against our own
   vLLM measurements" into "the entire result rests on a timing model we wrote
   ourselves." For a study whose *whole claim* is careful empirical
   characterisation, that is the wrong risk to take. This is why C is rejected
   despite a competitive day count.
2. **`canary` already ships cache-aware sticky routing with an overload guard**
   — `sticky_lor_scheduler.py`, `ranked_sticky_lop_uncached_global_scheduler.py`
   and `tolerant_sticky_lop_uncached_global_scheduler.py`, the last with an
   explicit `tolerance_factor` load-imbalance guard. These are *candidate*
   implementations of our **B3**.

   Starting from an upstream implementation **reduces one specific risk** — that
   we author a treatment whose code we shaped, consciously or not, to favour the
   outcome we expect. It does **not** eliminate tuning bias, and an earlier draft
   of this file overclaimed that it did. Two things remain to be established, and
   neither is free:

   - **Equivalence.** `PROJECT_SPEC.md` §5 specifies B3 as "prefix-affinity
     routing with a guard that sheds affinity under load". Whether
     `tolerant_sticky_lop_uncached` *is* that policy, or a related-but-different
     one, is an open question to be answered by reading and testing it against
     the spec, not assumed. If it diverges we must either adopt its definition
     explicitly and say so, or implement the specified policy ourselves.
   - **Fair parameter selection.** `tolerance_factor` (and B2-tok's `d`, and the
     service-time estimator) are free parameters. Whoever wrote the code, *we*
     choose the values. Bias enters through tuning the treatment more carefully
     than the baseline. The mitigation is a **documented tuning protocol applied
     symmetrically** to B2-tok and to B3/B4 — same search budget, same selection
     criterion, same seeds, decided and written down **before** the headline runs.
     That protocol is M5/M8 work and is not yet written.

   What survives of the original argument: if the result is negative, it is a
   negative result about an implementation we did not author, which is a
   modestly stronger position than one about a router we wrote ourselves. That is
   a real but limited benefit, not a defence against tuning bias.
3. **`canary` ships `data/processed_traces/mooncake_conversation_trace.csv`** —
   80 MB, 12 031 requests, with `block_hash_ids`, `block_size` and `session_id`.
   Mooncake is our **primary** trace (`PROJECT_SPEC.md` §7) and this is most of
   the M2 loader. `TraceRequestGenerator` already parses that schema and
   tolerates its absence, so the same reader ingests the synthetic φ sweep and
   the cache-blind Azure control without a second code path.
   `assumption` — **this file must be re-derived from the upstream Mooncake
   trace before any RQ1 claim rests on it.** We will not take a third party's
   preprocessing on trust.

### Reproducibility

| | Vidur `canary` | LLMServingSim |
|---|---|---|
| Install | `uv sync --frozen` against a committed `uv.lock` | 10 git submodule paths (nested 3 deep) + a 2.26 GB Docker image + a C++ cmake build + a `pip install` that clones a further repo from GitHub *inside the container* |
| Determinism | **verified**: two separate processes produced a bit-identical simulated end time, `240.3957407989195 s` | not tested by us; no simulation-level seed flag exists (seeds hardcoded `42` in three modules) |
| Cost on *this* machine | 4 h 37 m one-off predictor fit, then 1 min/run | see `NOTEBOOK.md`: **11 h 29 m** for the ASTRA-Sim build, and a `pip` step that stalled outright and had to be worked around |

`PROJECT_SPEC.md` §11 requires ≥10 seeds per cell with paired seeded workloads.
Vidur's demonstrated cross-process determinism is directly that property.
LLMServingSim's missing seed flag is fixable, but it is one more thing to fix.

### Ability to support E1–E5 / E8

| Experiment | Vidur `canary` | LLMServingSim |
|---|---|---|
| **E1** min cost @ fixed SLO | needs R4 + R7 + the search harness; `capacity_search.py` is a working template; runs are **in-process**, `measured` ~0.18 s/request on the configuration tested | needs R7 from zero *and* an out-of-process driver (a container + subprocess per run), `measured` ~0.97 s/request on the configuration tested. The two figures come from different workloads and are indicative, not a controlled comparison. |
| **E2** cache-sharing threshold (φ) | prefix cache + Mooncake block hashes + `replica_prefix_cache_metrics` present | tiered cache present; needs the per-request hit columns exported |
| **E3** heterogeneity | **blocked on R4** — the only place LLMServingSim is clearly ahead | **works today, verified by running a mixed RTX4090 + RTXPRO6000 fleet** |
| **E4** preemption / H4 | new event class; per-replica KV cache object can simply be dropped, which *is* the H4 mechanism | crosses into the C++ topology |
| **E5** signal ablation | trivial once policies are ours | trivial once R2 is rebuilt |
| **E8** fidelity vs vLLM | we build the comparison; Vidur's own MLSys'24 validation is the precedent | **best in class** — a `bench` harness with strict token-id replay and published per-request deltas of +0.6 % TTFT / +0.2 % TPOT on the matched configuration |

E3 and E8 are the two places LLMServingSim wins. E3 is one MVP experiment whose
third mix is already cut-if-behind. E8's *methodology* — strict replay pinning
of token ids and sampling params so simulator and vLLM see identical prompts in
identical order — is copyable regardless of base, and we will copy it.

### Maintenance burden

`canary` is an **unmerged branch whose last commit is 2025-06-25**, ~14 months
before this spike. `assumption`: it will not be maintained and will never merge.
The mitigation is not to hope otherwise but to **vendor it** — copy the tree in
at the pinned SHA, with provenance and licence recorded, and treat it as our
source rather than a tracked upstream. That converts an abandonment risk into a
fixed, known quantity, which is what a 12-week project needs.

LLMServingSim is by contrast *actively* maintained (commits days before this
spike, three papers, a documentation site). That is a genuine point in its
favour and is recorded as such — it is simply outweighed.

---

## 3. What this recommendation costs us, stated plainly

1. **R4 becomes our problem.** LLMServingSim does heterogeneity today; we will
   spend an estimated 3–5 d building it. E3 (RQ2) is gated on that work.
2. **We take on an abandoned branch.** Two defects were already found on it
   (`vidur-notes.md` §6): a latent 4-arg/3-arg call in `hash_block_tokens`, and
   an unbounded per-`(request, replica)` memo in the tolerant sticky scheduler.
   There will be more.
3. **We give up the best-validated timing model.** LLMServingSim's published
   vLLM agreement is stronger evidence than anything Vidur currently offers on
   its `canary` branch, and E8 will be more work for us as a result.
4. **The predictor-fit cost is per-SKU, and `canary` is not cheaper.**
   `measured`: 4 h 37 m for one `(model, device)` pair on `main`, producing a
   235 MB cache. Adding device SKUs for E3 re-pays that cost per SKU.

   I initially expected `canary` to be cheaper here — its merge commit
   advertises "a much faster and lighter Vidur" — and an early mid-run
   snapshot of its cache directory seemed to support that. It does not:
   `canary`'s cache for the same `(a100, Llama-2-7b-hf)` pair grew **larger**
   than `main`'s. The "lighter" claim in that commit message is not about the
   predictor cache, or does not hold on this machine. Recorded because I was
   about to assert the opposite. Falsifier **F2** covers the consequence.

---

## 4. Why not C (build our own small DES)

`PROJECT_SPEC.md` §9 permits C only if neither candidate is suitable. One is.
Beyond that: option C's day count (17–26) is not the objection — the objection
is that it would require us to invent the continuous-batching timing model that
both candidates derived from real profiling, and E8 would then be validating our
own invention rather than a published one. That trades a *schedule* risk for a
*validity* risk, in a project whose entire contribution is empirical care.

---

## 5. What would falsify this recommendation

Concrete, checkable, with a deadline. If any of these fires, D-006 is revisited
and a superseding decision is written. F6 was added at the end of the spike,
after the first `canary` run crashed and made the context-length constraint
visible:

| # | Falsifier | Check by |
|---|-----------|----------|
| F1 | The **bounded feasibility check defined in §5a** fails, or shows R4 cannot be closed in ≤ 8 engineer-days — e.g. the per-`(model, device)` execution-time predictors turn out to be entangled beyond the 4 call sites found | **end of M4** (the check, not the implementation) |
| F2 | The per-process predictor-load tax (`measured`: 32–115 s) cannot be amortised across an E1 sweep, making a fleet search of the required size infeasible on available hardware | **end of M4** |
| F3 | `canary`'s prefix cache proves not to be a faithful port of vLLM's block-pool semantics under unit test, invalidating RQ1/E2 | **end of M4** |
| F4 | The shipped `mooncake_conversation_trace.csv` cannot be reproduced from the upstream Mooncake trace, so its prefix structure is unverifiable | **end of M2** |
| F5 | The `canary` branch turns out to be so defective that fixing it exceeds the from-scratch estimate (17–26 d) — i.e. option C becomes cheaper *and* we would be replacing the calibrated timing model anyway | **end of M4** |
| F6 | Mooncake at native lengths cannot be simulated: its p95 request is 40 568 tokens and the largest context any Vidur model config ships is 32 768. Whatever filtering or scaling we adopt changes the prefix-sharing structure RQ1 measures, so it must be a documented research decision — and if no defensible policy exists, RQ1's primary-trace evidence is compromised | **end of M2** |

F1 is the most likely to fire.

**If F1 fires, the fallback is not an immediate change of base** — it is to keep
Vidur for E1/E2/E4/E5 and re-open the question of E3's scope **with the user**.

**A scope clarification that an earlier draft of this file got wrong.**
`PROJECT_SPEC.md`'s cut-if-behind register lists "third heterogeneous mix" —
that is *one additional fleet composition*, not heterogeneity itself. Dropping
heterogeneity altogether would delete **RQ2** ("When does capability-aware
routing outperform strong queue-aware routing on heterogeneous GPU fleets?")
and **E3**, both of which are frozen MVP items in the M0 specification. Those
are not the same decision and must not be conflated:

| Change | Status |
|---|---|
| Drop the *third* heterogeneous fleet mix, keep two | already sanctioned by the frozen cut-if-behind register |
| Reduce E3 to a single heterogeneous mix | **requires explicit user approval** |
| Drop E3 / RQ2 entirely | **requires explicit user approval**, and amends the frozen `PROJECT_SPEC.md` |

If F1 fires, the assistant's job is to present the measured effort, the options
and a recommendation — not to quietly shrink the research question.

---

## 5a. The bounded R4 feasibility check (defines F1's trigger)

F1 is checked at **end of M4**; the full R4 implementation stays at **M7**. These
are different pieces of work and the check must not become the implementation by
stealth. The check is a **time-boxed 1-day probe** (`estimate`) with three steps
and a pass/fail rule, run on the vendored tree:

1. **Confirm the coupling surface.** Re-grep the vendored tree for reads of
   `cluster_config.replica_config`. The M1 spike found **4** non-analyzer sites
   (`base_global_scheduler.py:40,46`, `replica_metrics_store.py:60,220`).
   *Fail if* the count is materially larger on the vendored SHA than the spike
   found.
2. **Two predictors in one process.** Instantiate two `ExecutionTimePredictor`s
   for two different `(model, device)` pairs inside a single interpreter and
   confirm they coexist — no singleton, no shared module-level cache keyed
   without the device, no cross-contamination of prediction tables. This is the
   step most likely to surprise us, because it is the one the spike inferred
   from source rather than executed. *Fail if* they cannot coexist without
   restructuring the predictor layer.
3. **Two-replica smoke test, minimal patch.** With a throwaway patch — not the
   real implementation, not merged — build a 2-replica cluster whose replicas
   have different `device` values and confirm a short run completes and the two
   replicas draw different execution times. **Deliberately excluded from the
   probe:** CLI/config plumbing, metrics-store changes, cost attribution,
   capability-aware routing. Those are M7.

**Pass rule:** all three steps succeed within the 1-day box → F1 does not fire,
R4 is scheduled at M7 on the 3–5 d estimate.
**Fail rule:** any step fails, or step 2 requires restructuring → F1 fires, and
the E3-scope question goes to the user with measured evidence.

The throwaway patch from step 3 is discarded, not carried forward; M7 starts
from the vendored tree.

---

## 6. Immediate consequences to carry into M2

- Vendor `canary` at `25e0082` into `simulator/` **when M2 begins** — not now;
  M1 is a decision milestone and vendoring is implementation.
- Record MIT licence and provenance at vendoring time.
- Re-derive `mooncake_conversation_trace.csv` from upstream (F4) as part of the
  M2 loader work, rather than adopting it.
- Copy LLMServingSim's E8 methodology (strict token-id replay pinning) into the
  M11 plan. We are not adopting the simulator; we are adopting the validation
  discipline.
- Keep both spike checkouts reproducible from `REPRODUCE.md` §3a so this
  decision can be re-audited.
