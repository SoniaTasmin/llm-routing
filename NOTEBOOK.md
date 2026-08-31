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
