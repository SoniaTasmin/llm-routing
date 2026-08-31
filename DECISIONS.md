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
**Date:** 2026-08-31 · **Status:** ACCEPTED (open decision — to be resolved in M1)

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

## D-006 — Simulator base selection
**Date:** *(pending — Milestone 1 output)* · **Status:** NOT YET DECIDED

*Placeholder. To be written when the M1 spike completes. Must cite the R1–R8
scoring matrix in `docs/spike/`.*
