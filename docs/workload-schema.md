# docs/workload-schema.md — the unified workload record format

**Version 1.0** · defined in `src/workload/schema.py` · M2

Every workload this project simulates is converted to one record type before
anything downstream sees it. Routers, the simulator adapter and the analysis
harness read this schema and nothing else. The point is that a policy cannot
behave differently on one source because it happened to see a differently-shaped
record.

---

## The record

```python
@dataclass(frozen=True)
class WorkloadRequest:
    request_id: int
    arrival_s: float                          # seconds from trace start
    num_prefill_tokens: int                   # >= 1
    num_decode_tokens: int                    # >= 1
    block_hash_ids: tuple[int, ...] | None    # chained prefix hashes, prefill only
    block_size: int | None                    # tokens per hash; required iff hashes present
    session_id: int | None                    # never invented by a loader
```

Every workload file is JSONL, one record per line, with a mandatory sidecar
`<file>.manifest.json` recording provenance. `read_workload` refuses a file
without a manifest: a workload with no provenance is not usable here.

---

## The four rules, and what each is defending against

### 1. Cache-blindness is *declared*, never inferred

The manifest carries `prefix_structure: "present" | "absent"`. Downstream code
branches on that flag, not on `block_hash_ids is None`.

`DECISIONS.md` D-004 fixes the Azure traces as **cache-blind controls**: they
record no prompt content, so no cache-hit or prefix-sharing claim may be derived
from them. If cache-blindness were signalled only by a missing field, "this trace
cannot have prefix structure" and "we forgot to populate this field" would look
identical. The schema enforces the distinction in both directions:

- `WorkloadManifest` **rejects** a non-zero `realised_sharing` on a workload
  declared `absent`.
- `read_workload` **rejects** a file whose records carry hashes while its
  manifest declares `absent`, and vice versa.
- `measure_realised_sharing` **raises** on a cache-blind request rather than
  returning `0.0` — a zero could be reported as a finding; an exception cannot.

### 2. Block hashes are supplied by us, never computed by the simulator

Vidur `canary`'s fallback hashing path is broken — confirmed by execution:
`TypeError: hash_block_tokens() takes 3 positional arguments but 4 were given`
(`simulator/vendor/PROVENANCE.md`). It is reached exactly when a request arrives
without externally supplied `block_hash_ids`.

So this is not a stylistic preference. Any workload claiming prefix structure
**must** carry explicit hashes or it will fail at simulation time, and the schema
enforces it at construction instead of three milestones later.

### 3. Prefix semantics are chained

`block_hash_ids[i]` identifies the **whole prefix up to and including block i**,
not that block's tokens in isolation. Two requests share a prefix of `k` blocks
iff their id lists agree on the first `k` entries. This matches vLLM's block-pool
construction and Mooncake's own `hash_ids`.

Two consequences the code enforces:

- **Whole blocks only.** `len(block_hash_ids) == num_prefill_tokens // block_size`.
  A request's trailing partial block is never hashed and is always recomputed.
- **Prefill only.** Decode tokens are excluded. A router choosing a replica at
  admission time does not know what the model will generate, so hashing decode
  tokens would leak future information into a routing decision. (The CSV Vidur
  ships *does* extend its hash chain over decode tokens. We do not.)

### 4. Realised sharing is measured, never assumed

`PROJECT_SPEC.md` §7: the generator "must **measure** the realised
prefix-sharing rate ... Nominal phi may not be reported as if it were measured."

`workload.sharing.measure_realised_sharing` is the single definition, so Mooncake
and the synthetic sweep are scored identically and their numbers are comparable:

> Requests in arrival order. A block is *reused* if its chained hash id has
> already been emitted by an earlier request. Realised sharing is
> `reused_blocks / total_blocks`.

**This is an upper bound on any achievable cache hit rate.** It assumes infinite
capacity and no eviction. A simulator with a finite, evicting cache reports a
lower number. The two characterise different things — this one the *workload*,
the simulator's the *workload-plus-system* pair — and must never be compared as
though they were the same quantity.

---

## What the three sources produce

| | Mooncake | Azure 2023 | Synthetic |
|---|---|---|---|
| `prefix_structure` | present | **absent** | present |
| `block_size` | 512 (upstream's own) | — | 512 (configurable) |
| `session_id` | **None** — upstream has none | None | set (ground truth by construction) |
| Realised sharing | 38.19 % `measured` | undefined by construction | measured per phi |
| Role | primary trace, RQ1/E2 | cache-blind control | controlled phi sweep, E2 |

### Why Mooncake gets no `session_id` but the synthetic generator does

Upstream Mooncake has no session field. The CSV Vidur ships invents one — 7 417
sessions over 12 031 requests — by a rule we could not recover from the source.

Our session-sticky routing policies (B3, and Vidur's `sticky_lor`) key on exactly
this field. Adopting an invented grouping would mean **routing on a structure
someone else inferred while reporting results about Mooncake**. So the loader
leaves it `None`, and if we later want session-sticky policies on Mooncake we
must derive sessions ourselves under a rule written down in `DECISIONS.md`.

In the synthetic generator the sessions are not inferred — they are the
construction. Reporting them is reporting ground truth.
