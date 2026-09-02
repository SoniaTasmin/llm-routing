# docs/spike/llmservingsim-notes.md — LLMServingSim, as actually obtained and run

**Spike date:** 2026-09-01 · **Milestone:** M1 · **Status:** evidence file

Labels as in `vidur-notes.md`: `measured` / `estimate` / `assumption` /
`hypothesis`; unlabelled statements are code facts verified by reading the
source at the stated path and commit.

---

## 1. What was obtained

| Item | Value |
|------|-------|
| Repository | `https://github.com/casys-kaist/LLMServingSim` |
| Commit | `a4053bc1161872420e1e0607cb3409ef659b828e` (2026-08-28) |
| Submodule `astra-sim` | `d3469945c50410cac2e727c9ab627670c965db2a` (+ 8 nested submodules) |
| Papers | IISWC 2024; CAL 2025; **ISPASS 2026 (LLMServingSim 2.0)** |
| Python files (excl. submodules) | 68 |
| Local checkout | `.spike/llmservingsim` — **git-ignored, not committed** |

This is **LLMServingSim 2.0**, substantially rewritten since the 2024 paper. The
Python frontend under `serving/` is a port of vLLM v0.19.0's scheduler and
block-pool logic. It is a far closer match to our problem than the 2024
description would suggest, and — as with Vidur's `canary` — judging it from the
paper rather than the tree would have produced the wrong answer.

---

## 2. Installation — this is the expensive half

Unlike Vidur, LLMServingSim is **not** a pip install. It is a Python frontend
bolted to a C++ backend that must be compiled:

```bash
git clone --recurse-submodules ...     # 10 submodule paths, nested 3 deep
./scripts/docker-sim.sh                # astrasim/tutorial-micro2024 image
./scripts/compile.sh                   # Chakra (pip, from git) + ASTRA-Sim (cmake)
```

`measured` on this machine (WSL2, 8 cores, 7 GB RAM, repo on a DrvFs `/mnt/d`
mount):

| Step | Cost |
|---|---|
| `git submodule update --init --recursive` | needed **two** invocations; the first left 5 of the 10 submodule paths unchecked-out |
| `docker pull astrasim/tutorial-micro2024` | ~18 min; **2.26 GB** on disk |
| `pip3 install` of the six pinned frontend deps | ~1 min |
| `./scripts/compile.sh` — Chakra step | **stalled indefinitely**; had to be worked around (`NOTEBOOK.md`, `REPRODUCE.md` §3a) |
| `./scripts/compile.sh` — ASTRA-Sim cmake build | **11 h 29 m** against a documented "2–5 minutes on a typical machine" |

The 11 h 29 m figure is an **environment** result, not an indictment of the
project: 8 cores against a build configured for 16 threads, with the C++ sources
on a DrvFs mount. It is recorded because it is a real cost on the machine this
project will actually be done on, and a reviewer on Windows/WSL would hit it
too.

The image ships Python 3.10.12, cmake, g++ and protobuf 28.3, but **no** Python
packages and **no** pre-built backend, so the compile step is mandatory, not
optional (`docs/docs/getting-started/installation/simulator.mdx`).

Consequence for `REPRODUCE.md`: reproducing this project from a clean clone
would require a working Docker daemon, ~3 GB of image, network access to GitHub
from inside a container, and a C++ build — on top of the Python environment.
That is a real, permanent reproducibility tax on an Erasmus Mundus artefact
that a reviewer may try to run.

---

## 3. Architecture, as read

Two processes, coupled by a line-oriented pipe
(`docs/docs/simulator/architecture.mdx`, confirmed against
`serving/__main__.py` and `serving/core/controller.py`):

```
Python frontend (serving/)                     C++ backend
  Router ─▶ Scheduler ─▶ trace_generator ─▶ graph_generator ─┐
                                                              ├─▶ AnalyticalAstra
  controller ◀── "sys[i] iteration n finished, C cycles" ◀────┘
```

Per **batch**, the frontend generates a per-layer compute trace, converts it to
a Chakra protobuf `.et` graph, writes it to disk, hands the path to ASTRA-Sim
over stdin, and blocks on stdout until the backend reports cycles. The simulated
clock `current` (ns) advances by whatever the backend returns.

Two consequences that matter more than any feature checkbox:

1. **The simulator is not a self-contained Python object.** There is no
   `Simulator.run()` we can call in-process, no way to run many configurations
   inside one interpreter, and the event loop is driven by a subprocess
   handshake. `controller.read_wait()` carries a comment noting **337 786**
   parse calls for a *10-request, 8-NPU* run. An E1 fleet search is thousands of
   runs; each is a container, a subprocess, and disk I/O per batch.
2. **Fidelity is bought with coupling.** The upside is real — see §5, R8 and
   the validation section — but it is bought at exactly the cost that hurts a
   large parameter sweep.

### Measured throughput

Three runs on an otherwise-idle machine (an earlier pair of timings was
discarded as CPU-contaminated — see `NOTEBOOK.md`):

| Run | Instances | Requests | Wall clock | Per request |
|---|---|---|---|---|
| single instance, bundled trace | 1 | 10 | **9.0 s** | 0.90 s |
| shared CPU prefix pool, bundled trace | 2 | 10 | **14.4 s** | 1.44 s |
| shared CPU prefix pool, 300-request probe | 2 | 300 | **4 m 51 s** | **0.97 s** |

The 300-request probe is the informative one: a hand-written workload
(`spike_throughput_300.jsonl`, ~10 req/s Poisson arrivals, 1024-token prompts
sharing a 512-token prefix, 128-token outputs). Per-request cost is **flat at
~1 s** from 10 to 300 requests — so this is a genuine marginal rate, not
start-up overhead.

That run also confirms R3 at runtime rather than from documentation:
**NPU prefix hit 49.67 %**, and a non-zero **CPU (cross-instance) hit of
0.17 %** — the shared node-level tier is live and serving recalls. The
cross-instance share is small here only because the shared prefix stays
resident on the NPU; that is the correct behaviour, not a defect.

**What ~1 s/request means for E1.** `estimate`, extrapolating the measured flat
marginal rate: a 20 000-request run is ~5.5 h. `PROJECT_SPEC.md` §11 requires
≥10 seeds per cell, and E1 sweeps policies × φ × fleet composition — a few
hundred runs at minimum. That is thousands of serial hours, and there is no
in-process API to amortise anything across runs. Parallelism helps
proportionally and nothing else does.

For contrast, and comparing like with like — both with prefix caching enabled —
Vidur `canary` is `measured` at **~0.18 s/request** (512 Mooncake requests,
4 replicas, `vllm_v1` + prefix cache, 91 s of simulation). That is about
**5.5× cheaper**, plus the option of running many cells inside one process.

An earlier draft of this file put the gap at ~60×, by comparing against Vidur
`main` running the cheap Sarathi scheduler with no prefix cache at all. That was
not a fair comparison and has been withdrawn. 5.5× is real and it compounds with
the process model, but it is a contributing reason for the recommendation, not
the decisive one.

---

## 4. Where routing lives

`serving/core/router.py`, 327 lines, one class. Policy is selected by string in
`__init__` and bound to `self._select_instance`:

```python
if   self.routing_policy == "RR":     self._select_instance = self._rr_select
elif self.routing_policy == "RAND":   self._select_instance = self._rand_select
elif self.routing_policy == "LOAD":   self._select_instance = self._least_load_select
elif self.routing_policy == "CUSTOM": self._select_instance = self._custom_select
```

and `_custom_select` is an explicit extension point:

```python
def _custom_select(self, schedulers, role):
    raise NotImplementedError("Implement custom routing policy.")
```

exposed at the CLI as
`--request-routing-policy {LOAD,RR,RAND,CUSTOM}` (`serving/__main__.py:280`).

`_least_load_select` is a genuinely non-trivial baseline — `waiting*4 + running`,
normalised by `max_num_seqs` — i.e. a capacity-normalised least-load, close in
spirit to our B2-req.

---

## 5. Requirement-by-requirement evidence

### R1 — multiple replicas · PASS

Instances are declared in the cluster JSON and one `Scheduler` is constructed
per instance (`serving/__main__.py`, `for instance_id, instance in enumerate(instances)`).
Shipped multi-instance configs: `configs/cluster/single_node_multi_instance.json`,
`rtx4090_multi_instance.json`, `dual_node_multi_instance.json`,
`single_node_4_instance_2TP.json`. Shipped output
`outputs/example_multi_run.csv` carries an `instance id` column.

### R2 — pluggable routing · PARTIAL

The hook exists (`CUSTOM`, above) and is wired to the CLI, which is more than
"you could subclass it". Two concrete blockers for our policy set:

1. **The router cannot see the request.** The call site is
   `instance_id = self._select_instance(self.prefill_schedulers, "prefill")`
   (`router.py`, `route_arrived_requests`). The request dict — which holds
   `input_hash_ids`, `input_toks`, `arrival_time_ns` — is in scope at the call
   site but is **not passed**. B3 and B4 are impossible without widening this
   signature. B2-tok needs it too (it needs the request's token count).
2. **No registry, no config object.** Policies are an `if/elif` chain over
   strings, with no per-policy parameters (our B3 needs at least a guard
   threshold; B2-tok needs `d`). Adding five policies means either five
   `elif` branches with parameters smuggled in as globals, or building the
   registry first.

Both are small edits. They are counted honestly in `requirements-matrix.md`
rather than waved through, because "there is a CUSTOM hook" reads like a PASS
and is not one.

### R3 — cross-replica prefix-cache state · **PASS** (the strongest result for either candidate)

A full vLLM-v0.19.0-derived tiered prefix cache:

- `serving/core/block_pool.py` (522 lines) — block pool with ref-counting, LRU
  free list, `cache_full_blocks`, `touch`.
- `serving/core/kv_cache_manager.py` (563 lines) — `TieredKVCacheManager` with
  chained block hashes (`request_block_hashes`), NPU tier plus optional
  CPU/CXL storage tier, a **single shared key space** across tiers.
- `serving/core/memory_model.py:125` — "The second-tier pool: shared across
  instances, or private."

The documentation states the sharing semantics precisely
(`docs/docs/simulator/scheduling/prefix-caching.md`), and the code agrees:

> "The NPU pool is **per-instance**: a request that lands on instance B can't
> reuse a prefix cached on instance A.
> The storage pool is **shared across instances on the same node** when
> `--enable-prefix-sharing` is on."

So: private GPU caches, plus a genuinely shared node-level second tier whose
recall is charged as `kv_load` latency on the critical path, while write-down is
free (matching vLLM's `OffloadingConnector`). Flags: `--enable-prefix-caching`
(default on), `--enable-prefix-sharing`, `--prefix-storage {None,CPU,CXL}`.

**One constraint found in the code that the docs do not foreground**, and that
directly collides with R4: the shared pool refuses heterogeneous models.
`serving/__main__.py`, `_pool_kv_bytes_per_token` and `_pool_block_size` raise

```
RuntimeError: Shared prefix pool requires instances to share model, dtype,
              and kv_cache_dtype; got {...}
RuntimeError: Shared prefix pool requires instances to share block_size; got {...}
```

Heterogeneous **hardware** with one model is unaffected (KV bytes/token depends
on model+dtype, not on the GPU). Heterogeneous **models** and cross-replica
cache sharing are mutually exclusive. For our E3 that is acceptable — our
heterogeneity is GPU-type heterogeneity — but it must be stated, not discovered
in week 7.

### R4 — heterogeneous replica types · **PASS**

Per-instance, not per-cluster:

```json
{"model_name": "...", "hardware": "RTXPRO6000", "npu_mem": {...},
 "num_npus": 2, "tp_size": 2, "pd_type": "prefill",
 "max_num_seqs": 32, "enable_prefix_caching": true}
```

(`configs/cluster/single_node_heterogeneous.json`, and every instance key is
read per-instance in `serving/core/config_builder.py:451` — required keys
`["model_name", "hardware", "npu_mem", "pd_type"]`.)

The shipped `single_node_heterogeneous.json` varies `pd_type` /
`max_num_seqs` rather than GPU type, and **no bundled example exercises a
mixed-SKU fleet** — so rather than assume, I wrote one and ran it.

`configs/cluster/spike_mixed_gpu.json`: two instances, same model
(`meta-llama/Llama-3.1-8B`), different hardware — one `RTX4090` (24 GB,
1008 GB/s) and one `RTXPRO6000` (96 GB, 1597 GB/s) — round-robin routed,
10 requests.

`measured`, exit 0, 5 requests on each instance:

| instance | hardware | mean TTFT | mean TPOT |
|---|---|---|---|
| 0 | RTX4090 | **22.35 ms** | **17.11 ms** |
| 1 | RTXPRO6000 | **15.36 ms** | **11.23 ms** |

The per-instance `hardware` field genuinely selects a different profile bundle
and produces different timings — a 1.45× TTFT gap in the direction physics
predicts. **R4 is a verified PASS, not an inferred one.** Two GPU SKUs, one
model, is enough for E3's first heterogeneous mix; not enough for the third
(already cut-if-behind in `PROJECT_SPEC.md`).

**Caveat that interacts with R3:** this fleet cannot *also* use a shared
cross-instance prefix pool if the instances differ in model or dtype — see R3
above. Differing only in GPU SKU, as here, is compatible with both.

### R5 — mid-run replica removal / failure · FAIL

No failure injection, no instance removal, no drain. The word "preemption" in
this codebase means the same thing it means in Vidur — vLLM KV-pressure
preemption of a *request* (`Scheduler._preempt_request`, `scheduler.py:252`;
`num_preemptions` counter; `serving/__main__.py:1207` reports it). Not spot
preemption.

Harder to add here than in a pure-Python DES, because the instance set is
mirrored into ASTRA-Sim's NPU topology at startup: `config_builder` writes
`network.yml` / `system.json` before the backend is spawned, and the frontend's
loop is keyed on NPU ids reported by the backend. Removing an instance mid-run
means either keeping the NPU alive in the backend and refusing to schedule it
(feasible; changes utilisation accounting) or restarting the backend (changes
the clock). This is the single biggest divergence in extension cost between the
two candidates — see `requirements-matrix.md` §3.

### R6 — SLO / deadline modelling · FAIL

`grep -rin "slo\|deadline" serving/ bench/` returns only prose comments and
`allocate_slots` false positives. No per-request deadline, no SLO config, no
attainment metric, no SLO-aware queue. Everything E1 needs would be built from
zero — though the raw TTFT/TPOT columns needed to *compute* attainment offline
are all present (R8).

### R7 — cost accounting · FAIL

No monetary cost anywhere: no `$/hr`, no price table, no cost column.
`serving/core/power_model.py` (223 lines) models **energy**, which is a
different quantity and cannot substitute for a fleet price without an
electricity-price assumption we would be inventing. `PROJECT_SPEC.md` §3 makes
cost the *primary* outcome, so this is a fail against the project's headline
metric, not a peripheral gap. (It is, however, the cheapest fail to fix on
either candidate — a price table plus `Σ replica-hours × price`.)

### R8 — per-request metrics · **PASS**, and the richest of any candidate

`Scheduler.save_output` writes one row per request. Verified against the shipped
`outputs/example_multi_run.csv`:

```
instance id, request id, model, input, output, arrival, end_time,
latency, queuing_delay, TTFT, TPOT, ITL
```

`instance id` is present — the column Vidur `main` lacks. `ITL` is the **full
per-token inter-token-latency list**, not a summary, which is more raw detail
than `PROJECT_SPEC.md` §11 requires ("raw per-request rows are the artefact").

**Gap:** no per-request cache-hit column in the CSV, though the components are
recorded on the `Request` object (`num_npu_hit`, `num_lower_hit` per
`docs/.../prefix-caching.md`). Exporting them is a small change and is needed
for RQ1 diagnostics.

**Gap:** no simulation-level seed. The only seeds are hardcoded defaults
(`router.py:13 seed=42`, `gate_function.py:47`, `trace_generator.py:1639`) with
no CLI flag. Our design needs ≥10 seeds per cell (`PROJECT_SPEC.md` §11).
Workload-level seeding exists in `workloads/generators/sharegpt.py --seed`, so
seeds can be varied *through the workload*, which is arguably the right place —
but simulator-side stochasticity (RAND routing, MoE gating) would remain
un-controlled.

---

## 6. The genuine strength: validation against real vLLM

This is where LLMServingSim is clearly ahead, and it bears directly on **E8**.

`docs/docs/validation.md` reports a 300-request ShareGPT replay run through both
vLLM v0.19.0 and the simulator on RTXPRO6000 and RTX 4090, with a `bench`
harness (`bench/core/validate.py`, `python -m bench validate`) that does
strict-replay pinning of token ids and sampling params so both sides process
identical prompts in identical order. Published deltas on the matched RTX 4090
configuration: **TTFT +0.6 %, TPOT +0.2 %, mean latency +0.5 %**. Four recorded
`(hardware, model)` example bundles ship with the repo, each containing the real
vLLM `requests.jsonl` / `timeseries.csv` **and** the simulator output.

`measured` — but measured *by the project authors*, not by us; we have not
reproduced it, and we have no GPU to do so during M1. It is nonetheless a
methodology we can copy for E8 regardless of which base we pick, and the
documentation is unusually candid about the failure mode (the `mem_util`
calibration caution: default 0.9 gives −20.7 % TTFT error, matched 0.833919
gives +0.6 %).
