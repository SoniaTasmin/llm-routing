# simulator/vendor/PROVENANCE.md — where the vendored simulator came from

This directory holds a **frozen copy of third-party source**, committed
deliberately. It is not a dependency we track, and it is not ours.

---

## What is vendored

| Field | Value |
|---|---|
| Project | **Vidur** — an LLM inference cluster simulator |
| Upstream | `https://github.com/microsoft/vidur` |
| Branch | `canary` (an **unmerged development branch**, not `main`) |
| **Commit (pinned)** | **`25e0082dbbfb206fb0477c3ebbededa7ead78949`** |
| Upstream commit date | 2025-06-25 |
| Licence | **MIT** — `vidur/LICENSE`, Copyright (c) Microsoft Corporation |
| Paper | Agrawal et al., *Vidur: A Large-Scale Simulation Framework for LLM Inference*, MLSys 2024 |
| Vendored on | 2026-09-10 |
| Authorised by | **D-006** (`DECISIONS.md`), clarified by **D-007** |

Extracted with `git archive <SHA>`, so the contents are provably the tree at that
commit rather than a copy of a working directory that might have drifted.

**Integrity check.** `VENDOR_TREE_SHA256` holds a SHA-256 over the sorted
file list of `vendor/vidur/`:

```
3881bc3c15a1e40eef474f7b81262b538e4d9017a5b2cbabac5ea30b8458448c
```

Recompute with:

```bash
find simulator/vendor/vidur -type f -print0 | sort -z \
  | xargs -0 sha256sum | sha256sum | cut -d' ' -f1
```

---

## What is included, and what is not

The upstream commit has **267** files. **181 Python files plus packaging and
docs** are vendored here (1.4 MB). **58 files under `data/` are not** (584 MB).

| Path | Vendored? | Why |
|---|---|---|
| `vidur/` (the package) | **yes** | the simulator itself |
| `pyproject.toml`, `uv.lock` | **yes** | the lockfile is the reason `canary` was chosen over `main` for reproducibility |
| `LICENSE`, `README.md`, `Makefile`, `docs/` | **yes** | licence obligation, and upstream's own documentation of behaviour we depend on |
| `data/profiling/` (503 MB, 54 CSVs) | **no** | too large for a public repository; fetched at the same SHA by `fetch_vidur_data.sh` |
| `data/processed_traces/` (~82 MB, incl. an 80 MB Mooncake CSV) | **no** | same, **and** we are deliberately re-deriving Mooncake from upstream rather than trusting this copy — see falsifier **F4** |
| `assets/`, `cache/`, `simulator_output/` | **no** | images, and generated artefacts from spike runs |

The exclusions are a size decision, not a content decision: the SHA pins the
excluded files exactly as much as the included ones, and
`fetch_vidur_data.sh` retrieves them from that same commit.

---

## Why vendored rather than tracked as a dependency

`canary` is an **unmerged branch whose last commit is 2025-06-25** — over a year
before we adopted it. The M1 spike's `assumption` is that it will not be
maintained and will never merge (`docs/spike/vidur-notes.md` §6).

Vendoring converts an abandonment risk into a fixed, known quantity: the code
cannot move under us, and a reader a year from now sees exactly what produced our
results. A submodule or a `pip install git+...` would not give that guarantee if
the branch were deleted or force-pushed.

---

## Known defects in this exact commit

Both found during the M1 spike and recorded here so they are not rediscovered:

1. **`vidur/kv_cache/utils.py` — `hash_block_tokens` arity bug.** Defined with
   three parameters, called with four by `hash_request_tokens`. Reached only when
   a request has **no** externally supplied `block_hash_ids`. **Confirmed by
   execution:** `TypeError: hash_block_tokens() takes 3 positional arguments but
   4 were given`. *Consequence:* our synthetic workload generator must emit block
   hashes itself. It does.
2. **`TolerantStickyLOPUncachedGlobalScheduler._cached_prefill_length_map`** — an
   unbounded memo keyed on `(request.id, replica_id)`, never pruned, and stale if
   the replica's cache changes between estimate and dispatch.

Neither is patched here. **This directory is a faithful copy of upstream.** Any
fix of ours belongs outside it, so that "what is upstream" and "what is ours"
never blur.

---

## Rule for this directory

**Do not edit anything under `vendor/vidur/`.** If we need to change simulator
behaviour, it goes in our own code outside `vendor/`, or in a patch file applied
at build time and recorded in `DECISIONS.md`. The integrity checksum above exists
so that an accidental edit is detectable.
