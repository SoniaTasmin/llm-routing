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
**Amended:** **CLARIFIED AND PARTIALLY CORRECTED BY D-007 (2026-09-10).** The text
below is preserved exactly as accepted. Four of its claims are corrected in
D-007; read them together. The *decision* — extend Vidur `canary` at `25e0082` —
is unchanged.

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


---

## D-007 — Clarifications and partial corrections to D-006
**Date:** 2026-09-10 · **Status:** ACCEPTED · **Clarifies:** D-006 (does **not** supersede it)

**Context.** The user reviewed the completed M1 report before approving the
milestone and identified four claims in D-006 and its supporting documents that
were overstated, under-specified, or arithmetically inconsistent. D-006's
*decision* survives review unchanged. Its *supporting argument* needed four
repairs, recorded here rather than by editing an accepted entry.

**Decision.** D-006 stands: extend Vidur, branch `canary`, vendored and pinned at
`25e0082dbbfb206fb0477c3ebbededa7ead78949`. The following four clarifications
attach to it and take precedence over the corresponding passages in D-006 and in
`docs/spike/*`.

### C1 — The throughput ratio is indicative, not a controlled comparison

D-006 said the ~5.5× per-request gap was "like for like, both with prefix
caching". **That is withdrawn.** Enabling prefix caching on both simulators does
not make their workloads equivalent. The two runs differ in trace (512 real
Mooncake requests ≤4 096 tokens vs 300 synthetic 1 024-token prompts), replica
count (4 vs 2), replica scheduler, cache topology and measured hit rate (32.69 %
vs 49.67 % NPU + 0.17 % CPU).

Correct statement: across the configurations actually run, Vidur's per-request
simulation cost was **indicatively single-digit times lower** — nominally ~5.5×.
A controlled comparison was **not** performed and will **not** be performed: it
would cost a day to strengthen a contributing argument, and the decision rests on
R2, R5 and R7, none of which is a throughput question. What *is* structural, and
independent of the ratio, is that Vidur runs in-process (many E1 cells per
interpreter) while each LLMServingSim run is a container plus a subprocess.

### C2 — Effort total corrected to 13–22 engineer-days

D-006's supporting matrix totalled **13.5–22.5 d**. Re-derived from the rows:
3–5 (R4) + 3–5 (R5) + 1–2 (R6) + 4–7 (R7) + 0 (R8) + 2–3 (R3) = **13–22 d**.

The discrepancy was a stale 0.5 d on the **R8** row for "add `replica_id` and
`arrived_at` columns". Re-checking run 4b's output settles it: `canary` already
emits `replica` (col 25), `request_arrived_at` (col 24) and
`request_num_prefill_tokens_cached` (col 20). R8 costs **0 d** on the branch we
chose; the 0.5 d applied to `main`, which we are not using.

**The 13–22 d figure covers only closing the R1–R8 gaps in the simulator base.**
Explicitly *additional and not included*: implementing policies B1/B2-req/B2-tok/
B3/B4 (M5–M8); the symmetric tuning protocol (C3); resolving Mooncake's
context-length constraint, falsifier F6 (M2/M4, **not yet estimated**); the
statistical analysis harness (M5); the E8 fidelity comparison (M11).

### C3 — An upstream router reduces some implementation bias; it does not remove tuning bias

D-006 rationale item 5 said that building the treatment on upstream's own
cache-aware router means "we cannot be accused of tuning the treatment to win".
**Overstated; withdrawn.**

What holds: starting from `tolerant_sticky_lop_uncached` and its siblings reduces
one specific risk — that we author a treatment whose code we shaped, consciously
or not, toward the outcome we expect. A negative result about an implementation
we did not write is a modestly stronger position than one about a router we did.

What does **not** hold, and is now explicit project work:

1. **Equivalence is unverified.** `PROJECT_SPEC.md` §5 specifies B3 as
   "prefix-affinity routing with a guard that sheds affinity under load".
   Whether `tolerant_sticky_lop_uncached` *is* that policy is an open question to
   be answered by reading and testing it against the spec. If it diverges we
   either adopt its definition explicitly and say so, or implement the specified
   policy ourselves. **Owner: M6.**
2. **Parameter selection is still ours.** `tolerance_factor`, B2-tok's `d`, and
   the service-time estimator are free parameters. Whoever wrote the code, *we*
   choose the values, and bias enters through tuning the treatment more carefully
   than the baseline. Mitigation: a **documented tuning protocol applied
   symmetrically** to B2-tok and to B3/B4 — same search budget, same selection
   criterion, same seeds — written down **before** the headline runs.
   **Owner: M5 (protocol), M8 (application).**

### C4 — F1 is checked by a bounded probe at M4; the R4 implementation stays at M7

D-006 dated F1 "end of M4" while assigning R4 to M7, without saying how a
requirement implemented in week 7 could be falsified in week 4. Resolved by
defining the check separately from the implementation, in
`docs/spike/recommendation.md` §5a: a **time-boxed 1-day probe** that (i)
re-greps the coupling surface against the 4 sites the spike found, (ii)
instantiates two `ExecutionTimePredictor`s for different `(model, device)` pairs
in one interpreter and confirms they coexist — the step the spike *inferred* from
source rather than executed, and the one most likely to surprise us — and (iii)
runs a 2-replica differing-device smoke test behind a throwaway patch that is
discarded, not merged. CLI plumbing, metrics, cost attribution and
capability-aware routing are **excluded** and remain M7.

### C5 — Dropping heterogeneity is not the same decision as dropping the third fleet mix

D-006's F1 fallback said E3 "may be reduced in scope, since `PROJECT_SPEC.md`
already lists the third heterogeneous mix as cut-if-behind". **That conflated two
different decisions and is corrected.**

The frozen cut-if-behind register sanctions dropping *one additional fleet
composition*. It does not sanction dropping heterogeneity, which would delete
**RQ2** and **E3** — both frozen MVP items.

| Change | Status |
|---|---|
| Drop the *third* heterogeneous fleet mix, keep two | already sanctioned by the frozen register |
| Reduce E3 to a single heterogeneous mix | **requires explicit user approval** |
| Drop E3 / RQ2 entirely | **requires explicit user approval**; amends the frozen `PROJECT_SPEC.md` |

If F1 fires, the assistant presents measured effort, options and a
recommendation. It does not shrink the research question on its own authority.

**Consequences.** No change to the simulator base, the vendoring plan, or the
milestone schedule. Two pieces of previously-unnamed work are now named and
owned: the B3-equivalence check (M6) and the symmetric tuning protocol (M5/M8).
The R4 feasibility probe (M4) is specified rather than implied.

**Would falsify this.** C1–C5 are corrections to reasoning, not empirical claims,
so they are not independently falsifiable. The six falsifiers in
`docs/spike/recommendation.md` §5 continue to govern D-006, with F1's trigger now
defined by §5a.

---

## D-008 — Mooncake context-length policy: D′, provisional
**Date:** 2026-09-10 · **Status:** ACCEPTED (**PROVISIONAL** — feasibility and fidelity gates open) · **Resolves:** falsifier F6

**Context.** Mooncake is the primary trace for RQ1. Its requests reach 126 527
tokens (median 7 255, p95 40 056). Vidur's shipped decode profiling stops at
65 536 tokens of per-sequence context. Every way of reconciling the two changes
either the workload or the timing model's evidential basis, so this is a research
decision, not a configuration detail.

Three successive analyses were required. Rev 1 recommended raising
`max_model_len` on Meta-Llama-3-8B — a hypothetical model, since the released
window is 8 192. A user audit found six errors and it was withdrawn. Rev 2
proposed D′ but reported profiling counts that did not reconcile and overstated
three claims. Rev 3, after a per-device per-TP coverage audit, supports D′ with
qualifications. Full evidence:
`docs/workload-mooncake-context-length-f6.md`.

**Decision.** Adopt **D′** as the provisional workload policy:

1. **Model/profile substitution.** Simulate a **Llama-3.1-8B-class** model using
   Vidur's shipped `meta-llama/Meta-Llama-3-8B` timing profile as an
   **unvalidated proxy**. Recorded as an `assumption` in every dependent manifest.
2. **Workload variant.** Truncate to a **65 536-token** context budget, emitted as
   a **separately named** workload. The native trace is **immutable** and
   preserved beside it.
3. **What the truncation preserves:** arrival times exactly, output lengths
   exactly, request count (0 dropped). Only prompts are capped, at
   `budget − num_decode_tokens`.
4. **Prefix hashes:** truncated to surviving **whole** blocks from the head.
   Chained hashes make head-truncation the only structure-preserving edit — the
   retained ids still identify the prefixes they identified before.
5. **All transformations and retention metrics recorded** in the manifest.

**Measured result** (`workloads/derived/mooncake-conversation-trunc65536.jsonl`):
12 031 requests, **0 dropped**, **257 altered** (2.14 %), **95.81 %** of prefix
blocks and **96.92 %** of reused blocks retained, realised sharing 38.19 % →
**38.63 % (+0.44 pp)**, arrivals and output lengths preserved.

**Rationale.**

1. **Coverage supports it, verified jointly rather than by column maxima.** For
   a100 TP=1: decode covers kv ≤ 65 536 at every batch size 1–64, and every
   memory-feasible `(batch, kv)` point is inside the profiled grid; prefill covers
   all 16 KV steps needed to chunk-prefill a 65 536-token prompt at chunk 4 096,
   with 0 missing. Same holds on h100 TP=1/2/4/8 and a100 TP=8.
2. **Native would move 2.14 % of requests outside the timing model's evidence.**
   Vidur's prediction grid runs to 262 144 while decode training data stops at
   65 536; a random forest flat-lines beyond its training range, systematically
   under-estimating the longest and costliest requests. D′ trades a **measured**
   +0.44 pp workload distortion for removing an **unmeasured** timing error.
3. **The architecture match supports the proxy without establishing it.** Every
   parameter determining FLOPs and KV bytes per token is identical between
   Meta-Llama-3-8B and Llama-3.1-8B. That is a principled reason to expect
   transfer; it is not a measurement, and the profile was itself swept at
   `max_model_len = 262 144` on a model whose released window is 8 192.
4. **Reversible at no cost.** The native trace is preserved. Adding decode
   profiling above 65 536 at M3 would permit a native run later.

**Alternatives rejected.**

- **Native, untruncated** — 0 pp workload distortion, but 2.14 % of requests fall
  outside profiled decode data. Remains the preferred end state *if* M3 adds the
  profiling. Not rejected permanently; deferred.
- **Consistent scaling** — preserves the sharing ratio exactly (0.00 pp at every
  factor, verified). Rejected for **loss of external validity**, not for breaking
  the timing model: a scaled workload is priced correctly but is no longer
  Mooncake, and exercises a different operating regime.
- **Truncate at 32 768** — +1.05 pp, 85.2 % of blocks. Strictly worse than D′ on
  every axis and needs the same model substitution.
- **Fit the released 8 192 window** (drop or truncate at 8k) — +4.16 / +6.36 pp,
  retaining 13.5 % / 43.2 % of prefix blocks. Discards most of the structure RQ1
  measures.

**Consequences.**

- Two Mooncake workloads exist from now on. Results must state which was used;
  the native one is not a drop-in substitute and vice versa.
- The +0.44 pp inflation is a known, recorded bias in the direction of *more*
  apparent sharing. It is far below the frozen practical-significance thresholds
  (`PROJECT_SPEC.md` §11) but must be carried into RQ1's interpretation.
- Every result depending on this carries an unvalidated timing proxy until M11.
- a100 TP=2 and TP=4 have **no** profiling data and must not be used as replica
  configurations without new profiling.

**Gates that remain OPEN — this decision is not final until all three close.**

| Gate | Milestone | Question |
|---|---|---|
| **G1 feasibility** | M4 | Does an end-to-end long-context run complete, at what predictor-fit cost and peak memory? **No defensible cost estimate exists** — see below. |
| **G2 predictor behaviour** | M4 | Does Vidur's random forest flat-line outside its training range as assumed? |
| **G3 fidelity** | M11 / E8 | Does the Meta-Llama-3-8B profile represent real Llama-3.1-8B at long context, or is additional profiling required? |
| **G4 block-size mapping** | M4 | Split into three sub-gates 2026-09-11. **G4a** mapping specified and implemented without inventing prefix information — **DONE** (`workload.transforms.expand_block_hashes`, `child(h,j) = h*32 + j`; sub-512 tails get unique never-matching ids). **G4b** workload-level sharing bias quantified — **DONE**, −0.88 pp on D′ (2.27 % of blocks are unknown-sharing tails). **G4c** system-level consequence — change in simulated cache-hit rate, p95 TTFT and **routing decisions** — **OPEN, UNMEASURED**. G4b is computed under infinite-cache assumptions and does **not** bound G4c: the simulator runs a finite evicting pool, and B3/B4 route on `get_cached_prefill_length`, whose resolution changes 32× under the expansion, so the router can make *different* decisions. G4 is **not resolved**. |

**On the predictor fit cost.** An earlier estimate of 11–14 h has been
**withdrawn**. It extrapolated from whole-device row totals, but
`_load_attention_df` filters training rows by `num_tensor_parallel_workers`; the
post-filter ratio for a100 TP=1 is **4.46×** (14 650 → 65 268 attention rows), not
2.45×. No replacement estimate is defensible: M1's log was captured with `tail`,
so only 4 of 11 trained operations are visible, covering ~10 m 43 s of a
4 h 36 m 47 s run, and the remaining ~4 h 26 m is unattributed. **Measure at M4.**

**Would falsify this.** G1 failing on available hardware (→ reconsider budget or
model). G2 showing the predictor does something other than flat-line (→ re-open
native). G3 showing the proxy does not transfer (→ new profiling at M3, or a
different model). Any reversal is recorded as a superseding entry, never by
editing this one.

---

## D-009 — Sequencing amendment: return the fidelity work to M11; defer paid GPU execution
**Date:** 2026-09-11 · **Status:** **PROPOSED — AWAITING USER APPROVAL** · **Proposes to amend:** the M3 acceptance criteria (not `PROJECT_SPEC.md`'s frozen plan)

> **Status correction, 2026-09-11.** This entry was first written with
> `Status: ACCEPTED`. That was wrong: the user asked me to *propose* a
> sequencing amendment for approval, and I marked my own proposal accepted.
> Only part 3 below — that no paid GPU execution is authorised — is the user's
> decision. Parts 1, 2 and 4 are proposals awaiting a ruling.

**Context.** Two things need reconciling, and one of them is a mistake of mine.

**1. I put M11's work into M3's acceptance criteria.** The frozen milestone
history is unambiguous about the split:

| Milestone | `MILESTONES.md`, as written at M0 |
|---|---|
| **M3** | "Measure real vLLM timing behaviour to **parameterise the simulator's timing model**." |
| **M11** | "**E8: simulator fidelity against real vLLM**; produces the fidelity error band used by the inconclusiveness rule." |

M3 *produces* timing data. M11 *validates* it. When I wrote M3's detailed
acceptance criteria at 2026-09-10 I added two that belong to M11:

- "A short real-vLLM replay on the same hardware, for comparison."
- "A written verdict on **G3**: does the shipped profile represent our model?"

Both are fidelity validation — E8's definition. Neither is parameterisation.
This was scope creep introduced by me, not by the plan.

It also could not have succeeded where it sat. A later finding
(`docs/m3-calibration-plan.md` §2) establishes that Vidur's profiler never loads
weights, so re-running it cannot distinguish two shape-identical configs. G3 is
**structurally** an M11 question: only a comparison against real vLLM serving
real weights can answer it.

**2. The user has declined paid GPU execution for now** (option 4), with the
explicit condition that deferral must not harden any provisional decision.

**Proposed (1, 2, 4) and decided by the user (3).**

1. **PROPOSED — move the real-vLLM replay and the G3 verdict from M3 to M11**,
   where the frozen plan already put the fidelity work. M3's acceptance criteria are
   amended to cover parameterisation only:
   - a costed calibration plan (**met**);
   - Vidur's profiler run on the chosen `(model, device, TP)` (**GPU-blocked**);
   - reproducibility from `REPRODUCE.md` (**partially met**, open pending
     recorded environment versions).
2. **PROPOSED — M3 stays `PREPARATION IN PROGRESS` — not "done", not "cut".** Its remaining
   criteria are blocked on a budget decision the user has deferred, not on work.
3. **DECIDED BY THE USER 2026-09-11 — no paid GPU execution is authorised.** Nothing may be rented or charged
   without an explicit, separately approved budget.
4. **PROPOSED (and entailed by 3) — D-008 stays PROVISIONAL and all four of its gates stay OPEN.** Deferring M3
   changes none of that.

**Rationale.** `PROJECT_SPEC.md` §12's twelve-week plan is frozen and this does
not amend it — it restores M3 and M11 to the division of labour the frozen plan
already stated, which my detailed criteria had blurred. Recording it as an
amendment rather than editing the criteria silently is the point: a reader
comparing M3's criteria across revisions would otherwise see two requirements
disappear with no explanation.

**Consequences.**

- M3 can be completed, when funded, **without** any real-vLLM work. That makes
  its budget smaller and its scope cleaner.
- M11 gains two explicit inputs it already implied: the replay harness and the
  G3 verdict. Its estimate should grow accordingly when M11 is planned.
- Until M3 is funded, the simulator runs on the shipped profile as an
  **unvalidated proxy**, and every result carries that `assumption`.

**Explicitly NOT decided here.** That D′ is permanent — it is not. D-008 remains
provisional, the native trace is preserved unmodified, and the truncation is a
one-line change to the workload build. Deferring M3 leaves the *reason* for D′
standing; nothing about it hardens with time.

**Would falsify this.** Evidence that M3's parameterisation cannot be validated
at M11 for some structural reason, which would mean the split does not work and
the fidelity work must move earlier.
