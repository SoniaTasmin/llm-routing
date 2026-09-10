# docs/workload-mooncake-f4.md — F4 verdict: is the shipped Mooncake CSV trustworthy?

**Date:** 2026-09-10 · **Milestone:** M2 · **Falsifier:** F4

**F4 asked:** *"The shipped `mooncake_conversation_trace.csv` cannot be
reproduced from the upstream Mooncake trace, so its prefix structure is
unverifiable."*

**Verdict: F4 does NOT fire.** The shipped CSV is a faithful reduction of the
upstream trace as far as prefix sharing is concerned — the structure RQ1 measures
survives its transformation to within **0.77 percentage points**. But it carries
three modifications we decline to adopt, one of which would have quietly changed
what our sticky-routing results mean.

**We use our own re-derivation regardless.** F4 is answered, not by trusting the
CSV, but by no longer needing to.

---

## What was compared

| | Upstream | Shipped with Vidur `canary` |
|---|---|---|
| File | `FAST25-release/traces/conversation_trace.jsonl` | `data/processed_traces/mooncake_conversation_trace.csv` |
| Repo | `github.com/kvcache-ai/Mooncake` @ `eeaca79aa298fdaf89580f0db1f12340ea206b32` | vendored Vidur @ `25e0082` |
| SHA-256 | `b8cbb061a85206d7…` (recorded in every manifest we emit) | — |
| Records | **12 031** | **12 031** |

Upstream schema, one JSON object per line:

```json
{"timestamp": 0, "input_length": 6758, "output_length": 500,
 "hash_ids": [0, 1, 2, ..., 13]}
```

**Block size is 512 tokens.** Not documented in the file; established
empirically and holding for **12 031 / 12 031** records
(`len(hash_ids) == ceil(input_length / 512)`). Nothing else fits — 16, 64, 128,
256 and 1024 each match **0** records. `load_mooncake` re-checks this on every
load rather than trusting the constant.

---

## What matches exactly

| Field | Result |
|---|---|
| Record count | 12 031 = 12 031 |
| Decode lengths | **identical multiset** |
| Arrival times | identical (upstream ms → seconds; both span 3 536.999 s) |

---

## What differs, and what we did about each

### 1. Every prompt is 512 tokens longer in the shipped CSV

`shipped_prefill == upstream_input_length + 512` for **all 12 031 rows** — a
uniform, exact one-block inflation. It is not block-padding
(`ceil(input/512)*512` matches 0 rows) and not `len(hash_ids)*512` (also 0 rows).

We could not determine the reason from the source. On the median request it is a
**+7 %** inflation of prompt length, which propagates into prefill time, KV
footprint and therefore every latency and cost number downstream.

**Our loader does not do it.** `num_prefill_tokens = input_length`, unchanged.

### 2. `session_id` is invented — and our routing policies key on it

Upstream has **no session field at all**. The shipped CSV carries 7 417 sessions
over 12 031 requests, produced by a rule we could not recover.

The grouping is not arbitrary — it captures the sharing structure well:

| Reuse | Blocks | Share of all prefill blocks |
|---|---|---|
| within-session | 92 214 | 31.96 % |
| cross-session | 13 496 | 4.68 % |

So ~87 % of all reuse falls inside the shipped session boundaries. Whoever built
it did a competent job.

**We still decline it**, because B3 and Vidur's `sticky_lor` route *on this
field*. Adopting it would mean routing on a grouping a third party inferred while
reporting results about Mooncake — and RQ1 is precisely a question about how
routing interacts with sharing structure. Our loader sets `session_id = None`.

*Consequence, carried forward:* session-sticky policies cannot be run on Mooncake
until we derive sessions ourselves under a rule recorded in `DECISIONS.md`. That
is M6 work. The synthetic sweep is unaffected — there, sessions are ground truth
by construction.

### 3. Re-blocked from 512 to 16 tokens, and extended over decode

The shipped CSV re-blocks at `block_size = 16` and its `block_hash_ids` covers
**prefill + decode** (`len == (prefill+decode)//16`, confirmed on 3 000 rows).

Extending the hash chain over generated tokens is defensible for a *cache* model
— vLLM does cache generated KV — but it is wrong for a *router* input, because a
router choosing a replica at admission cannot know what will be generated. Our
schema hashes prefill only.

---

## The measurement that decides F4

Realised prefix sharing, same definition applied to both
(`workload.sharing.measure_realised_sharing`), prefill blocks only, arrival
order, infinite cache:

| Source | Block size | Blocks | Reused | **Realised sharing** |
|---|---|---|---|---|
| Upstream, all `hash_ids` | 512 | 288 500 | 105 710 | **36.64 %** |
| Shipped CSV, prefill portion | 16 | 9 429 005 | 3 382 720 | **35.88 %** |
| **Our re-derivation** (whole blocks only) | 512 | 276 491 | 105 592 | **38.19 %** |

**Shipped vs upstream: −0.77 pp.** Re-blocking from 512 to 16 tokens preserves
the sharing structure almost exactly — which is the substantive question F4
asked, and the answer is reassuring.

Our own figure (38.19 %) sits 1.55 pp above the raw upstream number because the
schema drops each request's trailing partial-block hash id: partial blocks are
never hashed and are always recomputed, so counting them would overstate the
denominator. Same data, a stricter and better-defined denominator.

---

## Verdict

| Question | Answer |
|---|---|
| Can the shipped CSV be reproduced from upstream? | Yes in structure; **no** exactly — the +512 inflation and the invented `session_id` are not recoverable from the source data |
| Is its prefix structure unverifiable? | **No.** It is verifiable and it is faithful, to within 0.77 pp |
| **Does F4 fire?** | **No** |
| Do we adopt it? | **No** — we use our own re-derivation, so the question stops mattering |

The residual risk F4 was written to catch has been retired by removing the
dependency rather than by trusting it. The upstream file's SHA-256 is recorded in
every manifest we emit, so any result can be traced to exact bytes.

**Reproduce this comparison:** `python -m pytest tests/test_workload_generators.py`
for the loader invariants; the numbers above come from
`.spike/mooncake_upstream/repo` at the commit named in the table, fetched per
`REPRODUCE.md`.
