# NOTEBOOK.md — Chronological Research Diary

Append-only, newest entry at the bottom. This is a *research* diary: it records
what was tried, what failed, what surprised us, and what was abandoned. Failed
attempts and rejected approaches are **documented, not erased**.

Every quantity recorded here must be labelled:
`measured` · `hypothesis` · `estimate` · `assumption`.

---

## 2026-08-31 — Milestone 0 frozen; repository memory system created

**Week 1, day 1.**

**What happened.**
Milestone 0 (research specification) was approved by the user and frozen. The
repository was initialised as the permanent memory of the project, on the
principle that the Claude conversation is *not* the source of truth and will not
survive.

**Created.**
- Directory structure: `src/`, `simulator/`, `workloads/`, `experiments/`,
  `analysis/`, `configs/`, `tests/`, `results/`, `docs/` (+ `docs/spike/` for
  the Milestone-1 artefacts).
- Memory system: `CLAUDE.md` (permanent assistant contract), `PROJECT_SPEC.md`
  (frozen M0 spec), `CURRENT_STATUS.md`, `MILESTONES.md`, `DECISIONS.md`,
  `NOTEBOOK.md`, `REPRODUCE.md`, `README.md`.
- Initial decisions D-001..D-005 recorded, plus D-006 as an explicit placeholder
  for the simulator-base outcome.

**Deliberately NOT done** (scope discipline for M1):
- No routing policies (B1/B2-req/B2-tok/B3/B4).
- No simulator code.
- No trace downloads.
- No Kubernetes, no infrastructure.
- No experiment runs. **No measurements of any kind exist yet.**

**Environment notes (`measured`, from this machine).**
- Working directory `/mnt/d/llm-routing-research` on WSL2, Linux
  6.18.33.2-microsoft-standard-WSL2.
- `python3 --version` -> Python 3.14.4.
- `gh` CLI: **not installed**.
- Git: no global user identity configured, no credential helper, no remotes.

**Consequences of the environment notes.**
- Python 3.14 is very new. Vidur and LLMServingSim both pin scientific-Python
  stacks; wheels for 3.14 may not exist for some pinned versions. `hypothesis`:
  the M1 spike will likely need a separate pinned virtualenv (3.10/3.11) per
  candidate simulator rather than the system interpreter. This is expected to be
  the first real friction point of the spike and is recorded here *before*
  encountering it, so the prediction can be checked later.
- The GitHub remote under `SoniaTasmin` could not be created from this machine
  (no `gh`, no credentials). The local repository exists and is committed;
  remote creation is an open item in `CURRENT_STATUS.md`.
- Git identity was configured **repo-locally** (not globally), specifically so
  that the user's office GitLab identity is never attached to this project.

**Open questions carried into M1.**
1. Does either candidate simulator model **cross-replica** prefix-cache state,
   or only per-replica caches? (R3 is the requirement most likely to fail.)
2. Does either support **mid-run replica removal** without restarting the run?
   (R5 — needed for E4/H4, the major result.)
3. Is routing a pluggable interface or hard-coded in the scheduler? (R2)

**Repository hygiene pass (same day).**
Ran an AI-provenance scan over all ten committed text files via the local
watermark service. Result (`measured`): every file reported
`suspicious_total: 0`, no Layer A invisible-Unicode carriers, no C2PA, no AI
metadata, no frontmatter. An independent grep for zero-width, bidi, tag,
variation-selector, BOM and NBSP codepoints found nothing. No file was
modified by the scan. Note the service instance had no text-watermark detector
available, so statistical (token-sampling) marks were **not** measured either
way — this is an untested dimension, not a clean result.

**Decision taken during the hygiene pass.** The initial commit originally
carried `Co-Authored-By: Claude Opus 5` and a `Claude-Session:` URL. Since the
GitHub repository is public and backs an academic application, the user chose to
strip both trailers before the first push and to omit them from future commits.
Recorded as a standing rule in `CLAUDE.md` §15. This was done by amending the
single unpushed commit; no research history existed yet, so the
"never rewrite history" rule is not in tension with it.

**Remote.** The user created `https://github.com/SoniaTasmin/llm-routing`
(public) — note the name is `llm-routing`, not `llm-routing-research`; the local
working directory keeps the longer name. Clone URL in `REPRODUCE.md` updated to
match.

**Next.** Awaiting explicit user approval to begin the Milestone-1
simulator-base spike. Stopped here per the milestone protocol.

---

## 2026-09-01 → 2026-09-02 — Milestone 1: the simulator-base spike

**Week 1, days 2–3.** User approved M1 to begin. Ran it end to end. This entry
records what failed, what stalled, what I nearly got wrong, and the timings —
the scored evidence lives in `docs/spike/`.

### The prediction from 2026-08-31 was right, and for the right reason

The previous entry recorded a `hypothesis` that Python 3.14.4 would be too new
and that each candidate would need its own pinned interpreter. Confirmed. Both
candidates require Python ≥3.10 and pin scientific-Python stacks that have no
3.14 wheels. Every environment in this spike was built with `uv venv --python
3.10` or inside a container shipping 3.10.12. Recording it as a **correct
prediction** rather than quietly benefiting from it.

The three open questions carried into M1 all resolved, and two of the three
answers were the opposite of what the framing implied:

1. *Cross-replica prefix-cache state?* **LLMServingSim yes** (per-instance NPU
   pools plus a node-level CPU/CXL pool shared across instances). **Vidur
   `main` has no prefix cache at all**; Vidur `canary` has one, with a shared
   *disk* tier.
2. *Mid-run replica removal?* **Neither.** All three candidates fail R5.
3. *Is routing pluggable or hard-coded?* **Vidur: genuinely pluggable** (ABC +
   registry + enum). **LLMServingSim: a hook that cannot see the request** — an
   `if/elif` over policy-name strings whose selector is called as
   `self._select_instance(self.prefill_schedulers, "prefill")`, with the request
   in scope at the call site but never passed.

### The thing that would have made this spike worthless

Vidur's `README.md` line 145 sends anyone wanting prefix caching or routing
policies to a **`canary` branch**. I nearly scored `main` and stopped. `main`
has no prefix cache, no token ids on `Request`, three routing policies and no
SLO in the simulator. `canary` has a vLLM-derived block-pool prefix cache,
eleven routing policies including session-sticky ones with an explicit
load-imbalance guard, per-request prefill deadlines with an EDF queue,
per-replica cache-hit metrics, a `uv.lock`, and a preprocessed **Mooncake**
trace with block hashes and session ids.

Scoring `main` alone would have produced "Vidur cannot do R3, R6; use
LLMServingSim." That would have been wrong. Both branches are scored separately
in `docs/spike/requirements-matrix.md`.

**Generalised lesson, worth carrying:** for a research codebase, the default
branch is not necessarily where the research features are.

### The naming trap that would have made R5 wrong

Both Vidur and LLMServingSim use **"preemption"** heavily —
`request.preempted`, `REQUEST_PREEMPTION_TIME`, `num_preemptions`,
`Scheduler._preempt_request`. In both, this means **vLLM KV-pressure preemption
of a request**, which is then restarted on the *same* replica. It has nothing to
do with spot preemption or a replica disappearing, which is what R5 and our
E4/H4 are about.

Reading metric names would have scored R5 as PASS for both. R5 was scored by
reading the **event vocabulary** instead — seven event types in Vidur `main`,
nine in `canary`, none of them a failure — and it is FAIL for all three
candidates.

### Dead ends and stalls, in order

**1. Vidur `main` first run: 4 h 37 m.** (`measured`) Not a failure — a
one-time random-forest execution-time-predictor fit over the profiled operation
CSVs, cached to `cache/` (235 MB, 11 `.pkl`). The **simulation itself was ~4
seconds**. Second identical run: **1 min 1.7 s**, of which ~57 s was loading
that cache. Startled me enough that I checked the process was alive rather than
hung; it was fitting 4 models with a grid search across 8 cores. This is a
per-`(model, device, TP)` cost, so it will recur when E3 introduces new GPU
SKUs. Flagged as falsifier **F2**.

**2. Vidur boolean CLI flags.** `--metrics_config_write_json_trace false`
fails with `unrecognized arguments: false`. Vidur's `flat_dataclass` emits
`argparse.BooleanOptionalAction`, so the form is `--no-metrics_config_...`.
Thirty seconds lost; recorded because it will bite again.

**3. LLMServingSim submodules: the first `git submodule update --init
--recursive` silently left 5 of the 10 submodule paths unchecked-out.** `git submodule
status --recursive` showed them prefixed `-`. A second invocation completed it.
Cause not established — plausibly a timeout on the nested clones. Recorded in
`REPRODUCE.md` as "run it twice".

**4. `./scripts/compile.sh` stalled, apparently forever.** It reached a
`pip install` of Chakra which pulls `HolisticTraceAnalysis` from GitHub with
`git clone --filter=blob:none`, *inside* the container. The clone sat at 23 MB
with no working tree for **~25 minutes** and no growth.

Diagnosis, because "it hangs" is not a finding: I tested `git ls-remote` from
inside the container — it returned instantly, so the container's network was
fine. The stall is the blobless partial clone doing a lazy per-object fetch
during checkout. **Environment/network-shape problem, not an LLMServingSim
defect.**

Workaround, now in `REPRODUCE.md` §3a: clone `HolisticTraceAnalysis` on the
host (took seconds — a full clone, no filter) into the mounted tree, then
`pip3 install ./_hta` before `pip3 install ./astra-sim/.../chakra`. Both then
succeeded and `import chakra` worked.

**5. The ASTRA-Sim build took 11 h 29 m.** (`measured`, in-container `time`,
exit 0, binary produced.) The project documents this as **"2–5 minutes on a
typical machine"**.

Before treating this as a mark against LLMServingSim, I checked whether it was
an environment artefact:
- Host and container clocks agree (`03:34 UTC` = `09:34 +06`), so this is not
  clock skew — the elapsed time is real and matches the wall-clock gap between
  launching the build and its completion.
- The machine has **8 cores**, and `build.sh` runs cmake with up to 16 threads.
- The C++ sources sit on `/mnt/d`, a Windows **DrvFs** mount, which is
  pathologically slow for the many-small-files access pattern of a cmake build
  over fmt + spdlog + protobuf + ASTRA-Sim.

**Attribution: environment, not the project.** It is nevertheless a real cost
*on the machine this project will actually be done on*, and it is recorded as
such rather than discounted. A reviewer trying to reproduce our work on a
Windows/WSL machine would hit the same wall.

**6. Two contaminated measurements, discarded — and the correction matters.**
My first LLMServingSim timings were taken while Vidur `canary` was fitting
predictors across all 8 cores. The two-instance run reported **26 m 35 s** wall
against only **5.2 s of user CPU** — it was starved, not slow. The
single-instance run reported 37.96 s under the same contention.

Re-measured on an idle machine:

| Run | Instances | Requests | Contaminated | Clean |
|---|---|---|---|---|
| single instance | 1 | 10 | 37.96 s | **9.0 s** |
| shared CPU prefix pool | 2 | 10 | 26 m 35 s | **14.4 s** |

A **110× error** on the second one. Had I not noticed the user-CPU/wall
discrepancy I would have written a scoring document asserting that
LLMServingSim is unusably slow, which is false, and the recommendation would
have rested on a fabrication I produced myself. Recording the mechanism:
**check user-time against wall-time before believing any wall-clock number
taken on a shared machine.**

**7. A throughput probe, because the clean numbers demanded one.** The clean
small-run figures made LLMServingSim look *fast*, which cut against my
in-progress framing of its per-run cost as an E1 risk. Rather than leave the
claim as a suspicion, I generated a 300-request workload
(`spike_throughput_300.jsonl` — ~10 req/s Poisson, 1024-token prompts sharing a
512-token prefix) and ran it on 2 instances with the shared CPU pool.

`measured`: **4 m 51 s**, i.e. **~0.97 s per request** — flat against the 10-
request runs, so it is a marginal rate rather than start-up overhead. Vidur
`main`, `measured`: 2048 requests on 8 replicas in **32 s** of simulation,
~**0.016 s per request**.

I first wrote that up as a **~60× gap**. It is not. That number compared
LLMServingSim (vLLM-derived block-pool caching) against Vidur `main` running the
cheap Sarathi scheduler with **no prefix cache** — different work. Once Vidur
`canary` ran with prefix caching on, the figure was **~0.18 s/request**, i.e.
about **5.5×**.

Recording the error rather than the corrected number alone: I reached for the
fastest Vidur measurement I had instead of the comparable one, and it flattered
the option I was already leaning towards.

**Second correction, 2026-09-10, from user review.** I then described 5.5× as
"like-for-like, both with prefix caching". That is also wrong, and worse, because
it *sounds* controlled. Enabling prefix caching in both simulators does not make
their workloads equivalent — the two runs differ in trace (512 real Mooncake
requests vs 300 synthetic 1 024-token prompts), replica count (4 vs 2), replica
scheduler, and cache topology. The only defensible description is **indicative
across the configurations tested**: single-digit times lower. Corrected in all
four spike documents plus D-007.

The lesson generalises past this number: *matching one variable between two
systems does not make a comparison controlled.* I matched the variable I had been
thinking about and called the rest equal.

`estimate`: a 20 000-request LLMServingSim run is ~5.5 h, and E1 needs hundreds
of runs — so the underlying concern survives, but as an order-of-magnitude
observation, and it is a contributing reason for the decision rather than a
load-bearing one.

That same probe also confirmed **R3 at runtime rather than from documentation**:
NPU prefix hit **49.67 %**, and a non-zero **cross-instance CPU-pool hit of
0.17 %**. The shared node-level tier genuinely serves recalls.

**8. LLMServingSim's heterogeneity claim, tested rather than trusted.** R4 is
the one requirement LLMServingSim clearly wins, so it deserved more than a
reading of the config schema — and no bundled example actually mixes GPU SKUs.
I wrote `spike_mixed_gpu.json` (one RTX4090, one RTXPRO6000, same model,
round-robin) and ran it. Exit 0, 5 requests per instance, and the two instances
produced different timings from their own profile bundles (`measured`: mean TTFT
22.35 ms vs 15.36 ms; mean TPOT 17.11 ms vs 11.23 ms). **R4 is a verified PASS
for LLMServingSim.** Recorded emphatically because it is evidence *against* the
option I am recommending, and the report is worth less if it only tests the
candidate it likes.

**9. The canary run crashed after 18 minutes — and it was my fault.** First
attempt to drive Vidur `canary` with the shipped Mooncake trace, `vllm_v1`
scheduler, prefix caching and `sticky_lor` routing:

```
vidur/scheduler/replica_scheduler/vllm_v1_replica_scheduler.py:170
AssertionError: num_new_tokens should be greater than 0 but got -24844
```

I had paired the trace with `meta-llama/Llama-2-7b-hf`, whose `max_model_len` is
**4 096**. `measured` distribution of the shipped Mooncake trace: median
**7 767** tokens, p95 **40 568**, max **127 039**. Only 3 575 of 12 031 rows fit
a 4 k context.

Recording it prominently rather than quietly re-running, for three reasons:

- **It is my error, not a Vidur defect**, and the report would be dishonest if
  it read as the latter.
- It exposes something real anyway: **no model config `canary` ships has a
  context window large enough for Mooncake's p95 request** (largest is 32 768).
  `main`'s README avoids the problem by using the file as a *length* generator
  with an explicit 16 384-token clip — which throws away the block hashes, and
  therefore cannot serve RQ1. So "canary ships our primary trace" is true but
  came with a condition I had not checked.
- Vidur fails **late and uninformatively**: nothing validates the trace against
  `max_model_len` at start-up, so an obvious misconfiguration burned 18 minutes
  of simulation and produced a message naming neither the trace nor the model.

Carried into M2/M4 as work: running Mooncake at native lengths needs either a
long-context model config *with matching profiling data*, or a documented
filtering/scaling policy. That choice changes the prefix-sharing structure RQ1
measures, so it is a research decision, not a config detail. It compounds
falsifier F4.

Re-ran on a 512-request subset with ≤ 4 096 total tokens (420 distinct
sessions, 633 s of arrivals), reusing the already-fitted predictor cache.

### Two defects found in Vidur `canary`

Recorded because we are about to depend on this branch and its README warns of
"sharp edges".

1. `vidur/kv_cache/utils.py` defines `hash_block_tokens(hash_function,
   parent_block_hash, curr_block_token_ids)` — three parameters — and
   `hash_request_tokens` calls it with **four**, passing `req_extra_keys`. That
   path only runs when a request has no externally supplied `block_hash_ids`; a
   `TODO` in the same file confirms the authors supply hashes via trace files.
   I did not leave this as a hypothesis — I executed that path in the installed
   venv (`measured`): `TypeError: hash_block_tokens() takes 3 positional
   arguments but 4 were given`. Consequence for M2: our synthetic φ generator
   must emit block hashes itself rather than relying on Vidur to hash token ids,
   or we patch the one-line call.
2. `TolerantStickyLOPUncachedGlobalScheduler._cached_prefill_length_map` memoises
   `(request.id, replica_id) -> cached_prefill_length` and never prunes it. It
   is both an unbounded dict and a staleness hazard — the cached value is not
   invalidated when the replica's cache changes between estimate and dispatch.

### What the spike bought us for free, and what must not be trusted

Vidur `canary` ships `data/processed_traces/mooncake_conversation_trace.csv` —
80 MB, **12 031 requests**, with `arrived_at, num_prefill_tokens,
num_decode_tokens, block_hash_ids, block_size, session_id`. Mooncake is our
**primary** trace and this is most of the M2 loader.

It is `assumption`, not fact, that this is a faithful reduction of the upstream
Mooncake trace. Adopting a third party's preprocessing of the very structure
RQ1 measures would be exactly the kind of unexamined dependency this project
exists to avoid. **Re-deriving it from upstream is falsifier F4** and is M2 work.

### Decision

**Extend Vidur, branch `canary`, pinned at `25e0082`.** Recorded as **D-006**,
superseding D-005. Rationale, costs, rejected alternatives and **six** dated
falsifiers: `docs/spike/recommendation.md`. (Said "five" until 2026-09-10; F6
was added at the end of the spike and this sentence was not updated with it.)

The decision was **not** made on requirement counts — LLMServingSim scores more
PASSes (4 vs 3). It was made on a weighting stated explicitly in
`requirements-matrix.md` §4: R2 is the independent variable of the whole study
and R5 is the major result, and those are the two Vidur handles well and
LLMServingSim does not.

Honest statement of what we give up: LLMServingSim does heterogeneity (R4)
today and we will spend an estimated 3–5 days building it; and its published
per-request agreement with real vLLM (+0.6 % TTFT, +0.2 % TPOT on the matched
configuration, with a strict token-id replay harness) is better evidence than
anything Vidur `canary` currently offers. We are adopting **its E8 validation
methodology** even though we are rejecting the simulator.

### Not done, deliberately

No B1/B2/B3/B4. No simulator code. No vendoring. No trace downloads. No
Kubernetes. No vLLM. **No experimental measurements exist.** Every number in
this entry is an install or run *timing*, labelled `measured`.

**Next.** Stopped per the milestone protocol; awaiting explicit approval to
close M1 and begin M2.

---

## 2026-09-10 — M1 closed after user review; six corrections applied

**Week 2, day 1.** The user reviewed the completed M1 report before approving it
and returned six corrections. Recording them here in full, because five of the
six are cases where **the review caught something the assistant did not**, and
that is the most useful kind of entry this notebook can hold.

### What the review caught

1. **Four documentation inconsistencies** I had listed myself but not fixed
   (stale "remote synced" text, undercounted run totals, "five falsifiers" where
   there are six, a 57 s vs 32 s predictor-tax mismatch). Fixed.

2. **The throughput ratio was not a controlled comparison.** I had written that
   ~5.5× was "like-for-like, both with prefix caching". The user's objection:
   *enabling prefix caching in both does not make their workloads equivalent.*
   Correct. The two runs differ in trace, replica count, scheduler and cache
   topology. This is the second time I got this number's framing wrong — first
   ~60× from an unfair baseline, then a false claim of control. The generalisable
   error: **matching the one variable I happened to be thinking about, then
   treating the rest as equal.** Now described as `indicative`.

3. **Effort arithmetic.** The user computed 13–22 d from my own rows against my
   stated 13.5–22.5 d. The gap was a stale 0.5 d on R8. Re-checking run 4b's
   output settled it: `canary` already emits `replica`, `request_arrived_at` and
   `request_num_prefill_tokens_cached`, so R8 costs **0 d** on the branch we
   chose. Total corrected to **13–22 d**, with policy work and F6 explicitly
   listed as additional.

4. **F1 could not be checked when I said it could.** I dated F1 "end of M4" while
   assigning R4 to M7 and never said how. Now resolved by defining a bounded
   1-day probe (`recommendation.md` §5a) that is deliberately *not* the
   implementation — three steps, a pass/fail rule, and a throwaway patch that is
   discarded rather than merged.

5. **The tuning-bias claim was overstated.** I had written that using upstream's
   cache-aware router means "we cannot be accused of tuning the treatment to
   win". That is wrong twice over: it assumes upstream's policy *is* our B3
   (unverified), and it ignores that **we still choose the parameter values**.
   Starting from upstream code reduces authorship bias; it does nothing about
   tuning bias. The fix names two pieces of work that were previously invisible:
   a B3-equivalence check (M6) and a symmetric tuning protocol (M5/M8).

6. **I conflated two different scope reductions.** "Drop the third heterogeneous
   mix" is sanctioned by the frozen cut-if-behind register. "Drop heterogeneity"
   deletes RQ2 and E3. I had written the F1 fallback as though the register
   covered both. It does not, and any change to RQ2/E3 needs user approval.

### How the corrections were recorded

D-006 is an **accepted** decision, so its text was not edited. A pointer line was
added to its header and the substance went into a new dated entry, **D-007 —
Clarifications and partial corrections to D-006** (C1–C5). The supporting
evidence files under `docs/spike/` *were* edited directly — they are evidence,
not decisions — with each correction dated inline so a reader can see what
changed and when.

### The pattern worth carrying

Four of the six corrections are the same failure mode: **a claim stated more
strongly than the evidence supported, in the direction that favoured the
conclusion I had already reached.** The 60× ratio, the "like-for-like" framing,
the tuning-bias claim, and the scope conflation all flattered the recommendation.
None of them changed the decision — which is itself worth noting, because it
means the overclaiming was unnecessary as well as wrong.

No new benchmarks were run to strengthen the recommendation; the user explicitly
ruled that out, and it would have been the wrong instinct anyway.

**M1 is closed.** M2 begins.

---

## 2026-09-10 — M2: vendoring, schema, three loaders, and a generator that lied

**Week 2.** M1 closed. M2 built to its acceptance criteria in one session, with
one open decision handed back to the user.

### Vendoring

Vidur `canary` extracted at `25e0082` with `git archive`, so the tree is provably
that commit rather than a copy of a working directory that might have drifted.
**1.4 MB of code vendored; 584 MB of `data/` deliberately not** — 503 MB of that
is profiling CSVs, which do not belong in a public repository backing an academic
application. A SHA-pinned `fetch_vidur_data.sh` retrieves them from the same
commit, so the pin covers the excluded files exactly as much as the included ones.

A tree checksum sits in `VENDOR_TREE_SHA256`. It earned its keep within the hour
— see the cwd mistake below.

### The generator that reported a rate it could not produce

The synthetic phi generator's first construction kept a pool of sessions and
inherited `k = round(phi * n)` leading blocks from a randomly chosen one, clamped
to that session's chain length. It looked right. The measurement said otherwise:

| nominal phi | realised (first construction) |
|---|---|
| 0.25 | 0.2514 |
| 0.50 | 0.4524 |
| 0.75 | 0.6092 |
| **0.90** | **0.6845** |

The tests caught it because I had asserted `measured > phi - 0.12`, and 0.685 for
a nominal 0.9 fails that. My first instinct was that the tolerance was too tight.
It was not — the generator was wrong.

Instrumenting the loop found it: sessions had a **mean chain length of 5 blocks**,
and **40 % of requests** could not find a session long enough to inherit from.
The cause was that each request *replaced* its session's chain rather than
extending it, so a chain was only ever as long as its last request (U[2,16]), and
selecting long chains consumed them.

The fix was to model what actually produces prefix sharing in real serving: a
**multi-turn conversation**, where turn *t*'s prompt contains everything said so
far. Chains only grow; each turn appends `max(1, round(L*(1-phi)/phi))` new
blocks, which makes per-request sharing `L/(L+new) ≈ phi` by construction. A
session retires when its chain would exceed the cap.

| nominal phi | realised (now) | gap |
|---|---|---|
| 0.00 | 0.0000 | 0.0000 |
| 0.25 | 0.2360 | +0.0140 |
| 0.50 | 0.4908 | +0.0092 |
| 0.75 | 0.7413 | +0.0087 |
| 0.90 | 0.8805 | +0.0195 |

Monotonic, within 0.02 throughout, and still slightly below nominal — as it must
be, since every session's opening turn inherits nothing.

**Why this entry matters more than the numbers.** `PROJECT_SPEC.md` §7 says
nominal phi may not be reported as if it were measured. Had I not measured, I
would have shipped a "phi = 0.9" workload that actually shares 0.68 — and E2, the
experiment that locates the *threshold* at which cache-aware routing starts to
pay, would have had its x-axis quietly compressed at exactly the end where the
effect is supposed to appear. The rule is not bureaucratic. It caught a real one.

### F4 — the shipped Mooncake CSV: verdict, does not fire

Compared our re-derivation against upstream `kvcache-ai/Mooncake` @ `eeaca79`.
Record counts, decode lengths and arrival times match exactly. Block size is
**512**, established empirically (100 % of records; 16/64/128/256/1024 match
none). Realised sharing: upstream 36.64 %, shipped CSV 35.88 % — **−0.77 pp**, so
the re-blocking to 16 tokens preserves the structure.

Three modifications we decline to adopt:

1. **Every prompt is +512 tokens** in the shipped CSV, uniformly, all 12 031 rows.
   Not block-padding, not `len(hash_ids)*512`. Reason not recoverable from source.
   ~7 % inflation on the median request.
2. **`session_id` is invented.** Upstream has none. The shipped CSV's 7 417
   sessions capture the structure well (87 % of reuse falls within them) — but our
   B3 and Vidur's `sticky_lor` *route on this field*. Adopting it would mean
   routing on someone else's inferred grouping while reporting results about
   Mooncake. Our loader sets it `None`, and deriving sessions ourselves becomes M6
   work.
3. **Hash chain extended over decode tokens.** Defensible for a cache model, wrong
   for a router input: a router at admission cannot know what will be generated.

F4 is retired by removing the dependency, not by trusting it.

### F6 — I was wrong in M1 about what the limit was

M1 concluded that no shipped model configuration has a context window large
enough for Mooncake. That was true of the **declared `max_model_len` values** and
**wrong about the profiling data**, which is what actually determines whether the
timing model can be trusted.

Surveying all 22 shipped profile bundles: `Meta-Llama-3-8B` and `-70B` on a100
and h100 have `max_kv_cache_size = 262 112` tokens — past Mooncake's 126 527-token
maximum. Every other model stops at 4 032. The M1 spike used `Llama-2-7b-hf`,
which is in the second group, and I generalised from one model to all of them.

`prefill_chunk_size` (4 096 / 8 192) and `kv_cache_size` (262 112) are different
quantities: with chunked prefill, a long prompt is processed in bounded chunks
while the *KV cache* is what grows with context. I conflated them in M1.

So Option D — run at native lengths on Llama-3-8B — distorts the workload by
**0 pp**, against +1.05 pp for the best truncation and +20 pp for filtering at
4 k. Recommended, with the honest caveat that the predictor-fit cost at extended
KV is unmeasured and could fire F2. Presented for the user's decision; nothing
adopted.

### A mistake worth recording: cwd drift

Three M2 documents were written into `.spike/vidur-canary/docs/` instead of
`docs/`, because a heredoc inherited a `cd` from an earlier command. Caught by
`git status` showing them absent, not by noticing at the time. Moved, and the
vendored tree checksum re-verified as intact.

The lesson is small but real: **long sessions accumulate shell state, and
`cat > relative/path` trusts it.** Absolute paths, or verify placement.

### Not done, deliberately

No simulator modifications. No routing policies. No experimental sweeps. No vLLM
calibration. No Kubernetes. The vendored tree is untouched and checksum-verified.
Validation was limited to what establishes loader and generator correctness: 31
tests.

---

## 2026-09-10 — F6 rev 2: a user audit finds six errors in my own analysis

The user reviewed the F6 recommendation and returned six objections. **All six
were correct.** The recommendation changed as a result. Recording each, because
the pattern across them is more instructive than any single one.

### 1. I proposed a hypothetical model without noticing

Released Meta-Llama-3-8B has an **8 192**-token context. "Raise `max_model_len`
to 131 072" would simulate a model that does not exist — precisely the kind of
unlabelled fabrication `PROJECT_SPEC.md` §11 exists to prevent, and I walked into
it while writing a document about being careful.

There *is* a legitimate model behind the same numbers: **Llama-3.1-8B** is real,
131 072 context, and architecturally identical — 32 layers, 4 096 hidden, 32 q
heads, 8 kv heads, 14 336 intermediate, rope_theta 500 000. The only difference
is RoPE scaling, which affects output quality, not FLOPs or KV bytes. So the
corrected proposal is a **declared substitution**, not a raised constant.

### 2. I quoted a column maximum and called it coverage

Rev 1 said the profile reaches 262 112 tokens. Tracing `kv_cache_size` through
`AttentionInput.is_valid` and `attention_wrapper.py` establishes it is
**per-sequence processed context** (not aggregate batch tokens — that is a
separate quantity, `batch_size * (kv + chunk)`, used only to bound the sweep).

But the joint coverage is the thing that mattered, and it is split by phase:

| Phase | batch | chunk | kv | joint |
|---|---|---|---|---|
| prefill | 1 | ≤4 096 / 8 192 | ≤262 112 | chunk+kv reaches 262 144 |
| **decode** | 1…512 complete | 0 | **≤65 536** | dense, 644 kv values per batch size |

**The binding ceiling is 65 536, set by decode.** My 262 112 was prefill-only. I
took a max over a column that mixes two phases with different coverage.

### 3. The extrapolation problem I had not considered

Vidur's *prediction* grid runs to `prediction_max_tokens_per_request = 256*1024`
by default, so it will emit predictions past 65 536 without complaint. But the
decode *training data* stops there, and a random forest cannot extrapolate — it
flat-lines at the nearest leaf. Decode attention cost grows with context, so
those predictions would systematically **under-estimate** the longest requests,
which are the expensive ones. 2.14 % of Mooncake sits in that region.

### 4. Option C's headline number was my own artifact

I scaled token counts but kept `block_size = 512` and truncated each hash chain.
That deletes unique tail blocks while keeping shared heads — the ratio inflates
mechanically. Scaling **consistently** (tokens *and* block size), sharing is
**exactly invariant: 38.19 %, +0.00 pp at every factor.** My reported +38.13 pp
was entirely an invalid transformation.

C is still rejected — but for the right reason now (§5 below), not the fake one.

### 5. "Long requests share the most" — backwards

I asserted this as the mechanism. Measured by length quintile, per-request reuse:
**Q1 shortest 81.84 %**, then 44.41, 37.93, 37.21, 38.33. Short requests share
*most*. The real mechanism is **head/tail**: reuse concentrates in prompt heads
(every request's first hash id is the same shared block), and a short request is
almost all head. Both A and B inflate the ratio by preserving heads and
discarding tails — the same structural reason, not the one I gave.

### 6. Ranking by Δ-ratio was the wrong instrument entirely

This is the deepest of the six, and the user reached it from a smaller
observation (that B is not uniformly better than A — true, the ordering flips at
8 192 and 16 384).

Adding absolute counts shows why the ratio misleads: **A @8 192 has the smaller
ratio change (+4.16 pp vs +6.36) while discarding 86.5 % of all prefix blocks**
against B's 56.8 %. A ratio can look stable precisely because its numerator and
denominator fell together. I had built a whole recommendation on a statistic that
hides the thing it is supposed to measure.

### And the distinction underneath all of it

"0 pp distortion" establishes only that the trace was unchanged. It says nothing
about whether the simulator can *price* that trace. Consistent scaling preserves
sharing exactly and destroys timing validity completely. Preservation and
validity are independent axes, and rev 1 collapsed them.

### Corrected recommendation

**D′ — Llama-3.1-8B-class model (declared substitution, shipped profile) +
truncate at 65 536.** Costs +0.44 pp and 4.2 % of blocks; keeps 96.9 % of all
reuse; puts **every** request inside profiled data for both phases; needs no new
GPU profiling. Native remains better *if* decode profiling above 65 536 is added
later, which is M3 GPU work — and truncation is reversible, so choosing it now
forecloses nothing.

### On the smoke-test exception

The user authorised one with limits. **I did not use it**, because it is not
usable within those limits: any run on a new `(model, device)` pair must first fit
the predictor (`estimate` 11–14 h from a 2.45× larger training set), which is the
full fit that was excluded. There is no cached artefact and no partial-fit mode
that answers anything. I ran Vidur's `MemoryPlanner` instead — seconds, and it
produced the KV feasibility numbers (TP=1 holds **3** maximum-length sequences).
Saying "the authorised test would not answer the question" is more useful than
burning the allowance to look thorough.

### The pattern

Five of the six errors share a shape: **I reached for the summary statistic that
was easiest to compute, then reasoned about the system as though the statistic
were the system.** A column max stood in for joint coverage; a ratio stood in for
structure; a scaling transformation stood in for a scaled workload. The M1 review
found the same shape in the throughput ratio. That is now twice, and it is worth
naming as a standing failure mode rather than treating each instance as
independent.
