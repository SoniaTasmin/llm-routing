# M4 Run A — integration check: **PASS**

**Date:** 2026-09-12 · bounded, no-spend integration check
**This is an integration check. It is NOT evidence about D′ long-context
feasibility, timing fidelity, or G4c, and must not be cited as any of them.**

---

## Result

| | |
|---|---|
| **Verdict** | **PASS** |
| Requests completed | **128 / 128** |
| Cached predictor reused | **YES** — `require_cache`; zero `Trained model` lines; peak RSS matches M1's 4.02 GB for the same 1.3 GB cache |
| New predictor fit | **NO** |
| Wall clock | **143 s** (limit 600 s) |
| Peak process-tree RSS | **3.94 GB** (limit 5.5 GB) |
| **Determinism** | **ESTABLISHED** — `request_metrics.csv` byte-identical across both runs; simulated end time `164.20146542016323 s` in both |
| GPU / spend | none |
| Vendored tree | **INTACT** — checksum re-verified; no patch applied |

---

## Leakage: **CONFIRMED BY DEMONSTRATION**, then prevented

Previously I asserted this from reading code. `leakage_probe.py` demonstrates it.

Two requests, **identical 32-token prompts**, differing *only* in the hashes
covering tokens not yet generated, against a pool holding an earlier identical
conversation:

| | admission-time `get_cached_prefill_length` |
|---|---|
| output hashes coincide with the cached prior | **64 tokens** |
| output hashes differ | **32 tokens** |

Both findings are therefore established, not inferred:

1. Changing **only** future-output hashes changes the admission-time estimate
   that B3/B4 route on.
2. The estimate **exceeds the prompt length** (64 > 32) — output tokens credited
   as cached prompt tokens.

**Caps traced along the full path.** `KVCacheManager.get_computed_blocks`
(`base_kv_cache_manager.py:110-142`) walks the whole hash list, breaks at the
first miss, returns `len(computed_blocks) * block_size`. `ReplicaKVCacheManager`
does **not** override it. **No bound at `num_prefill_tokens` anywhere.** The
`vllm_v1` scheduler's own use is protected only accidentally — over-crediting
makes `num_new_tokens` negative and trips an assertion — but
`get_cached_prefill_length`, the router's input, is returned **uncapped**.

---

## The adapter, and why no vendor patch was needed

Canonical schema stays **prompt-only**. The adapter
(`src/workload/vidur_adapter.py`) emits, per request:

```
[ real prompt-block ids ]  ++  [ request-unique placeholders ]
     prefill // block_size            up to (prefill+decode) // block_size
```

The block straddling the prompt/output boundary is a placeholder: its contents
mix prompt and generated tokens, so its identity is genuinely unknown.

**The bound is achieved by construction.** Each placeholder is unique to one
request, so the first one is never in a shared pool at admission, and the chained
walk **necessarily breaks there**. The admission-time estimate can therefore
never exceed the complete prompt blocks — **without modifying the vendored
simulator**. Checksum re-verified after the run.

Id spaces are disjoint and checked: expanded prompt ids (small), G4 prompt-tail
ids (≥ 2⁴⁰), output placeholders (≥ 2⁵⁰).

### Verified in the actual run

| Invariant | Result |
|---|---|
| `cached_prompt_tokens ≤ prompt_tokens`, every request | **0 violations / 128** |
| Full requested decode performed | **41 591 simulated = 41 591 requested** |
| Prompt tokens | 206 679 requested, **67 584 (32.70 %)** credited as cached |
| Routing exercised | all 4 replicas used |

The 32.70 % sits below the workload's 37.08 % infinite-cache ceiling, as a finite
evicting cache should.

---

## Limitation, stated plainly

**Unique output placeholders cannot reproduce reuse of generated content between
requests.** If two conversations generate the same continuation, the second
cannot hit the first's output KV here.

For Mooncake specifically this is narrower than it sounds: a later turn's
*prompt* already contains the earlier turn's output, and Mooncake hashes the
whole input, so **cross-turn reuse is captured through prompt hashes**. What is
lost is reuse of output that has not yet reappeared in anyone's prompt. Closing
that would need per-token output identity, which the trace does not carry — a
limitation of the data, not of the adapter.

---

## What this does and does not establish

**Does:** workload → adapter → trace → Vidur works end to end; 128/128 requests
simulate; the predictor cache loads and is reusable under `require_cache`; output
carries `replica` and `request_num_prefill_tokens_cached`; the no-future-
information invariant holds in a real run; results are bit-reproducible;
resource limits are comfortable at this scale.

**Does not:** anything about Llama-3.1-class or 65 536-token feasibility — this
ran `Llama-2-7b-hf` at 4 096 tokens on a different profile and predictor.
Anything about timing fidelity. Anything about **G4c** — no 512-vs-16 timing
comparison was run, per instruction, and G4c stays open.

---

## Reproduce

```bash
python experiments/m4_run_a/build_run_a_workload.py
python experiments/m4_run_a/to_vidur_trace.py \
    experiments/m4_run_a/run_a_workload.jsonl experiments/m4_run_a/run_a_trace.csv
bash experiments/m4_run_a/run_a.sh
# and the leakage demonstration:
cd .spike/vidur-canary && PYTHONPATH=. ./.venv/bin/python \
    ../../experiments/m4_run_a/leakage_probe.py
```

Input: `mooncake-conversation-trunc65536.jsonl`, sha256
`456d80dc9098fa524c0d58180d1806315b0a39e034d95f577add4b77dd3747c2`, first 128
requests in arrival order with prompt+output ≤ 4 096, hashes expanded 512→16.
