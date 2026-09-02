# DECISIONS.md — Technical and Research Decisions

Append-only. Never delete or rewrite a decision. If a decision is reversed, add
a **new** entry that supersedes the old one and mark the old one as superseded.

Entry template:

```
## D-NNN — <title>
**Date:** YYYY-MM-DD · **Status:** ACCEPTED | SUPERSEDED by D-MMM | REJECTED
**Context:** why this came up
**Decision:** what we decided
**Rationale:** why
**Alternatives rejected:** what else was considered and why not
**Consequences:** what this forces later
**Would falsify this:** what evidence would make us reverse it
```

---

## D-001 — Frame the project as an empirical characterization study, not a new algorithm
**Date:** 2026-08-31 · **Status:** ACCEPTED (Milestone 0, frozen)

**Context.** The LLM-routing literature is crowded with proposed policies. A
Master's-application project claiming a novel superior router would be weak and
hard to defend.

**Decision.** The contribution is an **empirical characterization and
reproducibility study** answering *when* routing sophistication pays, not a new
routing algorithm.

**Rationale.** The honest, defensible contribution is the boundary condition —
the regime where sophistication stops paying — which the literature reports
inconsistently. This is achievable in 12 weeks; a genuinely novel algorithm is
not.

**Alternatives rejected.** "Propose a new cache+cost-aware router and show it
wins" — rejected as unfalsifiable-in-practice within the timeline and easy for a
reviewer to dismiss as tuned-to-win.

**Consequences.** Negative or null results are valid outcomes and must be
reported. Baseline strength becomes the critical methodological asset (see
D-002).

**Would falsify this.** Nothing empirical; this is a framing choice by the user.

---

## D-002 — B2-tok (token/service-time-aware JSQ(d)) is the strong primary baseline
**Date:** 2026-08-31 · **Status:** ACCEPTED (Milestone 0, frozen)

**Context.** Many papers compare sophisticated routing only against Round Robin
or least-connections, which inflates apparent gains.

**Decision.** Round Robin (B1) is a **floor/sanity** baseline only. Every
headline claim is measured **against B2-tok**. Beating B1 alone is not reported
as a finding.

**Rationale.** Queue-aware scheduling on service-time estimates is already
strong. If cache/capability awareness cannot beat it, that *is* the result.

**Alternatives rejected.** Using B1 or B2-req as the comparator — rejected as
methodologically weak.

**Consequences.** B2-tok must be implemented well and tuned fairly (choice of
`d`, service-time estimator). An under-tuned B2-tok would invalidate the whole
study, so its tuning must itself be documented and evidenced.

**Would falsify this.** Evidence that B2-tok as implemented is not competitive
with published queue-aware schedulers — which would mean our baseline is a straw
man and must be strengthened.

---

## D-003 — Primary outcome is minimum fleet cost at fixed SLO
**Date:** 2026-08-31 · **Status:** ACCEPTED (Milestone 0, frozen)

**Context.** Latency-only comparisons at fixed fleet size conflate "faster" with
"cheaper", and are sensitive to the arbitrary chosen load point.

**Decision.** The primary metric is the **minimum infrastructure/fleet cost
required to satisfy a fixed SLO**. Latency, SLO attainment, cache hit rate and
throughput are secondary/diagnostic.

**Rationale.** Cost-at-fixed-SLO is the decision an operator actually makes, and
it converts latency headroom into a single comparable scalar.

**Alternatives rejected.** p95 TTFT at fixed fleet size as the headline —
retained as a secondary metric instead.

**Consequences.** The simulator must support a search over fleet configurations
and must carry a cost model. This is why no provisioning controller is needed.

**Would falsify this.** If the fleet-configuration search proves intractable at
the required seed count, we would fall back to fixed-fleet metrics — and would
record that reversal here.

---

## D-004 — Azure traces are cache-blind controls
**Date:** 2026-08-31 · **Status:** ACCEPTED (Milestone 0, frozen)

**Context.** Azure LLM inference traces provide arrival and length distributions
but no prompt content, so prefix structure is absent.

**Decision.** Azure traces are used **only** for realistic arrival/length
distributions and serve as **cache-blind controls**. No cache-hit-rate or
prefix-sharing claim may be derived from them.

**Rationale.** Inferring prefix sharing from a trace that does not record prompt
content would be fabrication.

**Alternatives rejected.** Synthesising plausible prompt content onto Azure
records — rejected: it would manufacture the very structure under study.

**Consequences.** RQ1 evidence comes from Mooncake and the synthetic phi sweep;
Azure supplies the null/control condition.

**Would falsify this.** A release of Azure traces containing prompt hashes or
prefix identifiers.

---

## D-005 — Simulator base is UNDECIDED, pending the Milestone-1 spike
**Date:** 2026-08-31 · **Status:** **SUPERSEDED by D-006** (2026-09-02) — recorded the question as open; D-006 answers it

**Context.** The project needs a multi-replica simulator with pluggable routing,
cross-replica prefix-cache state, heterogeneous replicas, mid-run failure,
SLO modelling, cost accounting, and per-request metrics (R1–R8).

**Decision.** **No base has been chosen.** Milestone 1 is a 3-day spike that
evaluates **Vidur** and **LLMServingSim** against R1–R8 before any commitment.

Standing rules for the spike:
- No pre-commitment to Vidur.
- No pre-commitment to LLMServingSim.
- Do not immediately build our own simulator.
- If one existing simulator supports the project cleanly, **extend it**.
- If neither is suitable, build a **small cluster-level DES**.
- A full from-scratch LLM operator simulator requires a compelling demonstrated
  reason.

**Rationale.** Choosing a base by reputation rather than by requirement fit is
the most likely way to lose several weeks in the middle of the project.

**Alternatives rejected (for now).** Committing to Vidur on the strength of its
timing model; committing to a custom DES for control. Both remain live options
and will be decided on the spike's evidence.

**Consequences.** M1 produces a scoring matrix in `docs/spike/` and a successor
decision entry (D-006) recording the outcome.

**Would falsify this.** N/A — this entry records that the question is open.

---

## D-006 — Simulator base: extend Vidur, on the `canary` branch, vendored at a pinned commit
**Date:** 2026-09-02 · **Status:** ACCEPTED (Milestone 1 output) · **Supersedes:** D-005

**Context.** D-005 recorded that the simulator base was deliberately undecided
and that M1 would be a 3-day spike scoring **Vidur** and **LLMServingSim**
against R1–R8, with three permitted outcomes: extend Vidur, extend
LLMServingSim, or build a small cluster-level DES. The spike ran 2026-09-01 →
2026-09-02. Both candidates were installed and **actually run** — neither was
judged from its documentation.

A finding that changed the shape of the decision: Vidur's `main` README (line
145) directs anyone needing prefix caching or routing policies to an unmerged
**`canary`** branch. `main` and `canary` are different simulators for this
project's purposes — `main` has no prefix cache at all — so three candidates
were scored, not two.

**Decision.** **Extend Vidur, branch `canary`, vendored and pinned at commit
`25e0082dbbfb206fb0477c3ebbededa7ead78949`.**

Vendoring happens at M2, not now; M1 was a decision milestone.

**Evidence.** `docs/spike/requirements-matrix.md` (the R1–R8 matrix with
file/line evidence and per-requirement extension estimates),
`docs/spike/vidur-notes.md`, `docs/spike/llmservingsim-notes.md`,
`docs/spike/recommendation.md`. Dead ends and stalls in `NOTEBOOK.md`.

Score summary (**PASS / PARTIAL / FAIL**):

| | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 |
|---|---|---|---|---|---|---|---|---|
| Vidur `main` | PASS | PASS | FAIL | FAIL | FAIL | PARTIAL | PARTIAL | PASS |
| **Vidur `canary`** | PASS | PASS | PARTIAL | FAIL | FAIL | PARTIAL | PARTIAL | PASS |
| LLMServingSim 2.0 | PASS | PARTIAL | PASS | PASS | FAIL | FAIL | FAIL | PASS |

**Rationale.** The decision was **not** made on PASS counts — LLMServingSim
scores more (4 vs 3). It was made on a weighting stated explicitly in
`requirements-matrix.md` §4:

1. **R2 is the object of study.** The routers are the independent variable of
   every experiment. Vidur `canary` provides an ABC returning
   `(replica_id, request)` pairs, a registry, eleven worked policies, and
   `on_batch_end` / `on_prefill_end` / `on_request_end` callbacks — which is
   what our strong primary baseline **B2-tok** needs to maintain a
   service-time-aware queue estimate. LLMServingSim's `CUSTOM` routing hook is
   **never passed the request**, so B2-tok, B3 and B4 cannot be written against
   it until the interface is widened and a parameterised registry is built.
2. **R5 is the major result.** E4/H4 (`PROJECT_SPEC.md` §6). On Vidur this is a
   new event class in a uniform pure-Python event loop (`estimate` 3–5 d). On
   LLMServingSim the instance set is mirrored into ASTRA-Sim's NPU topology,
   written to disk before the C++ backend is spawned, and the frontend loop is
   keyed on NPU ids parsed from that backend's stdout (`estimate` 8–15 d, wide).
3. **R7 is the primary outcome metric** (`PROJECT_SPEC.md` §3). LLMServingSim
   has no cost model at all — its `power_model.py` is energy, not price. Vidur
   has a priced GPU table and, in `capacity_search.py`, a working
   binary-search-to-SLO-break harness that E1 can be built from.
4. **Reproducibility.** `canary` ships a committed `uv.lock`; two separate Vidur
   processes produced a **bit-identical** simulated end time
   (`240.3957407989195 s`, `measured`), which is exactly the determinism the
   ≥10-seeds-per-cell paired design in `PROJECT_SPEC.md` §11 depends on.
   LLMServingSim needs Docker, ten submodule paths and a C++ build, and exposes
   no simulation-level seed flag.
5. **Research validity.** `canary` already ships session-sticky cache-aware
   routing **with an explicit load-imbalance guard**
   (`tolerant_sticky_lop_uncached_global_scheduler_config_tolerance_factor`) —
   in substance our **B3**. Building the study's *treatment* on upstream's own
   implementation rather than one we wrote strengthens the central
   methodological claim: we cannot be accused of tuning the treatment to win,
   and a negative result becomes a negative result about a *published*
   cache-aware router rather than about a straw man.
6. **Head start on M2.** `canary` ships a preprocessed **Mooncake** trace
   (12 031 requests, with `block_hash_ids` / `block_size` / `session_id`) and a
   `TraceRequestGenerator` that reads exactly that schema — most of the M2
   loader. Adoption is conditional on re-derivation (falsifier F4).

**Alternatives rejected.**

- **B — extend LLMServingSim.** It wins **R4** outright (verified by execution:
  a hand-written RTX4090 + RTXPRO6000 fleet ran, the two SKUs producing
  measurably different timings) and has by far the better published vLLM
  validation (+0.6 % TTFT, +0.2 % TPOT on the matched configuration, with a
  strict token-id replay harness). Rejected because it is weakest exactly where
  this project is heaviest — routing extensibility, replica failure, SLO and
  cost — and because two of those fixes cross a process and language boundary.
  `estimate` 22–38 d versus 13.5–22.5 d.
- **C — build a small cluster-level DES.** `estimate` 17–26 d, which is not far
  off B. Rejected on **validity, not schedule**: it would require inventing the
  continuous-batching timing model that both candidates derived from real
  profiling data, converting E8 from "validate a published model against our own
  vLLM measurements" into "the whole result rests on a timing model we wrote
  ourselves." `PROJECT_SPEC.md` §9 permits C only if neither candidate is
  suitable. One is.

**Two findings that arrived late in the spike and are recorded because they
temper this decision rather than support it.**

1. **The first `canary` run on the shipped Mooncake trace crashed** after 18
   minutes with `AssertionError: num_new_tokens should be greater than 0 but got
   -24844`. The cause was **my configuration**, not a Vidur defect — I paired a
   trace whose median request is 7 767 tokens (p95 40 568, max 127 039) with a
   4 096-token model. But it surfaced a real constraint: **no model config
   `canary` ships has a context window large enough for Mooncake's p95 request**
   (largest is 32 768), and Vidur validates this nowhere, failing late and
   uninformatively. Running Mooncake at native lengths is therefore M2/M4 work —
   a long-context model config with matching profiling data, or a documented
   filtering/scaling policy that changes the prefix structure RQ1 measures.
   The re-run on a fitting 512-request subset succeeded (exit 0, 91 s of
   simulation, 32.69 % of prefill tokens served from cache, per-request output
   carrying `replica` and `request_num_prefill_tokens_cached`).
2. **A throughput claim in the first draft of this decision was wrong and has
   been withdrawn.** It put Vidur ahead of LLMServingSim by ~60× per simulated
   request. That compared LLMServingSim against Vidur `main` running the cheap
   Sarathi scheduler with **no prefix cache**. Like for like, both with prefix
   caching: **~0.18 s/request** (Vidur `canary`) against **~0.97 s/request**
   (LLMServingSim) — about **5.5×**. The E1 argument survives at that
   magnitude, and it is a contributing reason rather than the decisive one.

**Consequences.**

- R4 (heterogeneity) becomes our work — `estimate` 3–5 d at M7; E3/RQ2 is gated
  on it. This is the one thing LLMServingSim would have given us free.
- R5 (failure injection) becomes our work — `estimate` 3–5 d at M10.
- R6 attainment metric (1–2 d) and R7 cost + fleet search (4–7 d) at M9.
- We take on an **unmerged, unmaintained branch** (last commit 2025-06-25).
  Mitigation: vendor at the pinned SHA rather than track upstream. Two defects
  are already documented, one of them **executed and confirmed**
  (`hash_block_tokens` raises `TypeError` on the no-external-hashes path).
  Consequence for M2: our synthetic φ generator must emit block hashes itself.
- E8 will be more work than it would have been on LLMServingSim. We are
  adopting **its validation methodology** (strict token-id replay pinning) even
  though we are rejecting the simulator.
- Vidur's per-process predictor cost is real and per-`(model, device, TP)`:
  `measured` 4 h 37 m for the first fit, then ~32–115 s of cache loading per
  process. New GPU SKUs for E3 re-pay the fit. Batching many E1 cells into one
  interpreter is a requirement, not an optimisation.
- Peak memory is not trivial: `measured` **4.02 GB** RSS for a 512-request,
  4-replica `canary` run on a 7 GB machine. Parallelising E1 across cores on
  this hardware will be memory-bound before it is CPU-bound.

**Would falsify this.** Six dated falsifiers, stated in full in
`docs/spike/recommendation.md` §5:

- **F1** — R4 heterogeneity cannot be made to work on `canary` within 8
  engineer-days (check by end of M4). *Most likely to fire.*
- **F2** — the per-process predictor-load tax makes the E1 fleet sweep
  infeasible (end of M4).
- **F3** — `canary`'s prefix cache is not a faithful port of vLLM's block-pool
  semantics, invalidating RQ1/E2 (end of M4).
- **F4** — the shipped Mooncake CSV cannot be re-derived from upstream (end of
  M2).
- **F5** — `canary` proves defective enough that fixing it exceeds the
  from-scratch estimate (end of M4).
- **F6** — Mooncake at native lengths exceeds every model context Vidur ships,
  and no defensible filtering/scaling policy preserves the prefix structure RQ1
  measures (end of M2).

If F1 fires, the response is **not** an immediate switch: keep Vidur for
E1/E2/E4/E5 and reduce E3's scope, since `PROJECT_SPEC.md` already lists the
third heterogeneous mix as cut-if-behind. Any reversal is recorded as a new
superseding entry, never by editing this one.
