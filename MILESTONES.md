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
**Week:** 1 · **Budget:** 3 days · **State:** `DONE (approved)` · **Approved:** 2026-09-10

Approved subject to six corrections, all applied before closure. The user's
review caught four overstated or inconsistent claims that the assistant had not;
they are recorded in **D-007** rather than by editing the accepted D-006:
C1 throughput ratio is indicative not controlled · C2 effort total 13–22 d not
13.5–22.5 d · C3 an upstream router reduces some implementation bias but does not
remove tuning bias · C4 F1 is a bounded M4 probe, R4 implementation stays at M7 ·
C5 dropping heterogeneity ≠ dropping the third fleet mix, and needs approval.
Plus four documentation inconsistencies fixed (stale remote-sync text, undercounted
run totals, "five falsifiers" where there are six, 57 s vs 32 s predictor tax).

**Objective.** Decide the simulation base for the whole project: extend Vidur,
extend LLMServingSim, or build a small cluster-level discrete-event simulator.

**Acceptance criteria.**
- [x] Both Vidur and LLMServingSim obtained and actually run at least once.
      **Run counts corrected 2026-09-10** — the original text undercounted both
      candidates. Nine runs in total, seven usable:
      Vidur `main`: 3 (4 replicas ×128 req; an identical repeat to test
      determinism; 8 replicas ×2048 req).
      Vidur `canary`: **2** (full Mooncake trace — *crashed*, operator
      misconfiguration, see `NOTEBOOK.md` item 9; then a 512-request fitting
      subset — exit 0).
      LLMServingSim: **4 usable** (single instance; 2 instances with a shared CPU
      prefix pool; a hand-written mixed RTX4090+RTXPRO6000 fleet; a 300-request
      throughput probe) **plus 2 discarded** as CPU-contaminated.
      Neither candidate had to be judged unrun.
- [x] Both scored against R1–R8 with **concrete evidence** — file/line
      references, API surfaces, CLI probes and run output, not impressions.
      `docs/spike/requirements-matrix.md`. Vidur's `main` and `canary` branches
      were scored **separately**, because `main`'s README directs users needing
      prefix caching and routing policies to `canary`; they are different
      simulators for our purposes.
- [x] Estimated extension effort per candidate for every failed **and partial**
      requirement, in engineer-days, each with its basis stated and labelled
      `estimate`. `requirements-matrix.md` §3.
- [x] A single recommendation with rationale and **six dated falsifiers**.
      `docs/spike/recommendation.md`.
- [x] Decision recorded in `DECISIONS.md` as **D-006** (supersedes D-005).
- [x] Failed attempts, stalls and dead ends recorded in `NOTEBOOK.md`.
- [x] Spike artefacts committed under `docs/spike/`.

**Requirements to score (from `PROJECT_SPEC.md` §9).**
R1 multiple replicas · R2 pluggable routing · R3 cross-replica prefix-cache
state · R4 heterogeneous replica types · R5 mid-run replica removal/failure ·
R6 SLO/deadline modelling · R7 cost accounting · R8 per-request metrics.

**Explicitly NOT in this milestone.** Implementing B1/B2/B3/B4. Building the
simulator. Downloading traces. Kubernetes. Running the experiment matrix.

**Sub-status.**
- [x] Repository scaffolding + memory system created (2026-08-31).
- [x] Spike executed 2026-09-01 → 2026-09-02.

**Outcome.** **Extend Vidur**, branch `canary`, pinned at
`25e0082dbbfb206fb0477c3ebbededa7ead78949`. Vidur `canary` fails only R4
(heterogeneous replicas) and R5 (replica failure) outright; LLMServingSim wins
R4 but is only partial on R2 (its routing hook never receives the request) and
fails R5, R6 and R7, with R5 crossing a process boundary into C++.

**Carried into later milestones as work, not as risk-free assumptions:**
R4 heterogeneity (M7, `estimate` 3–5 d; feasibility probe at M4 per D-007 C4),
R5 failure injection (M10, `estimate` 3–5 d), R6 SLO attainment (M9, 1–2 d),
R7 cost + fleet search (M9, 4–7 d), R3 bounded router-side cache view (M4/M6,
2–3 d). **Total 13–22 d** — simulator-base gaps only. Additional and *not*
included: policy implementation B1–B4 (M5–M8), the symmetric tuning protocol
(M5/M8, D-007 C3), Mooncake context-length resolution (M2/M4, F6, unestimated),
the analysis harness (M5), E8 fidelity (M11).

**Note for M2.** Vidur `canary` ships a preprocessed Mooncake trace with block
hashes and session ids. It is **not** to be adopted on trust — re-deriving it
from the upstream trace is falsifier F4 in `recommendation.md`.

---

## M2 — Trace loaders + unified format + synthetic phi generator
**Week:** 2 · **State:** `IN PROGRESS` (started 2026-09-10)

**Objective.** A unified workload record format, three loaders that emit it, and
a synthetic generator whose realised prefix sharing is *measured* rather than
assumed — so that every later milestone consumes one schema regardless of source.

**Approved scope.**
1. Vendor Vidur `canary` at `25e0082` with licence and provenance preserved.
2. Define the unified workload schema.
3. Re-derive the Mooncake workload from upstream; check its prefix structure
   against the CSV `canary` ships (falsifier **F4**).
4. Azure 2023 cache-blind control loader (D-004).
5. Synthetic phi generator, phi in {0, 0.25, 0.5, 0.75, 0.9}, with **externally
   supplied block hashes** (forced by the confirmed `hash_block_tokens` defect)
   and **measured** realised prefix sharing.
6. Investigate Mooncake's context-length constraint (**F6**) early and present
   options for a user decision before adopting any of them.

**Acceptance criteria.**
- [ ] Vidur `canary` vendored at the exact D-006 SHA, licence + provenance recorded.
- [ ] Unified workload schema defined, documented, and versioned.
- [ ] Mooncake re-derived from upstream and compared against the shipped CSV,
      with a written verdict on F4.
- [ ] Azure 2023 loader emitting the unified schema, with prefix fields
      explicitly absent (cache-blind by construction, not by omission).
- [ ] Synthetic generator emitting block hashes, with realised prefix sharing
      **measured** and reported alongside nominal phi.
- [ ] Loader/generator correctness tests — only what establishes correctness.
- [ ] F6 options presented to the user; decision recorded before adoption.

**Explicitly NOT in this milestone.** Simulator modifications. Routing policies
B1/B2/B3/B4. Experimental sweeps. vLLM calibration. Kubernetes. Any change to
RQ2/E3 scope.

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
