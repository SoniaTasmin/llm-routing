# docs/spike/vidur-notes.md — Vidur, as actually obtained and run

**Spike date:** 2026-09-01 · **Milestone:** M1 · **Status:** evidence file

Every quantity below is labelled `measured` / `estimate` / `assumption` /
`hypothesis`. Anything not labelled is a **code fact** — a statement about what
is or is not present in the source at the stated path and commit, verified by
reading that source.

---

## 1. What was obtained

| Item | Value |
|------|-------|
| Repository | `https://github.com/microsoft/vidur` |
| Branch `main` commit | `abae7f63aa857300f5cdc6f5e0d27860cd24721b` (2026-08-24) |
| Branch `canary` commit | `25e0082dbbfb206fb0477c3ebbededa7ead78949` (2025-06-25) |
| Licence | MIT |
| Paper | Agrawal et al., *Vidur*, MLSys 2024 |
| Python files on `main` | 148 |
| Local checkout | `.spike/vidur` (`main`), `.spike/vidur-canary` (git worktree on `canary`) — **git-ignored, not committed** |

### The `canary` branch is not a detail — it is the whole story

`README.md:145` on `main` says, verbatim:

> "We have been working on several improvements for the simulator, including
> support for prefix caching, different routing policies, reducing memory
> requirements for the simulator, etc. However, there are some sharp edges that
> we are working on resolving. In the meantime, if you are looking for support
> for any of these features, please use the `canary` branch."

`main` and `canary` are **different simulators** for our purposes. Scoring only
`main` would have produced the wrong decision. Both are scored separately in
`requirements-matrix.md`.

---

## 2. Installation

### `main`

```bash
uv venv --python 3.10 .venv && . .venv/bin/activate
uv pip install -r requirements.txt && uv pip install -e .
```

Clean first time. No compilation, no container, no C++ toolchain, no GPU.
`requirements.txt` is **unpinned** (bare package names) — a reproducibility
weakness we would have to fix ourselves on `main`.

Resolved versions on this machine (`measured`, 2026-09-01): Python 3.10.21,
numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2.

### `canary`

`canary` ships `pyproject.toml` **and `uv.lock`** — a full lockfile. Install is
`uv sync --frozen`. This is a materially better reproducibility position than
`main`, and it matters for §11 of `PROJECT_SPEC.md`.

The dependency closure is heavy (ray, streamlit, jupyterlab) — see the dead-ends
entry in `NOTEBOOK.md` for how long it took on this machine.

---

## 3. It runs (`measured`)

### Run 1 — first ever run, cold cache

```bash
WANDB_MODE=disabled python -m vidur.main \
  --cluster_config_num_replicas 4 \
  --global_scheduler_config_type lor \
  --synthetic_request_generator_config_num_requests 128 \
  --no-metrics_config_write_json_trace \
  --no-metrics_config_enable_chrome_trace \
  --no-metrics_config_store_plots
```

Exit 0. Wrote `simulator_output/2026-09-01_16-10-59-225620/request_metrics.csv`
with **128 rows** (one per request) and 21 columns.

| Quantity | Value | Label |
|---|---|---|
| Total wall clock | **277 min 14 s** | `measured` |
| ...of which discrete-event simulation | **~4 s** (16:10:59 start → log 20:47:46→20:47:50) | `measured` |
| ...of which random-forest predictor fitting + prediction-table generation | the remaining ~4h36m | `measured` |
| Predictor artefacts written to `cache/` | 235 MB, 11 `.pkl` | `measured` |

**This is the single most important operational fact about Vidur.** Nearly all
of the first-run cost is a one-time fit of the per-operation execution-time
predictors, cached on disk and reused afterwards. It is not a per-run cost, but
it *is* a per-`(model, device, tensor-parallel, max-token)`-combination cost,
which matters for E3 (heterogeneity) where we deliberately introduce new device
SKUs.

### Run 2 — identical command, warm cache

| Quantity | Value | Label |
|---|---|---|
| Total wall clock | **1 min 1.7 s** | `measured` |
| ...of which simulation | ~4 s | `measured` |
| ...of which loading the 235 MB predictor cache | ~57 s | `measured` |
| Simulated end time | `240.3957407989195 s` — **bit-identical to run 1** | `measured` |

Determinism across processes at full float precision is exactly the property
`PROJECT_SPEC.md` §11 needs for paired, seeded comparisons.

### Run 3 — scale probe

`--cluster_config_num_replicas 8 --synthetic_request_generator_config_num_requests 2048 --poisson_request_interval_generator_config_qps 8`

| Quantity | Value | Label |
|---|---|---|
| Total wall clock | **2 min 26.6 s** | `measured` |
| ...of which simulation | **32 s** (21:07:55 → 21:08:27) | `measured` |
| Peak RSS | **1.24 GB** | `measured` |

### Run 4 — `canary`, the configuration we actually intend to use

512 Mooncake requests (the ≤ 4 096-token subset; see §7a for why a subset),
4 replicas, `vllm_v1` replica scheduler, **prefix caching on**, `sticky_lor`
session-affinity routing.

| Quantity | Value | Label |
|---|---|---|
| Total wall clock | **2 min 35.6 s** | `measured` |
| ...of which simulation | **91 s** (10:50:40 → 10:52:11) | `measured` |
| ...of which start-up (warm predictor cache) | ~32 s | `measured` |
| Peak RSS | **4.02 GB** | `measured` |
| Exit status | 0 | `measured` |

Output: `request_metrics.csv`, **512 rows, 25 columns** — including the three
columns `main` lacks and a routing study needs:

- **`replica`** — which replica served the request
- **`request_arrived_at`** — absolute arrival timestamp
- **`request_num_prefill_tokens_cached`** — per-request prefix-cache hit

Plus `plots/replica_prefix_cache_metrics.json`:

```json
{"0": {"cached_tokens_sum": 74240,  "total_tokens_sum": 239972, "hit_ratio": 0.3094},
 "1": {"cached_tokens_sum": 83456,  "total_tokens_sum": 268362, "hit_ratio": 0.3110},
 "2": {"cached_tokens_sum": 82944,  "total_tokens_sum": 246990, "hit_ratio": 0.3358},
 "3": {"cached_tokens_sum": 97280,  "total_tokens_sum": 278533, "hit_ratio": 0.3493}}
```

`measured`: **32.69 %** of all prefill tokens served from cache, and the
session-sticky router spread 512 requests over the four replicas as
**116 / 129 / 130 / 137**.

That single run demonstrates R1, R2, R3 and R8 working together on our primary
trace, with the per-request diagnostics RQ1 needs — which is what the spike had
to establish.

### Throughput — indicative only, and two corrections to my own readings

| Configuration | Requests | Replicas | Simulation time | Per request |
|---|---|---|---|---|
| `main`, sarathi, synthetic, no cache | 2 048 | 8 | 32 s | **0.016 s** |
| `canary`, `vllm_v1` + prefix caching, Mooncake ≤4 096 | 512 | 4 | 91 s | **0.178 s** |
| *(LLMServingSim, 2 instances, shared CPU pool, synthetic 1 024-tok)* | *300* | *2* | *4 m 51 s* | *0.97 s* |

**Correction 1.** I first quoted the 0.016 s figure against LLMServingSim. That
was unfair: `main` with the cheap Sarathi scheduler and no prefix cache, against
LLMServingSim running vLLM-derived block-pool caching. Withdrawn.

**Correction 2 (2026-09-10).** I then described the 0.178 s vs 0.97 s comparison
as "like-for-like, both with prefix caching". **That was also wrong**, and it is
the more insidious error because it sounds controlled. Turning prefix caching on
in both simulators does **not** equalise the work they do. The two runs differ in
almost every other respect:

| | Vidur `canary` | LLMServingSim |
|---|---|---|
| Trace | 512 Mooncake requests, ≤4 096 tokens, real prefix structure | 300 synthetic requests, 1 024-token prompts, one shared 512-token prefix |
| Replicas / instances | 4 | 2 |
| Replica scheduler | `vllm_v1` | vLLM v0.19.0 port |
| Cache configuration | per-replica GPU cache, no disk tier | per-instance NPU + shared node CPU pool |
| Measured hit rate | 32.69 % | 49.67 % NPU + 0.17 % CPU |

**The only defensible claim is `indicative`:** across the configurations we
happened to run, Vidur's per-request simulation cost was **single-digit times
lower** — nominally ~5.5×. It is not a benchmark and must not be quoted as one.

A properly controlled comparison — same trace, same replica count, same cache
settings on both simulators — was **not** performed. It is deliberately not being
performed now: it would take a day of work to strengthen a *contributing*
argument, and the decision rests on R2, R5 and R7, none of which is a throughput
question. Recorded so no future reader mistakes the absence for an oversight.

Each *process* additionally pays a fixed predictor-load tax of **~32–115 s**
depending on how many operations the configuration touches. For an E1 sweep of
order 10³ runs that fixed tax is comparable to the simulation itself, so
batching many cells per process is not an optimisation but a requirement.
Falsifier **F2**.

---

## 4. Architecture, as read

Pure-Python discrete-event simulator. `vidur/simulator.py` is a `heapq` event
loop over `BaseEvent` objects; each event returns new events. No subprocess, no
external engine, no wall-clock coupling.

```
main.py -> SimulationConfig (flat_dataclass -> argparse)
        -> Cluster(replicas)                    vidur/entities/cluster.py
        -> RequestGeneratorRegistry             vidur/request_generator/
        -> GlobalSchedulerRegistry              vidur/scheduler/global_scheduler/
        -> Simulator.run(): heapq event loop    vidur/simulator.py:63
        -> MetricsStore -> CSV                  vidur/metrics/metrics_store.py
```

Timing comes from a learned model, not from a hardware simulator:
`vidur/execution_time_predictor/` fits random forests (or linear regression) to
the profiled per-operation CSVs in `data/profiling/compute/<device>/<model>/`.

Two-level scheduling, which maps cleanly onto our problem:

- **global scheduler** = the *router* (`BaseGlobalScheduler.schedule()` returns
  `List[Tuple[replica_id, Request]]`)
- **replica scheduler** = the per-replica batching policy (Sarathi, vLLM, Orca,
  FasterTransformer, LightLLM)

---

## 5. Requirement-by-requirement evidence

### R1 — multiple replicas · `main` PASS · `canary` PASS

`vidur/entities/cluster.py:29-33` builds `cluster_config.num_replicas` `Replica`
objects. Run 1 and run 3 above used 4 and 8 replicas and the metrics directory
contains `replica_1..4_memory_usage.json`. Per-replica utilisation/MFU are
reported separately.

### R2 — pluggable routing · `main` PASS · `canary` PASS (stronger)

`main`: `BaseGlobalScheduler` (`vidur/scheduler/global_scheduler/base_global_scheduler.py`)
is an ABC with one abstract method, `schedule()`. Implementations are registered
in `global_scheduler_registry.py` against a `GlobalSchedulerType` enum. Adding a
policy = one file + one enum member + one `register()` line. `main` ships three:
`round_robin`, `random`, `lor` (least outstanding **requests**).

`canary` ships **eleven** and, decisively for us, the base class gains the
callbacks a stateful router needs:

```python
def on_batch_end(self, batch): ...      # canary base_global_scheduler.py
def on_prefill_end(self, request): ...
def on_request_end(self, request): ...
```

with matching `PREFILL_END` / `REQUEST_END` event types
(`canary vidur/types/event_type.py`). `main` has neither the callbacks nor the
events. Those callbacks are what make a token-aware queue estimate (our B2-tok)
implementable *correctly* rather than approximately.

**Caveat, and it is a real one for research validity:** `canary` already
contains policies that are close to our B3:
`sticky_lor_scheduler.py` (session-sticky affinity),
`tolerant_sticky_lop_uncached_global_scheduler.py` (sticky affinity **with a
load-imbalance tolerance factor** — i.e. an overload guard), and
`ranked_sticky_lop_uncached_global_scheduler.py`. We would be characterising
*their* implementations, not ours.

That reduces one risk — authoring a treatment we unconsciously shaped to win —
but it does **not** remove tuning bias, and it does **not** establish that these
policies *are* our B3 as `PROJECT_SPEC.md` §5 specifies it. Both equivalence and
a symmetric parameter-tuning protocol remain to be established at M5/M6/M8. See
`recommendation.md` §2 "Research validity", point 2, as corrected 2026-09-10.

### R3 — cross-replica prefix-cache state · `main` FAIL · `canary` PARTIAL

`main`: **no prefix caching of any kind.** `grep -ri prefix vidur/ --include=*.py`
returns only logging prefixes and `flat_dataclass` field-name prefixes. There is
no token-id field on `Request` (`vidur/entities/request.py:28-34` takes only
`arrived_at`, `num_prefill_tokens`, `num_decode_tokens`, `num_processed_tokens`),
no block hashing, no cache manager. `attn_kv_cache_save` in the metrics is the
*cost of writing KV*, not a reusable cache. This is a hard fail, not a gap.

`canary`: a real vLLM-derived prefix cache exists.
- `vidur/kv_cache/` — `kv_cache_block.py`, `kv_cache_block_pool.py`,
  `kv_cache_block_queue.py`, `base_kv_cache_manager.py`,
  `replica_kv_cache_manager.py`, `disk_kv_cache_manager.py`.
- Chained block hashing in `vidur/kv_cache/utils.py:hash_request_tokens`,
  same construction as vLLM (`hash(parent_hash, block_token_ids)`).
- `VLLMV1ReplicaScheduler.get_cached_prefill_length(request)`
  (`vllm_v1_replica_scheduler.py:51`) — **this is the exact query a cache-aware
  router needs**, and the shipped cache-aware schedulers already call it.
- `CacheConfig` (`config.py:304`) exposes `enable_prefix_caching`,
  `block_size`, `prefix_caching_hash_algo`, `enable_disk_caching`,
  `disk_num_blocks`.
- Per-replica caches are private; a **shared disk tier** is injected into every
  replica scheduler when `enable_disk_caching` is on
  (`base_global_scheduler.py`: one `DiskKVCacheManager`, then
  `replica.set_disk_kv_cache(...)` for each replica).

Why **PARTIAL** and not PASS: the shared state is a *disk tier*, not a shared
GPU-resident cache, and the thing our RQ1 is about — "replica B cannot reuse
what replica A has hot" — is modelled only as "replica B must pay a disk recall".
That is arguably the right model, but it is a modelling decision we would be
inheriting, and it is not the same as a global cache-state view. What we
additionally need for B3/B4 is a router-side, cheap, *approximate* view of every
replica's cache; `get_cached_prefill_length` gives an exact view whose cost is a
full block-walk per (request, replica) pair. `TolerantStickyLOPUncached...`
memoises it in `self._cached_prefill_length_map` and never evicts that map —
an unbounded dict keyed by `(request.id, replica_id)`. At our request counts
that is a memory-growth bug we would have to fix.

### R4 — heterogeneous replica types · `main` FAIL · `canary` FAIL

This is the requirement both Vidur branches fail, and they fail it the same way.

`ClusterConfig` (`config.py:854`) holds **one** `replica_config: ReplicaConfig`
and an integer `num_replicas`. `Cluster.__init__` loops `range(num_replicas)`
constructing every `Replica` from that single config. `ReplicaConfig` is where
`model_name`, `device`, `network_device`, `tensor_parallel_size` and
`num_pipeline_stages` live. Confirmed at the CLI: `python -m vidur.main -h`
offers exactly one `--replica_config_device` for the entire cluster.

`BaseGlobalScheduler` compounds it: **one** `ExecutionTimePredictor` is built
from `config.cluster_config.replica_config` and shared by every replica
scheduler.

The profiling *data* for a heterogeneous fleet is already present —
`data/profiling/compute/{a100,a40,h100}/meta-llama/Llama-2-7b-hf/` exists for
all three SKUs, and `GPU_COSTS` in the analyzer prices a100/a40/h100. Only the
*code* assumes homogeneity.

`canary` makes the fix much smaller than `main` does: `Replica` already stores
its own `replica_config` (`canary vidur/entities/replica.py:15`), and only four
non-`config_optimizer` sites reference `cluster_config.replica_config` —
`base_global_scheduler.py:40,46` and `replica_metrics_store.py:60,220`.
`flat_dataclass.py:100-104` already supports list-typed fields via `nargs="+"`.

### R5 — mid-run replica removal / failure · `main` FAIL · `canary` FAIL

Neither branch has any failure, preemption-of-*replica*, drain, or
removal mechanism. The complete event vocabulary is:

- `main`: `BATCH_STAGE_ARRIVAL, REQUEST_ARRIVAL, BATCH_STAGE_END, BATCH_END, GLOBAL_SCHEDULE, REPLICA_SCHEDULE, REPLICA_STAGE_SCHEDULE`
- `canary`: the same plus `PREFILL_END, REQUEST_END`

**Trap worth recording:** Vidur uses the word *preemption* heavily
(`request.preempted`, `REQUEST_PREEMPTION_TIME`, `preempted_time`,
`num_restarts`). This is **vLLM-style scheduler preemption** — a request evicted
from the running batch when KV memory runs out and later restarted on the *same*
replica (`Request.restart()`, `request.py:305`). It is not spot preemption and
has nothing to do with a replica disappearing. Reading the metric names alone
would give the wrong answer for R5, which is exactly why this spike required
reading the code.

E4/H4 — our major result — is therefore **not** supported out of the box on
either branch. What is favourable is that the machinery a failure event needs
already exists and is well factored: an event class hierarchy with a uniform
`handle_event(scheduler, metrics_store)` signature, a replica-scheduler registry
holding all in-flight and queued requests per replica, and (on `canary`) a
per-replica KV cache object that can simply be dropped to model losing cache
state on preemption.

### R6 — SLO / deadline modelling · `main` PARTIAL (external) · `canary` PARTIAL (in-core)

`main`: nothing in the simulator core. SLOs exist only in the *offline* config
explorer: `config_optimizer/config_explorer/capacity_search.py:_is_under_sla`
reads the finished run's `request_scheduling_delay.csv` and compares a quantile
against `--scheduling_delay_slo_value`. Note it is **scheduling delay**, not
TTFT. `config_optimizer/analyzer/bottleneck_analyzer.py` carries
`ttft_slo_percentile/value` and `tbt_slo_percentile/value`, again post-hoc.

`canary`: SLOs enter the simulator itself. `vidur/utils/slo_manager.py` sets
`request.prefill_slo_time` from a `SloConfig` (`prefill_e2e_time_normalized`,
`prefill_e2e_time_min`) at admission; `Request.prefill_deadline_at` =
`queued_at + prefill_slo_time`; and `EDFRequestQueue`
(`scheduler/request_queue/edf_request_queue.py`) actually schedules on that
deadline. This is a genuine per-request deadline model — restricted to *prefill*
(TTFT), which is the SLO E1 uses, but with **no decode/TBT deadline** and **no
attainment metric** computed anywhere.

### R7 — cost accounting · `main` PARTIAL (post-hoc) · `canary` PARTIAL (post-hoc)

Cost is not in the simulator on either branch. It lives in the analyzer:
`config_optimizer/analyzer/constants.py:55` —

```python
GPU_COSTS = {"h100": 4.25, "a100": 2.21, "a40": 1.28}   # $/hr, CoreWeave, 2024-02-07
CPU_MACHINE_COST = 3.36
```

and `stats_extractor.py:209-221` derives `cost`, `capacity_per_dollar` and
`hour_cost_per_replica` from `runtime × num_gpus × price`. There is no
preemptible/spot price, no per-replica price attribution, and — because a
Vidur cluster is homogeneous (R4) — no notion of a *mixed* fleet's cost, which
is precisely what E1 has to search over.

Direction of travel is favourable though: `capacity_search.py` already binary-
searches QPS until an SLO breaks, at a fixed fleet, and prices the result. E1 is
the same machinery with the search variable moved from QPS to fleet
composition.

### R8 — per-request metrics · `main` PASS (with one gap) · `canary` PASS

`main` writes `request_metrics.csv`, one row per request, 21 columns, verified
at 128/128 rows. Includes `request_e2e_time`, `prefill_e2e_time` (= TTFT),
`request_scheduling_delay`, `request_preemption_time`,
`request_num_prefill_tokens`, `request_num_decode_tokens`, `request_num_restarts`.

**Gap:** there is no column identifying **which replica served the request**, and
no absolute arrival timestamp. For a routing study that is the one column we
cannot do without. It is a small addition — `Request` already carries the
information on `canary` (`request.replica_id`, set by `assign_replica`).

`canary` is materially better: `ClusterMetricsStore` holds a
`ReplicaMetricsStore` per replica, adds `REQUEST_ARRIVED_AT`, emits
`*_replicawise` breakdowns, and writes **`replica_prefix_cache_metrics`** — a
per-replica cache-hit summary, which is the diagnostic RQ1 lives on.

---

## 6. Sharp edges actually found on `canary`

Recorded because `canary` is an unmerged branch and the README warns about
exactly this.

1. **`hash_block_tokens` is called with 4 arguments and defined with 3.**
   `vidur/kv_cache/utils.py` defines
   `hash_block_tokens(hash_function, parent_block_hash, curr_block_token_ids)`
   but `hash_request_tokens` calls it as
   `hash_block_tokens(hash_function, parent_block_hash_value, block_token_ids, req_extra_keys)`.
   That path is only reached when a request has **no** externally supplied
   `block_hash_ids`. The code even says so: a `TODO` in the same file notes
   "we supply external block_hash_ids in the trace files". So the working path is
   the one we would use (Mooncake supplies hashes), but the fallback is broken.

   **Confirmed by execution, not inference** (`measured`, in the installed
   `canary` venv):

   ```
   hash_block_tokens signature: (hash_function, parent_block_hash, curr_block_token_ids) -> BlockHashType
   call-site: hash_block_tokens(hash_function, parent_block_hash_value, block_token_ids, req_extra_keys)
   RESULT: TypeError on fallback path -> hash_block_tokens() takes 3 positional arguments but 4 were given
   ```

   So: any workload **without** externally supplied block hashes — which
   includes a naive synthetic φ generator — raises immediately. Our synthetic
   generator must therefore emit block hashes itself (which it should anyway,
   since `PROJECT_SPEC.md` §7 requires it to *measure* realised sharing), or we
   fix the call. One-line fix; recorded so it is not rediscovered at M6.

2. **Unbounded memo.** `TolerantStickyLOPUncachedGlobalScheduler._cached_prefill_length_map`
   grows one entry per `(request, replica)` pair for the life of the run and is
   never pruned. At 10⁴ requests × 8 replicas that is 8×10⁴ entries per run —
   survivable, but it is a leak and it silently goes stale if the replica's
   cache changes between the estimate and the dispatch.

3. **`canary`'s last commit is 2025-06-25**, ~14 months before this spike, and it
   has not been merged to `main`. `assumption`: it will not be maintained. Any
   dependence on it must be pinned to the exact SHA and vendored, not tracked.

---

## 7. Things `canary` gives us for free that we had budgeted to build

- `data/processed_traces/mooncake_conversation_trace.csv` — **80 MB, 12 031
  requests**, columns `arrived_at, num_prefill_tokens, num_decode_tokens,
  block_hash_ids, block_size, session_id`. This is our **primary trace**
  (`PROJECT_SPEC.md` §7), already reduced to block-hash form, i.e. most of the
  M2 Mooncake loader.
- `TraceRequestGenerator` (`canary vidur/request_generator/trace_request_generator.py`)
  already parses `block_hash_ids` / `block_size` / `session_id` and tolerates
  their absence — so the same reader ingests our synthetic phi sweep and the
  cache-blind Azure control without a second code path.
- `uv.lock`.

`assumption`, to be checked at M2 and **not** to be taken on trust: that this
shipped CSV is a faithful reduction of the public Mooncake trace. We must
re-derive at least a sample of it from the upstream trace ourselves before any
RQ1 claim rests on it.

### 7a. …and a trap inside that free gift (`measured`)

The first attempt to run `canary` on this trace **crashed after 18 minutes of
simulation**:

```
File "vidur/scheduler/replica_scheduler/vllm_v1_replica_scheduler.py", line 170
AssertionError: num_new_tokens should be greater than 0 but got -24844
```

**Cause: my configuration, not a Vidur defect.** I paired the Mooncake trace
with `meta-llama/Llama-2-7b-hf`. Measured token-length distribution of the
shipped trace (12 031 requests, prefill + decode):

| min | median | p95 | max |
|---|---|---|---|
| 1 407 | **7 767** | **40 568** | **127 039** |

against the `max_model_len` of every model config `canary` ships:

| Model | `max_model_len` | Mooncake rows that fit |
|---|---|---|
| `Llama-2-7b-hf`, `Llama-2-70b-hf`, `Meta-Llama-3-8B`, `internlm-20b` | 4 096 | 3 575 / 12 031 |
| `Meta-Llama-3-70B` | 8 192 | — |
| `internlm2-20b`, `Qwen-72B` | 32 768 | — |
| `phi-2` | 2 048 | — |

**No shipped model config has a context window large enough for Mooncake's p95
request** (40 568 tokens vs a 32 768 maximum). That is a genuine constraint on
using this trace at native lengths, and it is not documented anywhere I found —
`main`'s README example sidesteps it by using the file as a *length* generator
with an explicit `--trace_request_length_generator_config_max_tokens 16384`
clip, which discards the block hashes and so cannot serve RQ1.

Two real findings, separate from my own error:

1. **Vidur validates this late and badly.** `TraceRequestGeneratorConfig` has a
   `max_tokens` field, but it is only asserted when *supplied*; nothing checks
   the trace against the replica's `max_model_len` at start-up. The result is an
   assertion failure deep inside the replica scheduler, 18 minutes in, with a
   message (`-24844`) that names neither the trace nor the model. A 30-second
   config check would have caught it.
2. **Carried into M2/M4 as work:** running Mooncake at native lengths needs
   either a long-context model config *plus profiling data to match it*, or an
   explicit, documented filtering/scaling policy. Whichever we choose is a
   research decision about the workload and must be recorded, because it changes
   the prefix-sharing structure RQ1 measures. This compounds falsifier **F4**.

Re-run on a subset that fits (512 Mooncake requests with ≤ 4 096 total tokens,
420 distinct sessions, spanning 633 s of arrivals) — see §3, run 4.
