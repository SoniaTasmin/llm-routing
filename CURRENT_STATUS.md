# CURRENT_STATUS.md — What Is Happening RIGHT NOW

**Last updated:** 2026-09-10
**Project week:** Week 2 of 12
**Branch:** `main` · **Remote:** `SoniaTasmin/llm-routing` (public)

---

## Milestone state

| Milestone | Title | State |
|-----------|-------|-------|
| **M0** | Research specification (framing, RQs, policies, experiments, stats) | **APPROVED AND FROZEN** |
| **M1** | Simulator-base spike (Vidur vs LLMServingSim vs small custom DES) | **DONE (approved 2026-09-10)** |
| **M2** | Trace loaders + unified format + synthetic phi generator | **IN PROGRESS** |
| M3+ | everything else | NOT STARTED — do not implement |

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

## M2 — in progress

**Objective.** One unified workload record format, three loaders that emit it,
and a synthetic generator whose realised prefix sharing is *measured* rather than
assumed — so every later milestone consumes one schema regardless of source.

Approved scope: vendor Vidur `canary` at the D-006 SHA · define the unified
schema · re-derive Mooncake from upstream and check it against the shipped CSV
(**F4**) · Azure 2023 cache-blind control loader (**D-004**) · synthetic phi
generator with externally supplied block hashes and measured realised sharing ·
investigate Mooncake's context-length constraint (**F6**) and bring options back
for a decision.

**Out of scope for M2, explicitly:** simulator modifications · routing policies
B1/B2/B3/B4 · experimental sweeps · vLLM calibration · Kubernetes · any change
to RQ2/E3 scope. Validation is limited to establishing loader and generator
correctness.

---

## Open decision awaiting the user

**F6 — Mooncake's context length.** The shipped Mooncake trace has a median
request of 7 767 tokens, p95 **40 568**, max **127 039**. The largest context
window any model config Vidur ships is **32 768**; the models with profiling data
we would realistically use are **4 096**. So the primary trace does not fit the
simulator at native lengths.

Whatever we do about that — filter, scale, or add a long-context configuration —
**changes the prefix-sharing structure RQ1 measures**, so it is a research
decision, not a configuration detail. Options, consequences and a recommendation
are being prepared; **no option will be adopted before the user decides.**
Independent M2 work continues meanwhile.

---

## Known blockers / open items

| Item | Status |
|------|--------|
| GitHub remote | M1 corrections + closure pushed 2026-09-10; remote verified equal to local `HEAD` |
| Git identity | repo-local: Sonia Tasmin / stasmin10@gmail.com, so the office GitLab identity is never used |
| `.spike/` working area | git-ignored; holds both M1 candidate clones + venvs + the ASTRA-Sim build. Recreate from `REPRODUCE.md` §3a; safe to delete |
| Mooncake trace | re-derivation from upstream is **M2 work in progress** (F4) |
| Azure LLM inference traces | loader is **M2 work in progress** |
| vLLM testbed / GPU access | not yet arranged (needed by M3 and M11) |

## Risks carried out of M1

| # | Risk | Owner milestone |
|---|------|-----------------|
| F1 | R4 heterogeneity may exceed 8 engineer-days — checked by the bounded probe in `recommendation.md` §5a | M4 (probe) / M7 (implementation) |
| F2 | Vidur's per-process predictor tax (`measured` 32–115 s) and 4.02 GB peak RSS may make the E1 fleet sweep infeasible on this hardware | M4 |
| F3 | `canary`'s prefix cache may not faithfully port vLLM's block-pool semantics | M4 |
| F4 | The shipped Mooncake CSV may not be re-derivable from upstream | **M2 — active** |
| F5 | `canary` is unmerged, last commit 2025-06-25, and will not be maintained | mitigated by vendoring at a pinned SHA |
| F6 | Mooncake at native lengths exceeds every model context Vidur ships | **M2 — active, awaiting user decision** |

Full statement of each: `docs/spike/recommendation.md` §5.

---

## Standing reminders

- Headline comparison is always **against B2-tok**, never against Round Robin.
- Primary outcome is **minimum fleet cost at fixed SLO**.
- Never fabricate measurements; label every number
  `measured` / `hypothesis` / `estimate` / `assumption`.
- Any change to RQ2 or primary experimental scope requires **explicit user
  approval** (D-007 C5).
