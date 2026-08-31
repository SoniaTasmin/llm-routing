# MILESTONES.md — Milestone Tracker

Legend: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `DONE (approved)` ·
`CUT` · `DEFERRED`

A milestone becomes `DONE` **only** on explicit user approval.

---

## M0 — Research specification
**Week:** 0 · **State:** `DONE (approved)` · **Frozen:** 2026-08-31

**Objective.** Fix the research framing, questions, policies, experiment set,
data sources, statistical principles and 12-week plan.

**Acceptance criteria.**
- [x] Title fixed.
- [x] RQ1–RQ4 and H4 fixed.
- [x] Policy set B1 / B2-req / B2-tok / B3 / B4 fixed, with B2-tok named as the
      strong primary baseline.
- [x] Experiment set E1–E8 fixed, MVP subset and cut order fixed.
- [x] Data sources fixed (Mooncake primary, Azure secondary/cache-blind,
      synthetic phi sweep with *measured* realised sharing).
- [x] Statistical principles and frozen practical-significance thresholds fixed.
- [x] Scope cuts fixed.
- [x] 12-week plan fixed.

**Evidence.** `PROJECT_SPEC.md` (frozen).

---

## M1 — Simulator-base spike
**Week:** 1 · **Budget:** 3 days · **State:** `IN PROGRESS`

**Objective.** Decide the simulation base for the whole project: extend Vidur,
extend LLMServingSim, or build a small cluster-level discrete-event simulator.

**Acceptance criteria.**
- [ ] Both Vidur and LLMServingSim obtained and actually run at least once (or a
      documented, evidenced reason why one could not be run).
- [ ] Both scored against R1–R8 with **concrete evidence** (repository paths,
      file/line references, API surfaces), not impressions.
- [ ] Estimated extension effort per candidate for the requirements it fails.
- [ ] A single recommendation with rationale, including what would falsify it.
- [ ] Decision recorded in `DECISIONS.md` with date and rationale.
- [ ] Failed attempts and dead ends recorded in `NOTEBOOK.md`.
- [ ] Spike artefacts committed under `docs/spike/`.

**Requirements to score (from `PROJECT_SPEC.md` §9).**
R1 multiple replicas · R2 pluggable routing · R3 cross-replica prefix-cache
state · R4 heterogeneous replica types · R5 mid-run replica removal/failure ·
R6 SLO/deadline modelling · R7 cost accounting · R8 per-request metrics.

**Explicitly NOT in this milestone.** Implementing B1/B2/B3/B4. Building the
simulator. Downloading traces. Kubernetes. Running the experiment matrix.

**Sub-status.**
- [x] Repository scaffolding + memory system created (2026-08-31).
- [ ] Spike itself — **awaiting explicit user approval to proceed.**

---

## M2 — Trace loaders + unified format + synthetic phi generator
**Week:** 2 · **State:** `NOT STARTED`

Unified workload record format; Mooncake loader; Azure 2023 loader (cache-blind
control); synthetic generator with phi in {0, 0.25, 0.5, 0.75, 0.9} that
**measures** realised prefix sharing.

---

## M3 — vLLM calibration
**Week:** 3 · **State:** `NOT STARTED`

Measure real vLLM timing behaviour to parameterise the simulator's timing model.

---

## M4 — Simulator + single-replica validation
**Week:** 4 · **State:** `NOT STARTED`

Simulator (chosen base) validated against real single-replica measurements.

---

## M5 — B1/B2 + metrics/statistics
**Week:** 5 · **State:** `NOT STARTED`

Round Robin, JSQ(d) request-count, JSQ(d) token-aware; per-request result
schema; bootstrap CI + paired-comparison analysis harness.

---

## M6 — B3 cache-aware routing
**Week:** 6 · **State:** `NOT STARTED`

Prefix-affinity routing with overload guard.

---

## M7 — Heterogeneity
**Week:** 7 · **State:** `NOT STARTED`

Heterogeneous replica types and capability-aware routing (RQ2 / E3).

---

## M8 — B4 + ablations
**Week:** 8 · **State:** `NOT STARTED`

Combined cache + capability + SLO/cost policy; signal ablation (E5).

---

## M9 — Minimum-cost / SLO experiment
**Week:** 9 · **State:** `NOT STARTED`

**E1, the primary experiment. A defensible primary result must exist by the end
of this milestone.**

---

## M10 — Failure experiments
**Week:** 10 · **State:** `NOT STARTED`

E4: preemption and gray failure; direct test of **H4**.

---

## M11 — Real testbed / fidelity
**Week:** 11 · **State:** `NOT STARTED`

E8: simulator fidelity against real vLLM; produces the fidelity error band used
by the inconclusiveness rule.

---

## M12 — Analysis / report / reproducibility
**Week:** 12 · **State:** `NOT STARTED`

Final analysis, figures, report, and a `REPRODUCE.md` that works from a clean
clone.

---

## Cut-if-behind register

| Rank | Item | State |
|------|------|-------|
| 1 | E7 (overload / SLO-impossible regime) | in plan, first to cut |
| 2 | E6 (predictor quality / noise) | in plan, second to cut |
| 3 | Grafana polish | in plan |
| 4 | third heterogeneous mix | in plan |
| 5 | Azure 2024 | in plan |
| 6 | k3s | in plan |
| 7 | Tier-2 validation | in plan |
