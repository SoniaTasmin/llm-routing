# docs/spike/ — Milestone 1 simulator-base spike artefacts

**Empty until the M1 spike is approved and run.**

Expected contents when M1 completes:

- `requirements-matrix.md` — Vidur and LLMServingSim scored against R1–R8, with
  concrete evidence (repository paths, file/line references, API surfaces), plus
  an estimated extension effort for each failed requirement.
- `vidur-notes.md` — what was installed, what ran, what broke, what it models.
- `llmservingsim-notes.md` — same.
- `recommendation.md` — a single recommendation with rationale and the evidence
  that would falsify it.

The resulting decision is recorded as **D-006** in `DECISIONS.md`.

Requirements under evaluation (from `PROJECT_SPEC.md` §9): R1 multiple replicas ·
R2 pluggable routing · R3 cross-replica prefix-cache state · R4 heterogeneous
replica types · R5 mid-run replica removal/failure · R6 SLO/deadline modelling ·
R7 cost accounting · R8 per-request metrics.
