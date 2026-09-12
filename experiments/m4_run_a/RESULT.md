# M4 Run A — integration check: **FAIL**

**Date:** 2026-09-12 · **Authorised:** bounded, no-spend integration check
**This is an integration check. It is NOT evidence about D′ long-context
feasibility or timing fidelity, and must not be cited as either.**

---

## Result

| | |
|---|---|
| **Verdict** | **FAIL** — blocked by a schema/contract incompatibility |
| Requests completed | **0 of 128** — the run aborted during request construction, before simulation |
| Cached predictor reused | **YES** — see evidence below |
| Any new fit | **NO** — `require_cache` mode, and zero `Trained model` lines in the log |
| Wall clock | **122 s** for both attempts (limit 600 s) |
| Peak process-tree RSS | **3.96 GB** (limit 5.5 GB — not approached) |
| Determinism | **NOT ESTABLISHED** — both runs failed byte-identically excluding timestamps, but no simulated output was produced to compare |
| GPU / spend | none |

### Evidence that the cached predictor was genuinely reused

- Run under `--random_forest_execution_time_predictor_config_cache_mode require_cache`,
  which **raises** rather than fitting if any artefact is missing. It did not raise.
- Zero occurrences of `Trained model` in the full log.
- Peak RSS 3.96 GB, consistent with M1's measured 4.02 GB for loading the same
  1.3 GB cache; a cold path would have been far smaller before fitting began.
- Log reaches `Getting predictions for compute operations` → `...attention
  operations`, i.e. the predictor was constructed from cache and queried.

---

## Why it failed

`vidur/entities/request.py:47-56` asserts:

```python
last_block_size = num_prefill_tokens + num_decode_tokens - block_size * len(block_hash_ids)
assert 0 <= last_block_size < block_size
```

**Vidur requires `block_hash_ids` to cover `prefill + decode`.** Confirmed
against the CSV it ships: for row 0, `prefill=7270, decode=500, bs=16,
len(hashes)=485`, and `(7270+500)//16 = 485` while `7270//16 = 454`.

**Our unified schema deliberately hashes prefill only** — schema rule 3,
`docs/workload-schema.md`: *"a router choosing a replica at admission time does
not know what the model will generate, so hashing decode tokens would leak
future information into a routing decision."*

So the failure is not a bug in either side. It is a **design collision** between
our schema rule and Vidur's data contract, and Run A found it for free in two
minutes. Observed: `AssertionError: 318 is not in the range [0, 16)`.

---

## Second finding, not blocking but decision-relevant

While characterising the above I checked whether satisfying Vidur's contract
would be safe. **It would not be, without further work.**

`KVCacheManager.get_computed_blocks` (`base_kv_cache_manager.py:110-140`) walks
**the entire `block_hashes` list** and stops at the first miss. It is **not
bounded by `num_prefill_tokens`**. `get_cached_prefill_length` — the exact query
B3 and B4 route on — returns that walk's length.

So if we supplied prefill+decode hashes as Vidur expects, a request whose
*generated* tokens were already cached by an earlier identical conversation
would be credited with them at admission, and the router would be making
decisions informed by **this request's own un-generated output**.

That is future-information leakage into the independent variable of the whole
study. It sits in Vidur canary's model, not in anything we wrote, and it bears
directly on `PROJECT_SPEC.md` §5's baseline discipline and on RQ1's validity.

---

## What this does and does not establish

**Does:** the workload→trace→Vidur path is exercised end to end up to request
construction; the predictor cache loads and is reusable under `require_cache`;
memory and wall-clock limits are comfortable at this scale; the G4a expansion
produces a trace Vidur parses (128 requests loaded successfully); the failure is
reproducible.

**Does not:** anything about Llama-3.1-class or 65 536-token feasibility — this
ran `Llama-2-7b-hf` at 4 096 tokens on a different profile and predictor.
Anything about timing fidelity. Anything about **G4c**, which remains open and
was not probed: no 512-vs-16 timing comparison was run, per instruction.

---

## Reproduce

```bash
python experiments/m4_run_a/build_run_a_workload.py      # deterministic 128-request subset
python experiments/m4_run_a/to_vidur_trace.py \
    experiments/m4_run_a/run_a_workload.jsonl experiments/m4_run_a/run_a_trace.csv
bash experiments/m4_run_a/run_a.sh                        # enforces both limits, logs in full
```

Input artefact: `mooncake-conversation-trunc65536.jsonl`,
sha256 `456d80dc9098fa524c0d58180d1806315b0a39e034d95f577add4b77dd3747c2`,
first 128 requests in arrival order with prefill+decode ≤ 4 096,
block hashes expanded 512→16.

---

## Decisions this raises — **not taken here**

1. **How to reconcile prefill-only hashing with Vidur's whole-sequence
   contract.** Candidates: emit prefill+decode hashes in the Vidur *adapter*
   only, keeping the schema prefill-only; or bound the cache walk by
   `num_prefill_tokens` in a recorded patch outside `vendor/`; or pad decode
   positions with never-matching ids, which would wrongly model generated KV as
   unshareable. Each has a different effect on RQ1.
2. **Whether the unbounded cache walk is acceptable** for a study whose central
   comparison is routing quality.

Both belong to M4 and need the user's call. The vendored tree remains
unmodified; its checksum still verifies.
