# CLAUDE.md — Permanent Instructions for the Research Assistant

This file is the permanent operating contract for Claude (research/engineering
assistant) on this project. It is authoritative and must be re-read at the start
of every session. If this file and the conversation disagree, **this file wins**,
unless the user explicitly changes this file.

---

## 0. ROLE

You are the research/engineering assistant for an Erasmus Mundus Master's
application research project.

The repository is the **permanent source of truth**, NOT the Claude conversation.
Anything not written into the repository does not exist.

---

## 1. IMPORTANT WORKFLOW RULE

We work **ONE MILESTONE at a time**.

You must **NOT** jump ahead.

At the end of each milestone, **STOP** and wait for explicit approval from the user.

Never silently move to the next milestone.

---

## 2. PROJECT

Final title:

> **When Does Routing Sophistication Pay?
> A Controlled Evaluation of Load-, Cache-, and Cost-Aware Scheduling for LLM
> Inference on Heterogeneous, Preemptible Infrastructure**

The project is a research-oriented systems project intended to demonstrate
Master's-level ability for an Erasmus Mundus application.

---

## 3. RESEARCH FRAMING

We are **NOT** claiming to invent a new LLM routing algorithm.

The research question is:

> "When does routing sophistication actually provide practically significant
> benefits over strong queue-aware scheduling?"

The project is an **empirical characterization and reproducibility study**.

We want to determine when cache-, capability-, SLO-, and cost-aware routing
actually provides meaningful benefit.

Primary outcome:

> **Minimum infrastructure/fleet cost required to satisfy a fixed SLO.**

---

## 4. MAIN RESEARCH QUESTIONS

- **RQ1 — Cache locality.** At what level of prefix sharing does cache-aware
  routing become beneficial compared with strong queue-aware routing?
- **RQ2 — GPU heterogeneity.** When does capability-aware routing outperform
  strong queue-aware routing on heterogeneous GPU fleets?
- **RQ3 — Prediction.** How accurate is the completion-time predictor, and how
  does prediction error affect policy performance?
- **RQ4 — Resilience.** How does cache-locality interact with preemption/spot
  failure and gray failures?

**H4 is a major hypothesis:**

> Cache-sticky routing may suffer greater transient SLO degradation after replica
> preemption because losing a replica destroys concentrated cache state.

---

## 5. POLICIES

| ID | Policy | Role |
|----|--------|------|
| B1 | Round Robin | sanity/floor baseline |
| B2-req | JSQ(d) on request-count queue | queue-aware baseline |
| B2-tok | token/service-time-aware JSQ(d) | **STRONG PRIMARY BASELINE** |
| B3 | cache-aware routing with an overload guard | treatment |
| B4 | combined cache + capability + SLO/cost-aware routing | treatment |

Do **NOT** treat Round Robin as the meaningful competitor.
Beating B1 alone is **not** an interesting result.
The important comparison is **against B2-tok**.

---

## 6. CORE EXPERIMENTS

- **E1 — Minimum cost at fixed SLO.** *PRIMARY EXPERIMENT.*
- **E2 — Cache-sharing threshold.**
- **E3 — GPU heterogeneity.**
- **E4 — Preemption + gray failure.** *MAJOR RESULT / H4.*
- **E5 — Signal ablation.**
- **E6 — Predictor quality/noise.**
- **E7 — Overload / SLO-impossible regime.**
- **E8 — Simulator fidelity against real vLLM.**

Core MVP: **E1, E2, E3, E4, E5, E8**.

Cut if behind (in this order): E7, E6, Grafana polish, third heterogeneous mix,
Azure 2024, k3s, Tier-2 validation.

**Do not add new experiments without explicit approval.**

---

## 7. DATA

- **Primary real trace: Mooncake trace.** Purpose: prefix-sharing structure and
  realistic LLM serving workload.
- **Secondary: Azure LLM inference traces 2023/2024.** Purpose: realistic
  arrival/input/output length distributions.
  *Important:* Azure traces do not contain prompt content/prefix structure, so
  they are **cache-blind controls**.
- **Synthetic: controlled prefix-sharing parameter phi**, with
  `phi = {0, 0.25, 0.5, 0.75, 0.9}`.
  The synthetic generator must **measure the realised prefix-sharing rate**
  rather than merely assuming it.

---

## 8. ARCHITECTURE

```
Traces
    |
Unified workload loader
    |
Router
    |
Heterogeneous simulated replica fleet
    |
Timing model / KV cache / Prefix cache / Eviction /
Queue state / Cost / Failure injection
    |
Per-request raw results
    |
Statistical analysis
    |
Figures / report
```

Real validation path:

```
Same router code where practical -> small vLLM testbed -> real measurements
    -> simulator fidelity validation
```

The real testbed is **VALIDATION**, not the main research platform.
Do not build unnecessary production infrastructure.

---

## 9. SIMULATOR DECISION (MILESTONE 1)

Milestone 1 is a **3-day simulator-base spike**.

Evaluate:
1. Vidur
2. LLMServingSim

Against these requirements:
1. Multiple replicas
2. Pluggable routing
3. Cross-replica prefix-cache state
4. Heterogeneous replica types
5. Mid-run replica removal/failure
6. SLO/deadline modelling
7. Cost accounting
8. Per-request metrics

Rules:
- Do **NOT** decide in advance that we will use Vidur.
- Do **NOT** decide in advance that we will use LLMServingSim.
- Do **NOT** immediately build our own simulator.
- If one existing simulator can support the project cleanly, **extend it**.
- If neither is suitable, build a **small cluster-level discrete-event simulator**.
- Do **NOT** build a full LLM operator simulator from scratch unless there is a
  compelling demonstrated reason.
- Document the decision in `DECISIONS.md`.

---

## 10. IMPORTANT SCOPE CUTS

Do **NOT** build:

provisioning controller · Terraform · ArgoCD · KEDA · Karpenter · Kafka ·
service mesh · OpenTelemetry · RAG · vector database · agents · fine-tuning ·
multi-cloud · Raft · large models · custom web dashboard

The simulator can directly search fleet configurations for the minimum-cost fleet.

Kubernetes is **only** validation infrastructure.

---

## 11. STATISTICAL PRINCIPLES

- Use identical seeded workloads across policies.
- Primary experiments: **at least 10 seeds per cell**.
- Use **bootstrap 95% confidence intervals**.
- Use **paired comparisons** where appropriate.
- Report **effect size**, not merely statistical significance.
- Use enough requests for meaningful tail latency.

**Practical significance thresholds are FROZEN:**

| Metric | Threshold |
|--------|-----------|
| Cost | >= 10% difference |
| Latency | >= 15% p95 TTFT |
| SLO attainment | >= 2 percentage points |

Effects smaller than the measured simulator-fidelity error band are
**inconclusive**.

**Never fabricate measurements.**

Every number must be clearly labelled as one of:
- `measured result`
- `hypothesis`
- `estimate`
- `assumption`

---

## 12. FROZEN 12-WEEK PLAN

| Week | Content |
|------|---------|
| 1 | Simulator-base spike |
| 2 | Trace loaders + unified format + synthetic phi generator |
| 3 | vLLM calibration |
| 4 | Simulator + single-replica validation |
| 5 | B1/B2 + metrics/statistics |
| 6 | B3 |
| 7 | Heterogeneity |
| 8 | B4 + ablations |
| 9 | Minimum-cost/SLO experiment |
| 10 | Failure experiments |
| 11 | Real testbed/fidelity |
| 12 | Analysis/report/reproducibility |

A defensible primary result should exist by **Week 9**.

---

## 13. REPOSITORY MEMORY SYSTEM

The repository is the permanent memory of the project.

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Permanent instructions and rules for the assistant |
| `PROJECT_SPEC.md` | Frozen Milestone-0 research specification |
| `CURRENT_STATUS.md` | What is happening RIGHT NOW |
| `MILESTONES.md` | Milestone tracker |
| `DECISIONS.md` | Important technical/research decisions and rationale |
| `NOTEBOOK.md` | Chronological research diary, including failed attempts |
| `REPRODUCE.md` | How to reproduce the project from a clean clone |
| `README.md` | Public-facing project overview |

Directories: `src/`, `simulator/`, `workloads/`, `experiments/`, `analysis/`,
`configs/`, `tests/`, `results/`, `docs/`.

---

## 14. MILESTONE PROTOCOL

For every milestone, in order:

1. State objective.
2. State acceptance criteria.
3. State plan.
4. Identify files to create/change.
5. Implement only the approved scope.
6. Run verification/tests.
7. Record evidence.
8. Update `CURRENT_STATUS.md`.
9. Update `MILESTONES.md`.
10. Update `DECISIONS.md` if a decision was made.
11. Update `NOTEBOOK.md`.
12. Update `REPRODUCE.md` when relevant.
13. Make a meaningful git commit.
14. **STOP.**

---

## 15. GIT

- Use Git throughout.
- Make meaningful commits.
- **Never rewrite research history.**
- Failed experiments and rejected approaches should be **documented, not erased**.
- Remote: `https://github.com/SoniaTasmin/llm-routing.git` (public), on the
  GitHub account **SoniaTasmin**.
  **Never** push this project to the user's office GitLab account.
- **Do not add AI co-authorship trailers to commits.** No
  `Co-Authored-By: Claude ...` and no `Claude-Session:` line. Decided
  2026-08-31: this is a public repository backing an academic application, and
  the user does not want per-commit AI attribution baked into permanent public
  history. Tool use is disclosed in the project documentation instead, not in
  every commit.
- Git identity is configured **repo-locally** to avoid inheriting an office
  identity.

---

## 16. CURRENT STATE

- **Milestone 0: APPROVED AND FROZEN.**
- **Current milestone: MILESTONE 1 — SIMULATOR-BASE SPIKE.**
- Nothing from Milestone 2 onward is to be implemented yet.

See `CURRENT_STATUS.md` for the live state.
