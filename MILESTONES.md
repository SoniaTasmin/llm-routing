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
**Week:** 2 · **State:** `DONE (approved)` · **Approved:** 2026-09-10

Approved on the recorded acceptance checklist below. **D-008 remains PROVISIONAL**
and all four of its gates remain **OPEN** — closing M2 does not close them.

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

**Acceptance criteria — verified 2026-09-10.**

| # | Criterion | Evidence | Status |
|---|---|---|---|
| 1 | **Vendoring + provenance** | Vidur `canary` at `25e0082dbbfb206fb0477c3ebbededa7ead78949`, extracted with `git archive` so it is provably that commit. MIT licence. **181** Python files, **1.4 MB**. Tree checksum in `VENDOR_TREE_SHA256` — **re-verified INTACT** after the working session. The 584 MB `data/` is not committed; `fetch_vidur_data.sh` retrieves it at the same SHA. `simulator/vendor/PROVENANCE.md` | ✅ |
| 2 | **Unified schema** | v1.0, `src/workload/schema.py`, documented in `docs/workload-schema.md`. Cache-blindness *declared* not inferred; block hashes mandatory when prefix structure is claimed; hashes cover whole **prefill** blocks only; every workload carries a provenance manifest | ✅ |
| 3 | **Mooncake re-derivation (F4)** | Re-derived from `kvcache-ai/Mooncake` @ `eeaca79`, `FAST25-release/traces/conversation_trace.jsonl`, sha256 `b8cbb061a85206d7…`. n=**12 031**, block_size **512** verified on 100 % of records. Realised sharing **38.19 %**. **F4 does not fire** — `docs/workload-mooncake-f4.md` | ✅ |
| 4 | **Native + D′ manifests** | Native preserved **immutable**. D′ variant `mooncake-conversation-trunc65536`: n=**12 031**, **0 dropped**, **257 altered** (2.14 %), block retention **0.9581**, reused-block retention **0.9692**, arrivals and output lengths **preserved exactly**, sharing 38.19 % → **38.63 % (+0.44 pp)**, timing proxy recorded as `UNVALIDATED PROXY` | ✅ |
| 5 | **Azure cache-blind loader** | conv **19 366** + code **8 819** requests. `prefix_structure=absent`, `realised_sharing=None`, `block_size=None`. Cache-blind **by construction** — the schema refuses to attach a sharing rate (D-004) | ✅ |
| 6 | **Synthetic φ generator** | Externally supplied block hashes (forced by the confirmed `hash_block_tokens` defect). Nominal → **measured** realised sharing: 0.0 → 0.0000 · 0.25 → 0.2360 · 0.5 → 0.4908 · 0.75 → 0.7413 · 0.9 → **0.8805**. Figures are seed-stable: spread **≤ 0.06 pp across 10 seeds** | ✅ |
| 7 | **F6 decision recorded before adoption** | Four analysis revisions; three user audits. Adopted provisionally as **D-008**. `docs/workload-mooncake-context-length-f6.md` | ✅ |
| — | **Validation** | **39 tests passing** (`pytest tests/ -q`). They caught two real defects: the φ generator producing 0.685 realised sharing for a nominal 0.9, and the truncation invariants | ✅ |

**State:** all seven criteria met and approved 2026-09-10.

### Incomplete / deliberately deferred

Nothing here blocks M2 closure; all of it is scheduled work or an open gate.

| Item | Owner | Note |
|---|---|---|
| **G4 block-size mapping** — workload hashes are 512-token, the simulator's KV block size is **forced to 16** by the profiling data. The 1→32 expansion is **specified, not implemented** | **M4** | Would otherwise under-count the cached region ~32×, biased toward making routing sophistication look worse than it is |
| **G1 end-to-end feasibility** — no long-context run performed; predictor-fit cost **has no defensible estimate** (the 11–14 h figure is withdrawn) | **M4** | Full fit not authorised |
| **G2 predictor behaviour** outside its training range — random-forest flat-lining is inferred, not measured | **M4** | |
| **G3 timing-proxy fidelity** — the `Meta-Llama-3-8B` profile as a stand-in for Llama-3.1-8B is architecturally supported but unvalidated | **M11 / E8** | |
| Larger **experiment-cell** seed counts (≥10 per cell, `PROJECT_SPEC.md` §11) | **M5** | **Not an unmet M2 criterion.** M2 required realised sharing to be *measured and reported*, which it is. §11's ≥10 seeds governs experiment cells, not workload generation. Generator stability was checked separately and is now a test: realised sharing varies by **≤ 0.06 pp across 10 seeds** at every φ, so the single reported figure per φ is representative |
| **Mooncake session derivation** — upstream has no `session_id`, and we decline the invented one in the shipped CSV | **M6** | Blocks session-sticky policies on Mooncake until a rule is recorded |
| a100 **TP=2 / TP=4** have no profiling data at all | M4/M7 | Must not be used as replica configurations without new profiling |

### D-008 gates — all four OPEN

**G1** M4 feasibility · **G2** M4 predictor behaviour outside training range ·
**G3** M11/E8 proxy fidelity · **G4** M4 block-size mapping.

D-008 is provisional by construction: G1, G2 and G4 cannot close before M4, and
G3 cannot close before M11.

**Explicitly NOT in this milestone.** Simulator modifications. Routing policies
B1/B2/B3/B4. Experimental sweeps. vLLM calibration. Kubernetes. Any change to
RQ2/E3 scope.

---

## M3 — vLLM calibration
**Week:** 3 · **State:** `PREPARATION IN PROGRESS — DEFERRED` (2026-09-11: user chose option 4, no spend authorised. Scope amended by **D-009**: fidelity work returned to M11.)

**Objective.** Obtain trustworthy timing data for the model and hardware this
study will simulate, so that every latency, cost and SLO number downstream rests
on measured behaviour rather than on a borrowed profile we have not checked.

Concretely, D-008 left us simulating a **Llama-3.1-8B-class** model using Vidur's
shipped `Meta-Llama-3-8B` profile as an **unvalidated proxy**. M3 is where that
proxy is either validated or replaced.

**Acceptance criteria.**
- [x] **Calibration plan written** — `docs/m3-calibration-plan.md`: exact GPU,
      model, software, fixed parameters, two-phase bounded run, costed options,
      and the M3→M4→M11 dependency map. **Awaiting the user's budget approval**,
      which is the user's action, not outstanding work.
- [ ] Vidur's profiler run on the chosen `(model, device, TP)` — **GPU-blocked**.
      Runbook ready and dry-runnable: `run_profiling.sh plan` prints exactly what
      would execute without touching a GPU. Collectives profiling is **not
      required**: our target replica config is TP=1.
- [ ] A short real-vLLM replay for **parameterisation** — **STAYS IN M3,
      DEFERRED** (D-009). M3's brief is "measure real vLLM timing behaviour";
      this is that requirement, blocked on budget rather than removed. M3 is
      **not** a GPU-free milestone.
- ~~A written verdict on **G3**~~ — **MOVED TO M11 by D-009.** That is a
      *fidelity* judgement feeding the error band, which is E8's job; and it
      could not be answered here anyway, since Vidur's profiler never loads
      weights and cannot distinguish two shape-identical configs.
- [ ] Everything reproducible from `REPRODUCE.md` — **partially met.**
      §3c is written and the CPU-side half (dry run, profile audit, tests) is
      reproducible today. The criterion stays **open** until a run records its
      exact CUDA / PyTorch / FlashInfer / `sarathi-serve` versions; those follow
      `sarathi-serve`'s own README and cannot be pinned before the environment
      is stood up.

**Prepared and complete (no GPU required).**
`docs/m3-calibration-plan.md` · `experiments/m3_calibration/run_profiling.sh`
(three phases: `plan` / `pilot` / `full`) · `src/workload/profile_audit.py` +
`profile_audit_cli.py` · `tests/test_profile_audit.py` (6 tests) ·
`REPRODUCE.md` §3c.

**Explicitly NOT in this milestone.** Routing policies. Experimental sweeps. The
full predictor fit (that is M4/G1). Any spend before approval.

---

## M4 — Simulator + single-replica validation
**Week:** 4 · **State:** `PLAN PREPARED` — `docs/m4-feasibility-plan.md`

Simulator (chosen base) validated against real single-replica measurements.
With M3 deferred (**D-009**) there are no new real measurements, so M4 narrows
to what the **shipped profiles** and the **D′ workload** can establish — which
is most of D-008's gates.

**Prepared, awaiting approval (all free, CPU only):**
1. Adopt the **G4a/G4b** 512→16 block-hash expansion in the workload build.
   Mapping implemented and tested; workload-level bias **measured at −0.88 pp**.
   **G4 is not resolved** — **G4c**, the system-level effect on cache-hit rate,
   p95 TTFT and *routing decisions*, is open and is not bounded by the −0.88 pp,
   which assumes an infinite cache.
2. **Run A** — a **basic integration check**, ~2 min, on M1's surviving cache
   (`a100 / Llama-2-7b-hf / TP=1`). It can falsify the integration cheaply. It
   establishes **nothing** about Llama-3.1-class or 65 536-token feasibility —
   different model, profile, predictor and context.
3. **G2 probe** — whether the random forest flat-lines outside its training
   range, answerable on the **existing** cache with **no fit at all**.

**Blocked:** **G1** long-context feasibility (needs an authorised predictor fit;
no wall-clock estimate is offered, and why not is stated in the plan) · **G3**
proxy fidelity (moved to M11 by D-009) · reconsidering D′ (needs M3, then
G4 + G1 + a superseding decision).

**Bounds fixed for any authorised fit:** 6 h wall cap · 5.5 GB RSS on a 7 GB
host · full log to file, never `tail` · one fit at a time · stop on MEAP > 5 %.

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
