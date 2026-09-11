# docs/m3-calibration-plan.md — M3 run plan, for budget approval

**Date:** 2026-09-10 · **Milestone:** M3 · **Status: PREPARED, NOT RUN.**
**No GPU rented, no charges incurred, no predictor fit launched.**

---

## 1. What M3 is for, in plain language

Everything this project concludes about latency, cost and SLO attainment comes
out of a simulator, and the simulator's numbers are only as good as its timing
model. Vidur does not guess at timing: it *measures* how long each operation
(attention, MLP, layernorm…) takes on a real GPU at many shapes, fits a model to
those measurements, and replays that model on CPU. **M3 is where we obtain those
measurements for the hardware and model this study will actually simulate.**

Right now we are borrowing. D-008 has us simulating a Llama-3.1-8B-class model
using the `Meta-Llama-3-8B` profile Vidur ships, as an **unvalidated proxy**, and
truncating Mooncake to 65 536 tokens because that profile's decode data stops
there. M3 is where borrowing either becomes justified or gets replaced.

### Acceptance criteria (as written into `MILESTONES.md`)

1. A plan with exact GPU, model, software versions and a bounded cost — **this
   document** — approved before any spend.
2. Vidur's profiler run on the chosen `(model, device, TP)`, producing
   `attention.csv` and `mlp.csv` in the shipped schema.
3. A short real-vLLM replay on the same hardware, for comparison.
4. A written verdict on gate **G3**.
5. Everything reproducible from `REPRODUCE.md`.

---

## 2. A finding that re-scopes M3 before we spend anything

**Vidur's profiler loads no model weights.** `vidur/profiling/attention/attention_wrapper.py`
builds tensors from config shapes; `mlp_impl.py` uses `torch.randn_like`; the
imports include `sarathi.model_executor.weight_utils.initialize_dummy_weights`.
Nothing reads a checkpoint.

Three consequences, and the third is the important one:

1. **No HuggingFace access or gated-model approval is needed**, and no ~16 GB
   download. Cheaper and simpler than assumed.
2. The **sweep grid** is a function of shape, so it is deterministic: the same
   config yields the same set of `(batch, kv, chunk)` points. **The measured
   times are not.** They are wall-clock kernel benchmarks and carry the usual
   run-to-run variation — clock and power state, thermals, driver and library
   version, co-tenancy. *(Corrected 2026-09-11: an earlier revision called
   profiling "deterministic" without qualification, which conflated the grid
   with the measurements taken over it.)*
3. **Re-profiling under the name "Llama-3.1-8B" would sweep the same grid as
   `Meta-Llama-3-8B`**, because the two configs are shape-identical (32 layers,
   4 096 hidden, 32 q heads, 8 kv heads, 14 336 intermediate). The profiler has
   no way to distinguish them — it never reads a checkpoint, only shapes.
   *(Corrected: an earlier revision said the data would be "identical" and
   "byte-identical". Wrong. The **sampled points** would coincide; the **timing
   values** would differ by measurement noise and by whatever hardware and
   software stack produced them.)*

**So gate G3 — "does the shipped profile represent real Llama-3.1-8B?" — cannot
be closed by re-running Vidur's profiler**, because a profiler that never loads
weights cannot distinguish two models with identical shapes. It is answerable only by comparing
against **real vLLM serving real Llama-3.1-8B weights end-to-end**, which is E8
at M11. Recording this now prevents M3 from buying an answer it cannot deliver.

### What M3 can therefore genuinely deliver

| Deliverable | Value | Gate |
|---|---|---|
| **A. Reproduce** the shipped profile on our own GPU and compare | Confirms the shipped data is reproducible and our toolchain is sound. Guards against a silently corrupt or mis-generated vendored profile | supports G1 |
| **B. Extend decode coverage** from 65 536 to 131 072 tokens | **Removes the reason D′ exists.** It is *necessary* for running native Mooncake, not *sufficient*: retiring D′ would additionally need G4 (block-size mapping) resolved, G1 (the fit and run actually completing at that context) demonstrated, and a recorded decision superseding D-008 | **unblocks** reconsidering D′ |
| **C. Stand up the real-vLLM replay harness** | The only route to G3; also the E8 methodology we said we would borrow from LLMServingSim | **G3**, completed at M11 |

**B is the headline.** D-008 accepted a +0.44 pp distortion *only* because decode
profiling stopped at 65 536. Extending it removes the compromise rather than
managing it.

---

## 3. Exact requirements

### Hardware

| | Requirement | Note |
|---|---|---|
| GPU | **1 × A100 80 GB** (or H100 80 GB) | **One GPU is sufficient even for TP > 1** compute profiling — the profiler shards shapes, it does not need the devices (`docs/profiling.md`). Multi-GPU is needed only for *collectives* profiling, which we do not need at TP=1 |
| Host RAM | ≥ 32 GB | |
| Disk | ~40 GB | ~15 GB for CUDA/PyTorch/FlashInfer, remainder for outputs |

Our target replica configuration is **TP=1**, so no network/collectives
profiling is required. Note also that **a100 TP=2 and TP=4 have no shipped
profiling data at all** — if we ever want those, they are additional runs.

### Software

| Component | Version / source |
|---|---|
| Python | 3.10 |
| **`sarathi-serve`** | branch **`vidur`**, `github.com/microsoft/sarathi-serve` — a hard dependency: the profiler imports `sarathi.config`, `sarathi.model_executor.*` |
| Vidur | our vendored tree, `simulator/vendor/vidur` @ `25e0082` |
| Attention backend | **FlashInfer** (the profiler's default, and what the shipped data used) |
| CUDA / PyTorch | whatever `sarathi-serve`'s README pins — **to be recorded exactly at run time** |

### Model and parameters

| Parameter | Value | Why |
|---|---|---|
| model | `meta-llama/Meta-Llama-3-8B` | shape-identical to Llama-3.1-8B; no weights loaded |
| device label | `a100` | Vidur keys compute profiles by SKU only |
| `num_tensor_parallel_workers` | `1` | our target replica config |
| `block_size` | **16** | **forced** — Vidur filters training rows on it and every shipped profile is 16 (gate **G4**) |
| `max_chunk_size` | 4 096 | matches shipped a100 data |
| `max_seq_len` | pilot 32 768 → full **131 072** | the full value removes the coverage limit that forced D′ |
| `max_batch_size` | pilot 32 → full 512 | matches shipped coverage |

---

## 4. The bounded run

Two phases, because the pilot's **measured** throughput should size the full run
rather than a guess sizing the spend.

### Phase 1 — pilot (~1 hour billed)

`bash experiments/m3_calibration/run_profiling.sh pilot`

Reduced sweep (`max_seq_len 32768`, `max_batch 32`, TP=1). Establishes: that
`sarathi-serve` installs and the profiler runs; **rows per second**; that the
output passes `python -m workload.profile_audit_cli`; and that a reduced-range
profile of the *same* region agrees with the shipped data.

**Stop condition:** if the pilot fails or its throughput implies the full run
exceeds the cap, we stop and re-plan rather than spending into it.

### Phase 2 — full profile (estimated 3–8 hours billed)

`bash experiments/m3_calibration/run_profiling.sh full`

`max_seq_len 131072`, `max_batch 512`, TP=1 — the run that produces deliverable
**B**.

`estimate`, low confidence: the shipped a100 TP=1 profile holds **65 268** rows;
extending decode to 131 072 roughly doubles the decode KV range, so **~110 000
rows**. Wall time is unknown until the pilot measures it — that is precisely why
there is a pilot, and why no point estimate is offered here. *(The last time I
extrapolated a fit cost from row counts alone, the estimate was wrong by a factor
I could not bound; see `NOTEBOOK.md`, F6 rev 4.)*

### Phase 3 — real-vLLM replay (~2 hours billed) — **optional at M3**

The only work needing **real weights** (~16 GB, gated Llama access) and a
served model. Produces the reference trace E8 compares against at M11. Can be
deferred to M11 if you prefer to keep M3's spend minimal.

### Cost

Prices are `estimate`s from on-demand cloud rates; Vidur's own analyzer uses
$2.21/hr for A100 and $4.25/hr for H100 (CoreWeave, 2024).

| Phase | Hours | @ ~$2/hr |
|---|---|---|
| 1 — pilot | 1 | ~$2 |
| 2 — full profile | 3–8 | ~$6–16 |
| 3 — vLLM replay (optional) | 2 | ~$4 |
| setup / contingency | 2 | ~$4 |
| **Requested cap** | | **$40** |

**Hard stop at the cap.** Phase 2 does not start until phase 1's numbers are
reviewed.

---

## 5. What is already done, without a GPU

| Artefact | Status |
|---|---|
| `experiments/m3_calibration/run_profiling.sh` | two-phase runbook, parameters fixed, syntax-checked |
| `src/workload/profile_audit.py` + `profile_audit_cli.py` | audits any profile for **loadability** (would Vidur's TP and `block_size` filters empty the frame?) and **per-phase joint coverage**, and answers "is an N-token request inside sampled coverage?" |
| `tests/test_profile_audit.py` | 6 tests pinning the auditor, including the two filter-emptying cases and the rows-vs-distinct-pairs distinction |
| Baseline audit of the shipped profile | recorded, reproducible on CPU |

The auditor exists because three revisions of the F6 analysis carried wrong
coverage numbers derived by hand. It is the standing check from `NOTEBOOK.md`,
turned into code and CI rather than an intention.

Run it now, no GPU:

```bash
PYTHONPATH=src python -m workload.profile_audit_cli \
  .spike/vidur-canary/data/profiling/compute/a100/meta-llama/Meta-Llama-3-8B/attention.csv \
  --tp 1 --block-size 16 --require-context 65536
```

---

## 6. How M3 connects to M4 and M11

```
   M3 calibration                M4 feasibility               M11 fidelity
   ──────────────                ──────────────               ────────────
   A. reproduce profile  ───────► G1 predictor fit            
   B. extend decode      ───────► G2 no extrapolation  ─────► E8 error band
      to 131 072                     needed at all
                                  G4 block-size mapping
   C. vLLM replay harness ─────────────────────────────────► G3 proxy verdict
```

**M3 → M4.** M4 must fit Vidur's execution-time predictor and run end-to-end at
long context (G1), and we have **no defensible estimate** of that fit's cost —
withdrawn, because it could not be derived from the surviving M1 evidence. M3
produces the profile M4 fits, so its row count and structure directly determine
that cost. If M3 delivers **B**, gate **G2** (random-forest flat-lining outside
its training range) stops mattering for our workload, because nothing extrapolates
any more. **G4** (the 512→16 block-size mapping) is independent of M3 and stays
M4's problem either way.

**M3 → M11.** E8's whole purpose is a *measured* simulator-fidelity error band,
and `PROJECT_SPEC.md` §11's inconclusiveness rule makes that band the threshold
below which effects are reported as inconclusive. That band is only meaningful if
the simulator's timing model is the one being validated. M3 deliverable **C**
builds the replay harness; M11 runs the comparison and returns the verdict on
**G3**.

**If M3 is deferred**, the study still runs — on a borrowed, unvalidated profile,
with the D′ truncation **still in force**, and with E8 comparing real vLLM against
a timing model derived from someone else's measurements. That is the honest cost.

**Deferral does not make D′ permanent.** D-008 is provisional, the native trace is
preserved unmodified beside the variant, and the truncation is a one-line change
to the workload build. What deferral does is leave the *reason* for D′ standing.
Nothing about it hardens with time.

---

## 7. The decision requested

| | Option | Spend | Gets us |
|---|---|---|---|
| **1** | Pilot only | ~$2 | Toolchain proven, throughput measured, full-run cost known |
| **2** | **Pilot + full profile** *(recommended)* | **~$8–18** | **Retires the D′ truncation**; native Mooncake at 0 pp distortion |
| **3** | Pilot + full + vLLM replay | ~$12–22 | Above, plus the M11 reference trace captured early |
| **4** | Defer M3 | $0 | Proceed on the borrowed profile; D′ **remains in force and remains provisional**; G3 unresolved until M11 |

**Recommendation: option 2**, with the cap at **$40** and a hard stop after the
pilot for review. Phase 3 is better placed at M11, when the E8 comparison is
actually being built and we know what the reference trace must contain.
