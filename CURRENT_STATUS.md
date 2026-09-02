# CURRENT_STATUS.md — What Is Happening RIGHT NOW

**Last updated:** 2026-09-02
**Project week:** Week 1 of 12
**Branch:** `main` · **Remote:** `SoniaTasmin/llm-routing` (public), synced

---

## Milestone state

| Milestone | Title | State |
|-----------|-------|-------|
| **M0** | Research specification (framing, RQs, policies, experiments, stats) | **APPROVED AND FROZEN** |
| **M1** | Simulator-base spike (Vidur vs LLMServingSim vs small custom DES) | **WORK COMPLETE — AWAITING APPROVAL** |
| M2+ | everything else | NOT STARTED — do not implement |

---

## What was just done

**The M1 simulator-base spike ran, 2026-09-01 → 2026-09-02.**

Both candidates were obtained, installed and **actually run** — neither had to be
judged from its README:

- **Vidur** `main` @ `abae7f63` — 3 runs (4 replicas × 128 requests; an identical
  repeat to test determinism; 8 replicas × 2048 requests).
- **Vidur** `canary` @ `25e0082` — 2 runs on the shipped Mooncake trace with
  prefix caching and session-sticky routing. The first **crashed** (my
  misconfiguration: a 4 096-token model against a trace whose median request is
  7 767 tokens); the second, on a fitting 512-request subset, completed with
  32.69 % of prefill tokens served from cache and per-request output carrying
  the replica id and per-request cache hits. Scored **separately from `main`**,
  because `main`'s own README (line 145) sends users needing prefix caching and
  routing policies to `canary`. For this project they are different simulators.
- **LLMServingSim 2.0** @ `a4053bc` — 2 runs (single instance; and two instances
  with a shared CPU prefix pool), after a Docker image, 10 git submodule paths and a
  C++ ASTRA-Sim build.

Both were scored against R1–R8 with file/line evidence, CLI probes and run
output. Extension effort was estimated in engineer-days for every failed **and
partial** requirement, with the basis for each estimate stated.

Artefacts: `docs/spike/requirements-matrix.md`, `vidur-notes.md`,
`llmservingsim-notes.md`, `recommendation.md`. Dead ends in `NOTEBOOK.md`.
Decision in `DECISIONS.md` as **D-006**.

### The decision

> **Extend Vidur, on the `canary` branch, vendored and pinned at
> `25e0082dbbfb206fb0477c3ebbededa7ead78949`.**

The short version of why: R2 (pluggable routing) *is* the object of study and R5
(replica failure) *is* the major result E4/H4. Vidur `canary` gives us a clean
router abstraction with the completion callbacks B2-tok needs, and puts failure
injection inside one Python event loop. LLMServingSim wins R4 (heterogeneity)
outright and has far better published vLLM validation, but its routing hook
never receives the request, it has no cost model at all — and cost is our
**primary** outcome — and replica failure there crosses a process boundary into
a C++ backend whose NPU topology is fixed before the run starts.

**Nothing was implemented.** No policies, no simulator code, no vendoring, no
traces downloaded, no Kubernetes, no vLLM. **No experimental measurements of any
kind exist.** The only measured numbers in the repository are installation and
run *timings* of the two candidate simulators, and they are labelled as such.

---

## What is happening right now

**Waiting for explicit user approval to close M1 and begin M2.**

Per the milestone protocol, the assistant has STOPPED.

---

## Immediate next step (only after approval)

Begin **M2 — trace loaders + unified format + synthetic phi generator** (Week 2):

1. Vendor Vidur `canary` at `25e0082` into `simulator/`, with provenance and MIT
   licence recorded. (Vendoring is M2 work; M1 was a decision, not an
   implementation.)
2. Unified workload record format.
3. Mooncake loader — and **re-derive** `mooncake_conversation_trace.csv` from the
   upstream trace rather than adopting the copy `canary` ships. This is
   falsifier **F4** in `docs/spike/recommendation.md`.
4. Azure 2023 loader (cache-blind control).
5. Synthetic generator, phi in {0, 0.25, 0.5, 0.75, 0.9}, **measuring** the
   realised prefix-sharing rate rather than assuming nominal phi.

---

## Known blockers / open items

| Item | Status |
|------|--------|
| GitHub remote `SoniaTasmin/llm-routing` | created + **pushed/synced** 2026-08-31; `refs/heads/main` on GitHub verified equal to local `HEAD` via `git ls-remote` |
| Git identity | set **repo-locally** to Sonia Tasmin / stasmin10@gmail.com so the office GitLab identity is never used |
| `.spike/` working area | git-ignored; holds both candidate clones + venvs + the ASTRA-Sim build. Recreate from `REPRODUCE.md` §3a; safe to delete. |
| Mooncake trace | not yet downloaded from upstream (M2). A preprocessed copy ships with Vidur `canary` — **not to be trusted without re-derivation** |
| Azure LLM inference traces | not yet downloaded (M2) |
| vLLM testbed / GPU access | not yet arranged (needed by M3 and M11) |

## Risks carried out of M1

| # | Risk | Owner milestone |
|---|------|-----------------|
| F1 | R4 heterogeneity on Vidur may exceed 8 engineer-days | M4 / M7 |
| F2 | Vidur's per-process predictor-load tax (`measured` 32–115 s) and 4.02 GB peak RSS may make the E1 fleet sweep infeasible on this hardware | M4 |
| F6 | Mooncake at native lengths exceeds every model context Vidur ships (p95 40 568 tokens vs a 32 768 maximum); the filtering or scaling policy we choose changes the prefix structure RQ1 measures | M2 / M4 |
| F3 | `canary`'s prefix cache may not faithfully port vLLM's block-pool semantics | M4 |
| F4 | The shipped Mooncake CSV may not be re-derivable from upstream | M2 |
| F5 | `canary` is an unmerged branch, last commit 2025-06-25, and will not be maintained | M2 (mitigate by vendoring at a pinned SHA) |

Full statement of each, with what would trigger it: `docs/spike/recommendation.md` §5.

---

## Standing reminders

- Headline comparison is always **against B2-tok**, never against Round Robin.
- Primary outcome is **minimum fleet cost at fixed SLO**.
- Never fabricate measurements; label every number
  `measured` / `hypothesis` / `estimate` / `assumption`.
