# CURRENT_STATUS.md — What Is Happening RIGHT NOW

**Last updated:** 2026-08-31
**Project week:** Week 1 of 12
**Branch:** `master`

---

## Milestone state

| Milestone | Title | State |
|-----------|-------|-------|
| **M0** | Research specification (framing, RQs, policies, experiments, stats) | **APPROVED AND FROZEN** |
| **M1** | Simulator-base spike (Vidur vs LLMServingSim vs small custom DES) | **IN PROGRESS** |
| M2+ | everything else | NOT STARTED — do not implement |

---

## What was just done

Repository scaffolding for M1:

- Created directory structure (`src/`, `simulator/`, `workloads/`,
  `experiments/`, `analysis/`, `configs/`, `tests/`, `results/`, `docs/`).
- Created the repository memory system: `CLAUDE.md`, `README.md`,
  `PROJECT_SPEC.md`, `CURRENT_STATUS.md`, `MILESTONES.md`, `DECISIONS.md`,
  `NOTEBOOK.md`, `REPRODUCE.md`.
- Froze the Milestone-0 specification into `PROJECT_SPEC.md`.
- Wrote the permanent assistant contract into `CLAUDE.md`.

**No code has been written. No simulator has been chosen. No experiment has
been run. No measurements exist.**

---

## What is happening right now

**Waiting for explicit user approval to begin the Milestone 1 simulator-base
spike.**

The scaffolding step is complete and the assistant has STOPPED, per the
milestone protocol.

---

## Immediate next step (only after approval)

Begin **M1 — simulator-base spike** (3 days, Week 1):

1. Obtain and inspect **Vidur**.
2. Obtain and inspect **LLMServingSim**.
3. Score both against requirements R1–R8 (see `PROJECT_SPEC.md` §9).
4. Produce a written scoring matrix with evidence (file/line references, not
   impressions) in `docs/spike/`.
5. Recommend one of: extend Vidur · extend LLMServingSim · build a small
   cluster-level DES.
6. Record the decision and rationale in `DECISIONS.md`.

No pre-commitment to any candidate. No simulator implementation during scoring.

---

## Known blockers / open items

| Item | Status |
|------|--------|
| GitHub remote `SoniaTasmin/llm-routing` | created by user 2026-08-31 (public); `origin` set locally |
| Git identity | set **repo-locally** to Sonia Tasmin / stasmin10@gmail.com so the office GitLab identity is never used |
| Mooncake trace | not yet downloaded (Week 2) |
| Azure LLM inference traces | not yet downloaded (Week 2) |
| vLLM testbed / GPU access | not yet arranged (needed by Week 3 and Week 11) |

---

## Standing reminders

- Headline comparison is always **against B2-tok**, never against Round Robin.
- Primary outcome is **minimum fleet cost at fixed SLO**.
- Never fabricate measurements; label every number
  `measured` / `hypothesis` / `estimate` / `assumption`.
