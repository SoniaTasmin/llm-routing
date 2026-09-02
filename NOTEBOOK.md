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
cheap Sarathi scheduler with **no prefix cache** — different work. The
like-for-like figure, once Vidur `canary` ran with prefix caching on, is
**~0.18 s/request**, i.e. about **5.5×**. Corrected in all four spike documents.
Recording the error rather than the corrected number alone: I reached for the
fastest Vidur measurement I had instead of the comparable one, and it flattered
the option I was already leaning towards. `estimate`: a 20 000-request
LLMServingSim run is ~5.5 h, and E1 needs hundreds of runs — so the concern
survives, at a quarter of the drama.

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
superseding D-005. Rationale, costs, rejected alternatives and five dated
falsifiers: `docs/spike/recommendation.md`.

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
