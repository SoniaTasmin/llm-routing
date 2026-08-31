# When Does Routing Sophistication Pay?

**A Controlled Evaluation of Load-, Cache-, and Cost-Aware Scheduling for LLM
Inference on Heterogeneous, Preemptible Infrastructure**

---

## What this is

An empirical characterization and reproducibility study of LLM inference
routing. It is a research-oriented systems project.

**It does not propose a new routing algorithm.** It asks a different question:

> **When does routing sophistication actually provide practically significant
> benefits over strong queue-aware scheduling?**

Cache-aware, capability-aware and cost-aware routers are widely reported to beat
simple load balancing. Those comparisons are often made against weak baselines
(round robin, least-connections) and at a single load point. This project
measures where the benefit actually begins and where it disappears, against a
deliberately strong queue-aware baseline, under controlled prefix sharing, GPU
heterogeneity, and replica preemption.

**Primary outcome:** the **minimum fleet cost required to satisfy a fixed SLO**.

## Research questions

| | Question |
|---|---|
| **RQ1** | At what level of prefix sharing does cache-aware routing become beneficial versus strong queue-aware routing? |
| **RQ2** | When does capability-aware routing outperform strong queue-aware routing on heterogeneous GPU fleets? |
| **RQ3** | How accurate is the completion-time predictor, and how does prediction error affect policy performance? |
| **RQ4** | How does cache locality interact with preemption and gray failures? |

**H4 (major hypothesis).** Cache-sticky routing may suffer *greater* transient
SLO degradation after replica preemption, because losing a replica destroys
concentrated cache state. This is stated as a hypothesis; refuting it is a valid
outcome.

## Policies compared

| ID | Policy |
|----|--------|
| B1 | Round Robin — floor/sanity baseline only |
| B2-req | JSQ(d) on request-count queue |
| **B2-tok** | **JSQ(d) on token / service-time — the strong primary baseline** |
| B3 | Cache-aware routing with an overload guard |
| B4 | Cache + capability + SLO/cost-aware routing |

Every headline comparison is made **against B2-tok**. Beating round robin is not
treated as a result.

## Experiments

`E1` minimum cost at fixed SLO *(primary)* · `E2` cache-sharing threshold ·
`E3` GPU heterogeneity · `E4` preemption + gray failure *(H4)* ·
`E5` signal ablation · `E6` predictor noise · `E7` overload regime ·
`E8` simulator fidelity vs real vLLM

MVP set: **E1, E2, E3, E4, E5, E8**.

## Workloads

- **Mooncake trace** — primary; provides realistic prefix-sharing structure.
- **Azure LLM inference traces (2023/2024)** — realistic arrival and length
  distributions; used as **cache-blind controls** (they contain no prompt
  content, so no cache claim is derived from them).
- **Synthetic** — controlled prefix-sharing parameter `phi ∈ {0, 0.25, 0.5,
  0.75, 0.9}`, with the **realised** sharing rate measured, not assumed.

## Method

Simulation is the main platform; a small vLLM testbed is used for **validation
only** (E8), producing a fidelity error band. Effects smaller than that band are
reported as **inconclusive**.

Statistics: identical seeded workloads across policies, >= 10 seeds per cell,
bootstrap 95% CIs, paired comparisons, effect sizes. Frozen practical-
significance thresholds: **cost >= 10%**, **p95 TTFT >= 15%**, **SLO attainment
>= 2 percentage points**.

## Status

**Week 1 of 12.** Milestone 0 (specification) is frozen; Milestone 1 (simulator-
base spike) is in progress. **No experimental results exist yet.**

See `CURRENT_STATUS.md` for the live state.

## Repository map

| Path | Contents |
|------|----------|
| `PROJECT_SPEC.md` | frozen research specification |
| `CURRENT_STATUS.md` | what is happening right now |
| `MILESTONES.md` | milestone tracker + acceptance criteria |
| `DECISIONS.md` | decisions and rationale (append-only) |
| `NOTEBOOK.md` | research diary, including failed attempts |
| `REPRODUCE.md` | reproduction instructions from a clean clone |
| `CLAUDE.md` | permanent operating rules for the AI assistant |
| `src/` | shared library code |
| `simulator/` | simulation engine (base TBD in M1) |
| `workloads/` | trace loaders, unified format, synthetic generator |
| `experiments/` | experiment drivers E1–E8 |
| `analysis/` | statistics and figure generation |
| `configs/` | experiment and fleet configurations |
| `tests/` | tests |
| `results/` | raw per-request outputs |
| `docs/` | design notes, spike reports |

## Honesty policy

Every reported quantity is labelled `measured`, `hypothesis`, `estimate` or
`assumption`. Measurements are never fabricated. Negative and null results are
reported as findings.
