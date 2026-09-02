# REPRODUCE.md — Reproducing This Project From a Clean Clone

> **STATUS: M1 SPIKE REPRODUCIBLE (2026-09-02).**
> There are still no experiments and no results. What *is* reproducible is the
> Milestone-1 simulator-base spike (§3a): the two candidate simulators, at the
> exact commits scored, with the workarounds that were needed. This file is
> grown milestone by milestone so that reproducibility is never retrofitted at
> the end.

---

## Current reproducibility status

| Component | Milestone | Reproducible? |
|-----------|-----------|---------------|
| Repository + documentation | M1 (scaffold) | yes — `git clone` |
| Simulator base decision | M1 | **yes** — see §3a and `docs/spike/` |
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

Recorded facts about the development machine (`measured`, 2026-08-31 /
2026-09-02):

- Linux 6.18.33.2-microsoft-standard-WSL2 (WSL2), bash, 8 cores, 7 GB RAM.
- Project directory on `/mnt/d`, a Windows **DrvFs** mount. This is slow for
  workloads that touch many small files, and it dominated one M1 measurement
  badly enough to be worth stating up front (§3a).
- System Python: 3.14.4 — too new for both candidate simulators, so every
  environment below pins its own interpreter via `uv`.
- Docker daemon available (Docker Desktop, version 29.1.3).
- No GPU access configured yet (needed for M3 calibration and M11 fidelity).

Policy, unchanged: one pinned virtual environment per component, with exact
versions committed (a lockfile, not a loose `requirements.txt` range), because
the statistical claims depend on deterministic seeded runs.

## 3a. Reproducing the M1 simulator-base spike

Nothing third-party is committed to this repository. Both candidates were
cloned into `.spike/`, which is **git-ignored**. To re-audit the M1 decision,
recreate that working area:

```bash
mkdir -p .spike && cd .spike
```

### Vidur (the chosen base)

```bash
git clone https://github.com/microsoft/vidur.git vidur
cd vidur && git checkout abae7f63aa857300f5cdc6f5e0d27860cd24721b   # branch main, as scored
uv venv --python 3.10 .venv && . .venv/bin/activate
uv pip install -r requirements.txt && uv pip install -e .

export WANDB_MODE=disabled
python -m vidur.main \
  --cluster_config_num_replicas 4 \
  --global_scheduler_config_type lor \
  --synthetic_request_generator_config_num_requests 128 \
  --no-metrics_config_write_json_trace \
  --no-metrics_config_enable_chrome_trace \
  --no-metrics_config_store_plots
```

The `canary` branch — the one D-006 selects — is a worktree of the same clone:

```bash
git fetch origin 'refs/heads/*:refs/remotes/origin/*'
git worktree add ../vidur-canary 25e0082dbbfb206fb0477c3ebbededa7ead78949
cd ../vidur-canary && uv sync --frozen        # uses the committed uv.lock
```

**Expect the first run to take hours.** `measured` on this machine: **4 h 37 m**
wall for the first `main` run, of which ~4 s was simulation and the rest was a
one-time random-forest execution-time-predictor fit cached under `cache/`.
Subsequent runs: **~1 min**. Two separate processes produced a bit-identical
simulated end time (`240.3957407989195 s`), which is the determinism property
the statistical design depends on.

### LLMServingSim (the rejected candidate)

```bash
git clone --recurse-submodules https://github.com/casys-kaist/LLMServingSim.git llmservingsim
cd llmservingsim && git checkout a4053bc1161872420e1e0607cb3409ef659b828e
git submodule update --init --recursive     # run TWICE; see NOTEBOOK.md
```

Then, per the project's own instructions, in the container:

```bash
docker run -d --name servingsim_docker -v "$PWD":/app/LLMServingSim \
  -w /app/LLMServingSim astrasim/tutorial-micro2024 sleep infinity
docker exec servingsim_docker pip3 install \
  pyyaml pyinstrument rich pandas==1.5.3 numpy==1.23.5 matplotlib==3.5.3
docker exec servingsim_docker ./scripts/compile.sh
```

**Two workarounds were required on this machine**, both recorded in
`NOTEBOOK.md`:

1. `./scripts/compile.sh` stalls indefinitely on a `pip install` of Chakra that
   `git clone --filter=blob:none`s `HolisticTraceAnalysis` *inside* the
   container. Work around it by cloning that repository on the host into the
   mounted tree and installing it from the local path first:

   ```bash
   git clone https://github.com/facebookresearch/HolisticTraceAnalysis.git _hta
   (cd _hta && git checkout d731cc2e2249976c97129d409a83bd53d93051f6)
   docker exec servingsim_docker pip3 install ./_hta
   docker exec servingsim_docker pip3 install ./astra-sim/extern/graph_frontend/chakra
   ```

2. The ASTRA-Sim cmake build then succeeds, but took **11 h 29 m** here against
   the project's documented "2–5 minutes on a typical machine". This is an
   **environment** problem (8 cores, C++ sources on a DrvFs mount), not a defect
   in LLMServingSim — see `NOTEBOOK.md` for the reasoning behind that
   attribution.

Verify and run:

```bash
docker exec servingsim_docker ls -l \
  astra-sim/build/astra_analytical/build/AnalyticalAstra/bin/AnalyticalAstra
docker exec servingsim_docker python -m serving \
  --cluster-config configs/cluster/single_node_single_instance.json \
  --dtype bfloat16 --block-size 16 \
  --dataset workloads/example_trace.jsonl \
  --output outputs/spike_single_run.csv --num-reqs 10
```

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
