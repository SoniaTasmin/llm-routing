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
| Workload loaders / synthetic generator | M2 | **yes** — see §3b |
| vLLM calibration | M3 | **partially** — CPU-side tooling and audit reproducible today (§3c); GPU phases prepared but unrun |
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

## 3b. Reproducing the M2 workloads

Source traces are **not** vendored — they are large and they are other people's
data. Fetch them into the git-ignored `.spike/` area, then build:

```bash
# Mooncake (primary trace, ~3 MB of the repo's FAST25 release)
mkdir -p .spike/mooncake_upstream && cd .spike/mooncake_upstream
git clone --filter=blob:none --no-checkout https://github.com/kvcache-ai/Mooncake.git repo
cd repo
git sparse-checkout set --no-cone "FAST25-release/traces/conversation_trace.jsonl"
git checkout HEAD          # verified at eeaca79aa298fdaf89580f0db1f12340ea206b32
cd ../../..

# Azure 2023 LLM inference traces (cache-blind control, ~1 MB)
mkdir -p .spike/azure && cd .spike/azure
for f in AzureLLMInferenceTrace_conv.csv AzureLLMInferenceTrace_code.csv; do
  curl -sSL -o "$f" \
    "https://raw.githubusercontent.com/Azure/AzurePublicDataset/master/data/$f"
done
cd ../..

# Vidur profiling data + processed traces, at the SHA pinned by D-006 (~584 MB)
bash simulator/vendor/fetch_vidur_data.sh

# Build every derived workload
python -m venv .venv && . .venv/bin/activate && pip install pytest
python workloads/build_workloads.py
python -m pytest tests/ -q
```

`measured` on this machine, 2026-09-10:

| Workload | Requests | Realised prefix sharing |
|---|---|---|
| `mooncake-conversation` | 12 031 | **38.19 %** |
| `azure-2023-conv` | 19 366 | **cache-blind** — none may be reported (D-004) |
| `azure-2023-code` | 8 819 | **cache-blind** |
| `synthetic-phi0` … `phi0.9` | 4 000 each | 0.0000 / 0.2360 / 0.4908 / 0.7413 / 0.8805 |

The derived `.jsonl` files are git-ignored and regenerable. Their
`.manifest.json` sidecars **are** committed: they carry the upstream SHA-256 and
the measured realised sharing, which is the evidence a result may cite.

Test suite: **31 tests**, all passing.

## 3c. Reproducing the M3 calibration

**Status: prepared, not run.** No GPU has been rented and no charges incurred.
Everything below except the two GPU phases runs on CPU today.

### What you can reproduce right now, with no GPU

```bash
# 1. See exactly what the GPU phases would execute — nothing runs, nothing bills
bash experiments/m3_calibration/run_profiling.sh plan

# 2. Audit the profile the simulator currently depends on
PYTHONPATH=src python -m workload.profile_audit_cli \
  .spike/vidur-canary/data/profiling/compute/a100/meta-llama/Meta-Llama-3-8B/attention.csv \
  --tp 1 --block-size 16 --require-context 65536

# 3. Run the auditor's own tests
python -m pytest tests/test_profile_audit.py -q
```

Step 2 reproduces the coverage audit that D-008 rests on (`measured`, CPU only):

```
  TPs present         : [1, 8]          <- a100 has NO TP=2 or TP=4 data
  block_size present  : [16]            <- gate G4: 512 would empty the frame
  prefill: 21,524 rows, 21,204 distinct pairs, max chunk+kv = 262,144
  decode : 43,744 rows, 43,184 distinct pairs (560 repeats), 176 batch sizes
           max kv = 65,536, reached at 71 batch sizes
  covers 65,536-token request at chunk 4096: True
  covers 131,072-token request at chunk 4096: False — decode stops at 65,536
```

That last line is the whole reason the D′ truncation exists (D-008), and the
reason M3's headline deliverable is extending decode coverage.

### The GPU phases — require approved budget

Not yet run. See `docs/m3-calibration-plan.md` for hardware, software, costed
options and the decision requested.

```bash
# On a machine with 1 x A100 80GB (or H100 80GB):
#   Python 3.10; sarathi-serve @ branch `vidur`; FlashInfer; Vidur from
#   simulator/vendor/vidur installed with `pip install -e .`
#   NO HuggingFace token and NO model download are needed — the profiler uses
#   dummy weights (initialize_dummy_weights / torch.randn_like).

bash experiments/m3_calibration/run_profiling.sh pilot   # ~1 h billed, ~$2
# review the printed rows/s and the audit before continuing
bash experiments/m3_calibration/run_profiling.sh full    # 3-8 h billed
```

Produced profiles land under `calibration/<device>/<model>/`. **They are never
copied into `simulator/vendor/`** — that tree is immutable
(`simulator/vendor/PROVENANCE.md`) and its checksum is verified.

### Recording what the run used

The exact CUDA, PyTorch, FlashInfer and `sarathi-serve` versions are **not
pinned here yet**, because they follow `sarathi-serve`'s own README and we have
not stood the environment up. Capturing them is part of the pilot:

```bash
python -c "import torch;print('torch',torch.__version__,'cuda',torch.version.cuda)"
pip freeze > calibration/environment-$(date +%F).txt
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

Until that file exists, M3 is **not** reproducible in the sense §5 requires, and
the acceptance criterion stays open.

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
