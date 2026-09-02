# docs/spike/requirements-matrix.md — R1–R8 scored, with evidence

**Milestone:** M1 simulator-base spike · **Dates:** 2026-09-01 → 2026-09-02
**Requirements source:** `PROJECT_SPEC.md` §9

Candidates scored:

| # | Candidate | Commit |
|---|-----------|--------|
| **V-main** | Vidur, branch `main` | `abae7f63aa857300f5cdc6f5e0d27860cd24721b` |
| **V-canary** | Vidur, branch `canary` | `25e0082dbbfb206fb0477c3ebbededa7ead78949` |
| **LSS** | LLMServingSim 2.0 | `a4053bc1161872420e1e0607cb3409ef659b828e` |

`canary` is scored separately because `main`'s own README (line 145) directs
users needing prefix caching and routing policies to it. They are different
simulators for our purposes.

Scoring vocabulary — deliberately strict:

- **PASS** — works today, for our use, without code changes.
- **PARTIAL** — the mechanism exists but does not meet the requirement as
  `PROJECT_SPEC.md` states it (wrong scope, post-hoc only, or missing the
  interface we need).
- **FAIL** — absent.

Detailed evidence per candidate: `vidur-notes.md`, `llmservingsim-notes.md`.

---

## 1. The matrix

| # | Requirement | V-main | V-canary | LSS |
|---|-------------|:------:|:--------:|:---:|
| R1 | Multiple replicas | **PASS** | **PASS** | **PASS** |
| R2 | Pluggable routing | **PASS** | **PASS** | PARTIAL |
| R3 | Cross-replica prefix-cache state | FAIL | PARTIAL | **PASS** |
| R4 | Heterogeneous replica types | FAIL | FAIL | **PASS** |
| R5 | Mid-run replica removal / failure | FAIL | FAIL | FAIL |
| R6 | SLO / deadline modelling | PARTIAL | PARTIAL | FAIL |
| R7 | Cost accounting | PARTIAL | PARTIAL | FAIL |
| R8 | Per-request metrics | **PASS** | **PASS** | **PASS** |
| | **PASS / PARTIAL / FAIL** | 3 / 2 / 3 | 3 / 3 / 2 | 4 / 1 / 3 |

Counting passes is **not** how this decision was made — see §4 and
`recommendation.md`. R2 and R5 are worth more to this project than R4, because
R2 *is* the object of study and R5 *is* the major result (E4/H4).

---

## 2. Evidence, one line per cell

### R1 — multiple replicas

| | Evidence | Verified |
|---|---|---|
| V-main | `vidur/entities/cluster.py:29-33` builds `num_replicas` `Replica`s | **ran** 4 and 8 replicas; `replica_1..4_memory_usage.json` written |
| V-canary | same, `canary vidur/entities/cluster.py` + per-replica `ReplicaMetricsStore` | **ran** 4 replicas; session-sticky routing spread 512 requests **116 / 129 / 130 / 137** across them |
| LSS | one `Scheduler` per instance from the cluster JSON (`serving/__main__.py`) | **ran**; `instance id` column in output CSV |

### R2 — pluggable routing

| | Evidence | Gap |
|---|---|---|
| V-main | `BaseGlobalScheduler.schedule() -> List[(replica_id, Request)]`, ABC + `GlobalSchedulerRegistry` + `GlobalSchedulerType` enum; 3 policies shipped | no per-request-completion callbacks, so a stateful token-aware queue estimate must be reconstructed |
| V-canary | same, **11 policies** shipped, plus `on_batch_end` / `on_prefill_end` / `on_request_end` callbacks on the base class and matching `PREFILL_END` / `REQUEST_END` events | none blocking |
| LSS | `--request-routing-policy CUSTOM` → `Router._custom_select` (`serving/core/router.py`), `raise NotImplementedError` | **the request is not passed to the selector** (`self._select_instance(self.prefill_schedulers, "prefill")`), and policies are an `if/elif` over strings with no parameters. B2-tok/B3/B4 all need both fixed. |

### R3 — cross-replica prefix-cache state

| | Evidence |
|---|---|
| V-main | **Absent.** No token ids on `Request` (`entities/request.py:28-34`), no block hashing, no cache manager. `attn_kv_cache_save` is a *write cost*, not a cache. |
| V-canary | `vidur/kv_cache/` (block, block pool, block queue, replica manager, **disk manager**); chained block hashes in `kv_cache/utils.py`; `CacheConfig.enable_prefix_caching / enable_disk_caching`; **`get_cached_prefill_length(request)`** on the replica scheduler — the exact router-side query B3 needs. **Confirmed at runtime**, not just in source: a 512-request Mooncake run served `measured` **32.69 %** of prefill tokens from cache, reported per replica. **PARTIAL** because the only *shared* tier is a disk tier, and the per-(request, replica) lookup is exact and expensive rather than an approximate router view. |
| LSS | `TieredKVCacheManager` + `BlockPool` ported from vLLM v0.19.0; per-instance NPU pool **plus a node-level CPU/CXL pool shared across instances** under `--enable-prefix-sharing`; recall charged as `kv_load` on the critical path. Documented and code-confirmed. **Constraint:** the shared pool raises `RuntimeError` unless all instances share model, dtype and block size — so shared caching and heterogeneous *models* are mutually exclusive (heterogeneous *GPUs* are fine). |

### R4 — heterogeneous replica types

| | Evidence |
|---|---|
| V-main | `ClusterConfig` holds **one** `replica_config` + an int `num_replicas`; `Cluster` loops that one config; `python -m vidur.main -h` offers exactly one `--replica_config_device` for the whole cluster. Profiling data for a100/a40/h100 × Llama-2-7b **is** shipped; only the code assumes homogeneity. |
| V-canary | Same failure. Mitigating: `Replica` already stores its own `replica_config`, only 4 non-analyzer sites read `cluster_config.replica_config` (`base_global_scheduler.py:40,46`, `replica_metrics_store.py:60,220`), and `flat_dataclass.py:100-104` already supports list-typed CLI fields via `nargs="+"`. |
| LSS | Per-instance `model_name` / `hardware` / `npu_mem` / `num_npus` / `tp_size` / `max_num_seqs` / `enable_prefix_caching` in the cluster JSON (required keys read per instance at `config_builder.py:451`). **Verified by execution, not inference:** no bundled example mixes GPU SKUs, so one was written (`spike_mixed_gpu.json`, RTX4090 + RTXPRO6000, same model) and run — exit 0, and the two instances produced different timings from their own profile bundles (`measured`: mean TTFT 22.35 ms vs 15.36 ms, mean TPOT 17.11 ms vs 11.23 ms). |

### R5 — mid-run replica removal / failure

**All three FAIL.** No candidate models replica loss, spot preemption, drain, or
gray failure.

**Trap, recorded because it would mislead a reader of the metric names:** both
Vidur and LLMServingSim use "preemption" for **vLLM KV-pressure preemption of a
request**, which is restarted on the *same* replica
(`Request.restart()` / `Scheduler._preempt_request`, `scheduler.py:252`). It is
not spot preemption. R5 was scored by reading the event vocabulary, not the
metric names:

- V-main events: `BATCH_STAGE_ARRIVAL, REQUEST_ARRIVAL, BATCH_STAGE_END, BATCH_END, GLOBAL_SCHEDULE, REPLICA_SCHEDULE, REPLICA_STAGE_SCHEDULE`
- V-canary: the same **+ `PREFILL_END`, `REQUEST_END`**
- LSS: no event enum at all — the loop is driven by ASTRA-Sim's per-iteration stdout reports

The three FAILs are **not equal in cost to fix** (§3).

### R6 — SLO / deadline modelling

| | Evidence |
|---|---|
| V-main | Post-hoc only. `config_optimizer/config_explorer/capacity_search.py:_is_under_sla` thresholds a quantile of `request_scheduling_delay.csv` after the run; `analyzer/bottleneck_analyzer.py` carries TTFT/TBT SLO percentiles, also post-hoc. Nothing in the DES. |
| V-canary | **In-core.** `utils/slo_manager.py` stamps `request.prefill_slo_time` at admission from `SloConfig{prefill_e2e_time_normalized, prefill_e2e_time_min}`; `Request.prefill_deadline_at = queued_at + prefill_slo_time`; `scheduler/request_queue/edf_request_queue.py` schedules on it. PARTIAL: prefill/TTFT only, no decode/TBT deadline, and **no attainment metric is computed anywhere**. |
| LSS | Nothing. `grep -rin "slo\|deadline" serving/ bench/` yields only prose and `allocate_slots` false positives. |

### R7 — cost accounting

| | Evidence |
|---|---|
| V-main / V-canary | Post-hoc, in the analyzer, not the simulator: `config_optimizer/analyzer/constants.py:55` `GPU_COSTS = {"h100": 4.25, "a100": 2.21, "a40": 1.28}` $/hr (CoreWeave, 2024-02-07), `CPU_MACHINE_COST = 3.36`; `stats_extractor.py:209-221` derives `cost`, `capacity_per_dollar`, `hour_cost_per_replica`. No spot/preemptible price; no mixed-fleet cost (impossible while R4 fails). Favourable: `capacity_search.py` already binary-searches QPS-to-SLO-break at fixed fleet and prices the result — E1 is that machinery with the search variable moved. |
| LSS | **None.** No price table, no cost column, no `$`. `serving/core/power_model.py` models *energy*, which is not fleet cost and cannot be converted without inventing an electricity price. This is a fail against `PROJECT_SPEC.md` §3's **primary** outcome metric. |

### R8 — per-request metrics

| | Evidence |
|---|---|
| V-main | `request_metrics.csv`, **verified 128/128 rows**, 21 columns incl. `request_e2e_time`, `prefill_e2e_time` (TTFT), `request_scheduling_delay`, `request_preemption_time`, `request_num_restarts`. **Gap: no replica-id column, no absolute arrival timestamp** — the one column a routing study cannot do without. |
| V-canary | **Verified by running it:** `request_metrics.csv`, 512/512 rows, **25 columns**, including the three `main` lacks — **`replica`**, `request_arrived_at`, and **`request_num_prefill_tokens_cached`** (per-request prefix-cache hit). Also writes `replica_prefix_cache_metrics.json` with per-replica hit ratios (`measured`: 0.309 / 0.311 / 0.336 / 0.349; **32.69 %** of all prefill tokens served from cache). This is exactly the RQ1 diagnostic set. |
| LSS | `instance id, request id, model, input, output, arrival, end_time, latency, queuing_delay, TTFT, TPOT, ITL` — instance id present, and `ITL` is the **full per-token list**, not a summary. Gaps: no per-request cache-hit column exported (the components exist on the `Request`), and **no simulation-level seed flag** (seeds are hardcoded `42` in `router.py`, `gate_function.py`, `trace_generator.py`); `PROJECT_SPEC.md` §11 needs ≥10 seeds per cell. |

---

## 3. Extension effort for every failed / partial requirement

**These are `estimate`s, not measurements.** Basis for each is stated. Unit is
**engineer-days for one person already familiar with the codebase**, which we
are not yet — so a first-time premium applies and is stated per row.
Calibration anchor: the M1 spike itself (reading both codebases to this depth,
plus installing and running both) took approximately **1.5 days** of effort,
compressed.

### 3a. Vidur `canary` — the failed and partial cells

| Req | Work required | Est. | Basis for the estimate |
|-----|---------------|:----:|------------------------|
| **R4** heterogeneous replicas | (i) `ClusterConfig.replica_config` → a list of `(ReplicaConfig, count)`; (ii) `Cluster.__init__` builds from the list; (iii) `BaseGlobalScheduler` builds **one `ExecutionTimePredictor` per distinct (model, device, TP, PP)** instead of one; (iv) `ReplicaMetricsStore` reads `replica._replica_config`; (v) CLI plumbing for a list of replica groups | **3–5 d** | Only **4** non-analyzer call sites touch the shared config (grepped); `Replica` already owns its config; `flat_dataclass` already emits `nargs="+"` for list fields. The risk is (v): Vidur's config layer flattens nested dataclasses into argparse, and a *list of nested dataclasses* is a shape it does not currently produce. Upper bound assumes we sidestep that with a JSON fleet-spec file instead of pure CLI. |
| **R5** replica failure / preemption | New `ReplicaFailureEvent` + `ReplicaRecoveryEvent`; mark replica unavailable; re-queue its in-flight and waiting requests to the global scheduler; **drop its KV/prefix cache** (that is the H4 mechanism); exclude it from routing; account its cost only while alive; add gray-failure as a per-replica slowdown multiplier on the predictor output | **3–5 d** | The event system is uniform (`handle_event(scheduler, metrics_store)` on every event) and the global scheduler already owns `_replica_schedulers` and a `_request_queue`, so re-queueing is a list move. `canary` gives us `on_request_end`/`REQUEST_END` to keep router state consistent. The genuinely new work is deciding and documenting the semantics of "a request that was mid-decode when its replica died", not the plumbing. |
| **R6** SLO modelling | Extend `SloConfig` with a decode/TBT deadline and an explicit attainment definition; compute per-request `slo_met` and fleet-level attainment in the metrics store; expose p95-TTFT-based attainment as the E1 constraint | **1–2 d** | `prefill_slo_time` / `prefill_deadline_at` / `EDFRequestQueue` already exist; this is mostly a metric plus a config field. |
| **R7** cost accounting | Move `GPU_COSTS` into the simulator as config; per-replica `$/hr × alive-hours`; on-demand **and** spot prices; a fleet-cost column in the run summary; then the **minimum-cost-at-fixed-SLO search harness** over fleet compositions (E1) | **4–7 d** | The price table and `capacity_search.py` (binary search + ray parallel driver + SLO check) already exist as a working template; ~1 d of that is the cost model and ~3–6 d is the search harness, which is a first-class deliverable of M9 rather than a patch. Depends on R4 landing first. |
| **R8** replica id in output | Add `replica_id` and `arrived_at` columns | **0.5 d** | `request.replica_id` is already set by `assign_replica`. |
| **R3** router-side cache view | Replace the exact-and-unbounded `_cached_prefill_length_map` memo with a bounded, explicitly-approximate router-side estimator; fix the latent 4-arg/3-arg `hash_block_tokens` call | **2–3 d** | Both defects are located and small; the design question (how approximate a router's cache view should be) is a research decision we want to make anyway, and is an E5 ablation axis. |
| | **Total** | **13.5–22.5 d** | |

### 3b. LLMServingSim — the failed and partial cells

| Req | Work required | Est. | Basis for the estimate |
|-----|---------------|:----:|------------------------|
| **R2** pluggable routing | Widen `_select_instance` to receive the request; add a policy registry + per-policy config; expose a per-instance queue/cache query API to the router; implement B1/B2-req/B2-tok/B3/B4 against it | **4–6 d** | The `CUSTOM` hook and CLI flag exist, and `_least_load_select` shows the shape. But every policy we need reads request state the selector cannot currently see, and there is no config object, so the extension point has to be rebuilt before it can be used. |
| **R5** replica failure | Remove an instance mid-run while ASTRA-Sim's NPU topology (`network.yml`, `system.json`, written by `config_builder` **before** the backend is spawned) stays fixed; either keep the NPU alive and refuse to schedule it — changing utilisation/energy accounting — or restart the backend, which resets the clock | **8–15 d**, wide | This is the one requirement whose cost differs by an order of magnitude between candidates, because it crosses a **process and language boundary**. The frontend loop is keyed on NPU ids parsed from the backend's stdout (`controller.py:_ITERATION_RE`), and `read_wait()` blocks on a strict handshake. `hypothesis`: the "keep the NPU alive, refuse to schedule" route works and is the cheap end; unverified. |
| **R6** SLO modelling | From zero: per-request deadline, config, attainment metric | **2–4 d** | No existing scaffolding, but the raw TTFT/TPOT columns needed to compute attainment offline already exist, so the offline half is nearly free. |
| **R7** cost accounting | From zero: price table, per-instance alive-hours, fleet cost, spot prices | **2–3 d** | Small and self-contained; the per-instance structure already exists. |
| **R8** seeds + cache-hit columns | CLI seed threaded through router/gating/trace generation; export `num_npu_hit` / `num_lower_hit` per request | **1–2 d** | Values already computed; plumbing only. |
| **E1 harness** | An experiment driver that runs thousands of configurations: one **container + subprocess + per-batch disk I/O** per run, with no in-process API | **5–8 d; the per-request cost itself is not something harness engineering removes** | `serving/__main__.py` is a CLI entry point with no reusable `run()`. Throughput is now **measured**, not assumed: 300 requests on 2 instances took **4 m 51 s**, and the per-request cost is flat at **~1 s** from 10 to 300 requests, so it is a marginal rate. `estimate`: a 20 000-request run ≈ 5.5 h; E1 needs hundreds of such runs. Like-for-like (both with prefix caching), Vidur `canary` is `measured` at **~0.18 s/request** — about **5.5× cheaper**, and in-process so many cells can share one interpreter. An earlier draft of this file claimed ~60×; that compared against Vidur `main` with no prefix cache and was withdrawn. |
| | **Total** | **22–38 d** | |

### 3c. Build a small cluster-level DES from scratch (option C)

| Component | Est. | Basis |
|---|:---:|---|
| Event loop, cluster, replicas, request lifecycle | 2–3 d | Straightforward; Vidur's `simulator.py` is ~120 lines and is the reference shape. |
| Continuous-batching / chunked-prefill replica scheduler | 4–6 d | This is the part that decides whether the simulator is *credible*. Both candidates port vLLM's real scheduler; writing a plausible-looking one is fast, writing a faithful one is not. |
| Timing model + calibration against the M3 vLLM measurements | 5–8 d | We would be inventing the model that both candidates derived from profiling data. **This moves E8 from "validate a published, already-validated model" to "the entire result rests on a timing model we wrote ourselves."** |
| Prefix cache: block hashing, ref-counting, LRU eviction, tiers | 3–5 d | Correctness-critical for RQ1; both candidates port vLLM's block pool, which is ~500 lines of subtle code. |
| Cost, SLO, failure injection, metrics | 3–4 d | Cheap — this is the part we are adding to a chosen base anyway. |
| **Total** | **17–26 d** | |

Option C's day count is *not* much worse than option B's. Its cost is
**research validity**, not schedule: see `recommendation.md` §4.

---

## 4. How the requirements were weighted

`PROJECT_SPEC.md` does not weight R1–R8, so the weighting is stated here
explicitly rather than smuggled into the arithmetic:

| Requirement | Weight | Why |
|---|---|---|
| **R2** pluggable routing | highest | The routers *are* the independent variable. A base that makes policy implementation awkward taxes every week from M5 to M8. |
| **R5** replica failure | high | E4/H4 is named the **major result** in `PROJECT_SPEC.md` §6. |
| **R3** cross-replica cache | high | RQ1/E2, and the mechanism behind H4. |
| **R7** cost | high | The **primary** outcome metric (§3) — but cheap to add anywhere. |
| **R4** heterogeneity | medium | RQ2/E3, one MVP experiment, and the third heterogeneous mix is already cut-if-behind. |
| **R6** SLO | medium | Needed for E1, but definable offline from R8 output. |
| **R1**, **R8** | entry conditions | All three candidates clear them. |

Under this weighting, LLMServingSim's R4 advantage is bought at the price of the
two highest-weighted requirements (R2 partial, R5 an order of magnitude more
expensive), plus both of the cheap-but-mandatory ones (R6, R7 from zero).
