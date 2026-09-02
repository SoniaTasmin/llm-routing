# docs/spike/ — Milestone 1 simulator-base spike artefacts

**Status: COMPLETE (2026-09-02).** The spike ran; the decision is recorded as
**D-006** in `DECISIONS.md`.

Read in this order:

| File | What it is |
|------|------------|
| `requirements-matrix.md` | **Start here.** Vidur (`main` and `canary`) and LLMServingSim scored against R1–R8, with file/line evidence, plus engineer-day extension estimates for every failed and partial requirement, and the weighting used. |
| `vidur-notes.md` | Vidur: what was installed, what ran, measured timings, architecture, per-requirement evidence, defects found. |
| `llmservingsim-notes.md` | LLMServingSim 2.0: the same. |
| `recommendation.md` | The single recommendation, what it costs us, why the alternatives were rejected, and six dated falsifiers. |

Failed installations, stalls and dead ends are in `NOTEBOOK.md`, not here.

**Outcome:** extend **Vidur**, branch `canary`, pinned at
`25e0082dbbfb206fb0477c3ebbededa7ead78949`.

Requirements evaluated (`PROJECT_SPEC.md` §9): R1 multiple replicas · R2
pluggable routing · R3 cross-replica prefix-cache state · R4 heterogeneous
replica types · R5 mid-run replica removal/failure · R6 SLO/deadline modelling ·
R7 cost accounting · R8 per-request metrics.

## Reproducing the spike

Both candidates were cloned into a git-ignored `.spike/` working area; nothing
third-party is committed to this repository. The exact commands, commit SHAs and
the workarounds needed are in `REPRODUCE.md` §3a.
