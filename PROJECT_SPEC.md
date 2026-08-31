# PROJECT_SPEC.md — Frozen Milestone-0 Research Specification

> **STATUS: FROZEN.** Approved at Milestone 0 on 2026-08-31.
> This document may not be silently edited. Any change requires an explicit
> user decision recorded in `DECISIONS.md` with a new dated entry, and the
> change must be marked here as an amendment below the frozen text.

---

## 1. Title

**When Does Routing Sophistication Pay?
A Controlled Evaluation of Load-, Cache-, and Cost-Aware Scheduling for LLM
Inference on Heterogeneous, Preemptible Infrastructure**

## 2. Nature of the project

A research-oriented systems project intended to demonstrate Master's-level
ability for an Erasmus Mundus application.

It is an **empirical characterization and reproducibility study**, not an
algorithm-invention paper.

## 3. Research framing

We do **not** claim to invent a new LLM routing algorithm.

Central question:

> **When does routing sophistication actually provide practically significant
> benefits over strong queue-aware scheduling?**

We want to determine when cache-, capability-, SLO-, and cost-aware routing
actually provides meaningful benefit.

### Primary outcome metric

**Minimum infrastructure/fleet cost required to satisfy a fixed SLO.**

Latency, SLO attainment, cache hit rate and throughput are secondary/diagnostic
metrics that explain *why* the cost outcome moves.

## 4. Research questions

### RQ1 — Cache locality
At what level of prefix sharing does cache-aware routing become beneficial
compared with strong queue-aware routing?

### RQ2 — GPU heterogeneity
When does capability-aware routing outperform strong queue-aware routing on
heterogeneous GPU fleets?

### RQ3 — Prediction
How accurate is the completion-time predictor, and how does prediction error
affect policy performance?

### RQ4 — Resilience
How does cache-locality interact with preemption/spot failure and gray failures?

### H4 — major hypothesis
**Cache-sticky routing may suffer greater transient SLO degradation after replica
preemption because losing a replica destroys concentrated cache state.**

H4 is stated as a *hypothesis*, not a result. It may be refuted; a refutation is
a publishable outcome for this project and must be reported as such.

## 5. Policies under test

| ID | Policy | Description | Role |
|----|--------|-------------|------|
| **B1** | Round Robin | stateless rotation over replicas | sanity/floor baseline |
| **B2-req** | JSQ(d) request-count | join-shortest-queue over d sampled replicas, queue measured in requests | queue-aware baseline |
| **B2-tok** | JSQ(d) token/service-time-aware | queue measured in predicted service time / outstanding tokens | **STRONG PRIMARY BASELINE** |
| **B3** | Cache-aware + overload guard | prefix-affinity routing, with a guard that sheds affinity under load | treatment |
| **B4** | Cache + capability + SLO/cost-aware | full combined policy | treatment |

**Baseline discipline (frozen):**
- Round Robin (B1) is **not** the meaningful competitor.
- Beating B1 alone is **not** an interesting result and will not be reported as
  a headline finding.
- The headline comparison for every experiment is **treatment vs B2-tok**.

## 6. Core experiments

| ID | Experiment | Status |
|----|-----------|--------|
| **E1** | Minimum cost at fixed SLO | **PRIMARY EXPERIMENT** — MVP |
| **E2** | Cache-sharing threshold (sweep phi) | MVP |
| **E3** | GPU heterogeneity | MVP |
| **E4** | Preemption + gray failure | **MAJOR RESULT / H4** — MVP |
| **E5** | Signal ablation | MVP |
| **E6** | Predictor quality / injected noise | cut-if-behind |
| **E7** | Overload / SLO-impossible regime | cut-if-behind |
| **E8** | Simulator fidelity against real vLLM | MVP |

**Core MVP set: E1, E2, E3, E4, E5, E8.**

**Cut order if behind schedule:**
1. E7
2. E6
3. Grafana polish
4. third heterogeneous mix
5. Azure 2024
6. k3s
7. Tier-2 validation

**No new experiments may be added without explicit user approval.**

## 7. Data

### Primary real trace — Mooncake
Purpose: prefix-sharing structure and a realistic LLM serving workload.

### Secondary real trace — Azure LLM inference traces 2023 / 2024
Purpose: realistic arrival, input-length and output-length distributions.

**Important:** the Azure traces do not contain prompt content or prefix
structure. They are therefore used as **cache-blind controls**, and no
cache-hit-rate claim may be derived from them.

### Synthetic workload — controlled prefix sharing
Parameter **phi** in `{0, 0.25, 0.5, 0.75, 0.9}`.

**Requirement:** the synthetic generator must **measure the realised
prefix-sharing rate** of the emitted workload and report it alongside the
nominal phi. Nominal phi may not be reported as if it were measured.

## 8. Architecture

```
Traces
    |
Unified workload loader        (one canonical request record format)
    |
Router                         (B1 / B2-req / B2-tok / B3 / B4)
    |
Heterogeneous simulated replica fleet
    |
Timing model
KV cache
Prefix cache
Eviction
Queue state
Cost
Failure injection
    |
Per-request raw results        (one row per request, never aggregated early)
    |
Statistical analysis
    |
Figures / report
```

### Real validation path

```
Same router code where practical
        |
small vLLM testbed
        |
real measurements
        |
simulator fidelity validation  (E8)
```

The real testbed is **VALIDATION**, not the main research platform.
Do not build unnecessary production infrastructure.

## 9. Simulator base decision (open at freeze time)

Milestone 1 is a **3-day simulator-base spike**.

Candidates to evaluate:
1. **Vidur**
2. **LLMServingSim**

### Requirements matrix (the spike must score both candidates on all eight)

| # | Requirement |
|---|-------------|
| R1 | Multiple replicas |
| R2 | Pluggable routing |
| R3 | Cross-replica prefix-cache state |
| R4 | Heterogeneous replica types |
| R5 | Mid-run replica removal / failure |
| R6 | SLO / deadline modelling |
| R7 | Cost accounting |
| R8 | Per-request metrics |

### Decision rules (frozen)
- No pre-commitment to Vidur.
- No pre-commitment to LLMServingSim.
- Do not immediately build our own simulator.
- If one existing simulator can support the project cleanly, **extend it**.
- If neither is suitable, build a **small cluster-level discrete-event
  simulator** — small, not a full LLM operator simulator.
- A full from-scratch LLM operator simulator requires a compelling demonstrated
  reason.
- The outcome must be documented in `DECISIONS.md`.

## 10. Scope cuts (frozen exclusions)

The following are explicitly **out of scope** and must not be built:

provisioning controller · Terraform · ArgoCD · KEDA · Karpenter · Kafka ·
service mesh · OpenTelemetry · RAG · vector database · agents · fine-tuning ·
multi-cloud · Raft · large models · custom web dashboard

Notes:
- The simulator searches fleet configurations directly for the minimum-cost
  fleet. No provisioning controller is needed to answer E1.
- Kubernetes, if used at all, is **only** validation infrastructure.

## 11. Statistical principles

- Identical **seeded** workloads across policies (paired design).
- Primary experiments: **>= 10 seeds per cell**.
- **Bootstrap 95% confidence intervals**.
- **Paired comparisons** where appropriate.
- Report **effect size**, not merely statistical significance.
- Enough requests per run for meaningful **tail latency** estimates.

### Frozen practical-significance thresholds

| Metric | Practically significant if |
|--------|---------------------------|
| Cost | >= **10%** difference |
| Latency | >= **15%** p95 TTFT |
| SLO attainment | >= **2 percentage points** |

### Inconclusiveness rule
Effects **smaller than the measured simulator-fidelity error band** (from E8)
are reported as **inconclusive**, regardless of p-value.

### Honesty rules
- **Never fabricate measurements.**
- Every quantity must carry one of these labels:
  `measured result` · `hypothesis` · `estimate` · `assumption`.

## 12. Frozen 12-week plan

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
| 11 | Real testbed / fidelity |
| 12 | Analysis / report / reproducibility |

**A defensible primary result must exist by Week 9.**

## 13. Working protocol

One milestone at a time. No jumping ahead. Explicit user approval closes a
milestone. The repository — not the conversation — is the permanent record.

Full protocol: see `CLAUDE.md` section 14.

---

## Amendments to the frozen spec

*(none yet)*
