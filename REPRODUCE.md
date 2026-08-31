# REPRODUCE.md — Reproducing This Project From a Clean Clone

> **STATUS: SCAFFOLD ONLY (2026-08-31).**
> There is nothing to reproduce yet — no simulator, no workloads, no
> experiments, no results. This file is created now and grown milestone by
> milestone so that reproducibility is never retrofitted at the end.

---

## Current reproducibility status

| Component | Milestone | Reproducible? |
|-----------|-----------|---------------|
| Repository + documentation | M1 (scaffold) | yes — `git clone` |
| Simulator base decision | M1 | not yet — spike not run |
| Workload loaders / synthetic generator | M2 | not yet |
| vLLM calibration | M3 | not yet |
| Simulator | M4 | not yet |
| Policies B1/B2 | M5 | not yet |
| Policy B3 | M6 | not yet |
| Heterogeneity | M7 | not yet |
| Policy B4 + ablations | M8 | not yet |
| E1 minimum-cost experiment | M9 | not yet |
| E4 failure experiments | M10 | not yet |
| E8 fidelity validation | M11 | not yet |
| Figures / report | M12 | not yet |

---

## 1. Clone

```bash
git clone https://github.com/SoniaTasmin/llm-routing.git
cd llm-routing
```

## 2. Read the repository in this order

1. `README.md` — what the project is.
2. `PROJECT_SPEC.md` — the frozen research specification (RQs, policies,
   experiments, statistical rules).
3. `CURRENT_STATUS.md` — where the project actually is right now.
4. `MILESTONES.md` — milestone tracker and acceptance criteria.
5. `DECISIONS.md` — why things are the way they are.
6. `NOTEBOOK.md` — what was tried, including what failed.

## 3. Environment

*To be filled in at M1/M2 once the simulator base is chosen and dependencies are
pinned.*

Recorded facts about the development machine (`measured`, 2026-08-31):

- Linux 6.18.33.2-microsoft-standard-WSL2 (WSL2), bash.
- System Python: 3.14.4.
- No GPU access configured yet (needed for M3 calibration and M11 fidelity).

Planned: one pinned virtual environment per component, with exact versions
committed (a lockfile, not a loose `requirements.txt` range), because the
statistical claims depend on deterministic seeded runs.

## 4. Reproducing experiments

*Not available yet.* Will be written as each experiment lands, and will include
for every experiment: the exact command, the seed list, the expected runtime,
the raw per-request output path under `results/`, and the analysis command that
turns raw rows into the reported figure.

## 5. Reproducibility principles (fixed now, before any code exists)

- **Seeded, identical workloads across policies.** Policy comparisons are paired
  on seed.
- **Raw per-request rows are the artefact.** Aggregates are always recomputable
  from `results/`; never store only summaries.
- **>= 10 seeds per cell** for primary experiments.
- **Bootstrap 95% CIs**, paired comparisons, effect sizes reported.
- **Every number is labelled** `measured` / `hypothesis` / `estimate` /
  `assumption`.
- **Nothing is fabricated.** If a run did not happen, it is absent, not
  estimated into a table.
