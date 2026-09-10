# CURRENT_STATUS.md — What Is Happening RIGHT NOW

**Last updated:** 2026-09-10 (M2 approved; M3 preparation)
**Project week:** Week 2 of 12
**Branch:** `main` · **Remote:** `SoniaTasmin/llm-routing` (public)

---

## Milestone state

| Milestone | Title | State |
|-----------|-------|-------|
| **M0** | Research specification (framing, RQs, policies, experiments, stats) | **APPROVED AND FROZEN** |
| **M1** | Simulator-base spike (Vidur vs LLMServingSim vs small custom DES) | **DONE (approved 2026-09-10)** |
| **M2** | Trace loaders + unified format + synthetic phi generator | **DONE (approved 2026-09-10)** |
| **M3** | vLLM calibration | **PREPARATION IN PROGRESS** — no GPU work, awaiting budget approval |
| M4+ | everything else | NOT STARTED — do not implement |

---

## M1 — closed

The simulator-base spike ran 2026-09-01 → 2026-09-02. Both candidates were
installed and **actually run** (nine runs, seven usable). Outcome, recorded as
**D-006**:

> **Extend Vidur, branch `canary`, vendored and pinned at
> `25e0082dbbfb206fb0477c3ebbededa7ead78949`.**

Approved on 2026-09-10 **subject to six corrections**, all applied before
closure. Five of the six were things the user's review caught and the assistant
had not. Because D-006 was already accepted, its text was preserved and the
substance recorded as **D-007 — Clarifications and partial corrections to
D-006**:

| | Correction |
|---|---|
| C1 | The ~5.5× throughput ratio is **indicative across the configurations tested**, not a controlled like-for-like comparison. Prefix caching being on in both does not equalise their workloads. |
| C2 | Effort total corrected **13.5–22.5 d → 13–22 d** (stale 0.5 d on R8; `canary` already emits the needed columns). Policy work and the Mooncake context-length decision are **additional**. |
| C3 | Using an upstream router **reduces some implementation bias; it does not remove tuning bias.** B3-equivalence (M6) and a symmetric tuning protocol (M5/M8) are now named work. |
| C4 | **F1** is checked at M4 by a **bounded 1-day probe** (`recommendation.md` §5a); the full R4 implementation stays at **M7**. |
| C5 | **Dropping heterogeneity ≠ dropping the third fleet mix.** Any change to RQ2/E3 scope requires explicit user approval. |
| — | Four documentation inconsistencies fixed (stale remote-sync text, undercounted run totals, "five falsifiers", 57 s vs 32 s). |

Artefacts: `docs/spike/` (5 files), `DECISIONS.md` D-006 + D-007, `NOTEBOOK.md`.

---

## M2 — DONE (approved 2026-09-10)

**Objective.** One unified workload record format, three loaders that emit it,
and a synthetic generator whose realised prefix sharing is *measured* rather than
assumed — so every later milestone consumes one schema regardless of source.

**Delivered.**

| | Result |
|---|---|
| Vendored simulator | Vidur `canary` @ `25e0082`, extracted with `git archive`; MIT licence + provenance recorded; tree checksum verified. Code 1.4 MB; the 584 MB `data/` is fetched at the same SHA by `fetch_vidur_data.sh` |
| Schema v1.0 | `src/workload/schema.py` + `docs/workload-schema.md` |
| Mooncake | re-derived from `kvcache-ai/Mooncake` @ `eeaca79`; **12 031** requests; realised sharing **38.19 %** `measured` |
| Azure 2023 | conv **19 366** + code **8 819** requests, **cache-blind by construction** |
| Synthetic phi sweep | nominal 0/0.25/0.5/0.75/0.9 -> **measured** 0.0000/0.2360/0.4908/0.7413/0.8805 |
| Tests | **31 passing** — they caught a real generator defect |
| **F4** | **does not fire** — `docs/workload-mooncake-f4.md` |
| **F6** | options + recommendation prepared; **awaiting your decision** |

**Out of scope, and not done:** simulator modifications · routing policies
B1/B2/B3/B4 · experimental sweeps · vLLM calibration · Kubernetes · any change
to RQ2/E3 scope. The vendored tree is untouched and checksum-verified.

---

## Open decision awaiting the user

**M3 resource budget.** Plan prepared, nothing spent:
`docs/m3-calibration-plan.md`.

| | Option | Spend | Gets us |
|---|---|---|---|
| 1 | Pilot only | ~$2 | toolchain proven, throughput measured |
| **2** | **Pilot + full profile (recommended)** | **~$8–18** | **retires the D′ truncation** — native Mooncake at 0 pp distortion |
| 3 | + real-vLLM replay | ~$12–22 | above, plus the M11 reference trace early |
| 4 | Defer M3 | $0 | borrowed profile stands; D′ permanent; G3 open until M11 |

Requested cap **$40**, hard stop after the pilot for review.

**A finding that re-scoped M3 before any spend:** Vidur's profiler loads **no
model weights** (`initialize_dummy_weights`, `torch.randn_like`). So no gated
HuggingFace access and no 16 GB download are needed — but also, re-profiling
under the name "Llama-3.1-8B" would produce data **identical** to
`Meta-Llama-3-8B`, because the configs are shape-identical. **Gate G3 therefore
cannot be closed by Vidur's profiler at all**; only a real-vLLM comparison
closes it, at M11. M3's genuine value is instead extending decode coverage from
65 536 to 131 072 tokens, which would **retire the D′ truncation** rather than
manage it.

## Known blockers / open items

| Item | Status |
|------|--------|
| GitHub remote | **In sync as of 2026-09-10.** M1 (2 commits) and M2 (2 commits) pushed by the user; `git ls-remote origin refs/heads/main` returns `183fff9289d5fcf7965c40b66284bd88d676a5e3`, equal to local `HEAD`. The assistant cannot push from this machine — no credential helper, no SSH key, `gh` present but not authenticated. Pushes are manual until that changes. |
| Git identity | repo-local: Sonia Tasmin / stasmin10@gmail.com, so the office GitLab identity is never used |
| `.spike/` working area | git-ignored; holds both M1 candidate clones + venvs + the ASTRA-Sim build. Recreate from `REPRODUCE.md` §3a; safe to delete |
| Mooncake trace | **re-derived** from upstream @ `eeaca79`; F4 retired |
| Azure LLM inference traces | **loaded** (conv + code), cache-blind by construction |
| vLLM testbed / GPU access | not yet arranged (needed by M3 and M11) |

## Risks carried out of M1

| # | Risk | Owner milestone |
|---|------|-----------------|
| F1 | R4 heterogeneity may exceed 8 engineer-days — checked by the bounded probe in `recommendation.md` §5a | M4 (probe) / M7 (implementation) |
| F2 | Vidur's per-process predictor tax (`measured` 32–115 s) and 4.02 GB peak RSS may make the E1 fleet sweep infeasible on this hardware | M4 |
| F3 | `canary`'s prefix cache may not faithfully port vLLM's block-pool semantics | M4 |
| F4 | The shipped Mooncake CSV may not be re-derivable from upstream | **RETIRED 2026-09-10** — does not fire; we use our own re-derivation |
| F5 | `canary` is unmerged, last commit 2025-06-25, and will not be maintained | mitigated by vendoring at a pinned SHA |
| F6 | Mooncake at native lengths exceeds every model context Vidur ships | **narrowed** — Llama-3 profiles cover 262 112 tokens; awaiting user decision on Option D |

Full statement of each: `docs/spike/recommendation.md` §5.

---

## Standing reminders

- Headline comparison is always **against B2-tok**, never against Round Robin.
- Primary outcome is **minimum fleet cost at fixed SLO**.
- Never fabricate measurements; label every number
  `measured` / `hypothesis` / `estimate` / `assumption`.
- Any change to RQ2 or primary experimental scope requires **explicit user
  approval** (D-007 C5).
