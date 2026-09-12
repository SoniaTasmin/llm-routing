"""Adapter: canonical prompt-only workloads -> Vidur's whole-sequence contract.

**The collision.** Our canonical schema hashes the **prompt only**
(`docs/workload-schema.md`, rule 3): a router choosing a replica at admission
cannot know what the model will generate, so hashing output tokens would leak
future information into a routing decision. Vidur disagrees —
`vidur/entities/request.py` asserts

    0 <= num_prefill_tokens + num_decode_tokens - block_size * len(block_hash_ids) < block_size

i.e. it requires hashes covering **prompt + output**.

That is not a bug on either side. It is a difference of purpose: Vidur's list
describes what the *KV cache* will eventually hold, ours describes what a
*router* may legitimately know.

**The leakage this adapter prevents is demonstrated, not assumed.**
`experiments/m4_run_a/leakage_probe.py` builds two requests with identical
32-token prompts differing only in their output hashes, against a pool holding
an earlier identical conversation. Measured admission-time
`get_cached_prefill_length`: **64 tokens** when the output hashes coincide,
**32** when they do not. So (a) future-output hashes change the router's input,
and (b) the estimate exceeds the prompt length — output tokens are credited as
cached prompt tokens. The cause is that `KVCacheManager.get_computed_blocks`
walks the whole hash list and stops at the first miss, with no bound at
`num_prefill_tokens`, and `get_cached_prefill_length` returns that walk
uncapped.

**The fix, entirely in this layer.** Emit

    [ real prompt-block ids ] ++ [ request-unique placeholders ]

with `prefill // block_size` real ids and placeholders filling the rest. Because
each placeholder is unique to one request, it is never in the pool at admission,
so the chained walk **necessarily breaks there**. The admission-time estimate is
therefore bounded by the complete prompt blocks *by construction* — no patch to
the vendored simulator is required, and the vendored tree stays byte-identical.

The block straddling the prompt/output boundary is a placeholder too: its
contents mix prompt and generated tokens, so its identity is genuinely unknown
and must not be claimed as shared.

**Limitation, stated precisely.** Unique placeholders cannot reproduce reuse of
*generated content* between requests. In a real server, if two conversations
generate the same continuation, the second could hit the first's output KV; here
it cannot.

This is narrower than it first sounds for Mooncake specifically: a later turn's
*prompt* already contains the earlier turn's output, and Mooncake hashes the
whole input, so **cross-turn reuse is captured through prompt hashes**. What is
lost is reuse of output that has not yet reappeared in anyone's prompt. Closing
that gap would need trace information Mooncake does not carry — per-token output
identity — so it is a limitation of the data, not of this adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .schema import WorkloadError, WorkloadRequest

# Disjoint id spaces. Expanded prompt ids are small (h*32+j); G4 prompt-tail ids
# live at 2**40; output placeholders live at 2**50. Checked, not assumed.
OUTPUT_PLACEHOLDER_BASE = 1 << 50
_REQ_SHIFT = 20                      # up to 2**20 requests and 2**20 blocks each
_MAX_INDEX = (1 << _REQ_SHIFT) - 1


@dataclass(frozen=True)
class AdaptationReport:
    requests: int
    prompt_blocks: int
    placeholder_blocks: int

    @property
    def total_blocks(self) -> int:
        return self.prompt_blocks + self.placeholder_blocks

    def summary(self) -> str:
        return (
            f"vidur adaptation: {self.requests:,} requests, "
            f"{self.prompt_blocks:,} real prompt blocks + "
            f"{self.placeholder_blocks:,} request-unique output placeholders "
            f"(= {self.total_blocks:,} hashes for Vidur's whole-sequence contract)"
        )


def _placeholder(request_id: int, index: int) -> int:
    if request_id > _MAX_INDEX or index > _MAX_INDEX:
        raise WorkloadError(
            f"placeholder id space exhausted (request {request_id}, index {index}); "
            f"both must be <= {_MAX_INDEX}"
        )
    return OUTPUT_PLACEHOLDER_BASE + (request_id << _REQ_SHIFT) + index


def to_vidur_hashes(
    requests: Sequence[WorkloadRequest],
) -> tuple[list[list[int]], AdaptationReport]:
    """Build Vidur-contract hash lists from prompt-only workload records.

    Returns one list per request, of length
    ``(num_prefill_tokens + num_decode_tokens) // block_size``, satisfying
    Vidur's assertion. The canonical workload is **not** modified.
    """
    if not requests:
        raise WorkloadError("no requests to adapt")

    out: list[list[int]] = []
    n_prompt = n_ph = 0

    for r in requests:
        if r.block_hash_ids is None or r.block_size is None:
            raise WorkloadError(
                f"request {r.request_id}: cannot adapt a cache-blind record; "
                "Vidur's contract needs hashes"
            )
        bs = r.block_size
        n_prompt_blocks = r.num_prefill_tokens // bs
        if len(r.block_hash_ids) != n_prompt_blocks:
            raise WorkloadError(
                f"request {r.request_id}: schema violation — {len(r.block_hash_ids)} "
                f"hashes for {n_prompt_blocks} complete prompt blocks"
            )
        n_total_blocks = (r.num_prefill_tokens + r.num_decode_tokens) // bs

        ids = list(r.block_hash_ids)
        for idx in range(n_prompt_blocks, n_total_blocks):
            ids.append(_placeholder(r.request_id, idx))

        if min(ids, default=0) < 0:
            raise WorkloadError(f"request {r.request_id}: negative hash id")
        for h in r.block_hash_ids:
            if h >= OUTPUT_PLACEHOLDER_BASE:
                raise WorkloadError(
                    f"request {r.request_id}: prompt hash {h} collides with the "
                    "output-placeholder id space"
                )

        out.append(ids)
        n_prompt += n_prompt_blocks
        n_ph += n_total_blocks - n_prompt_blocks

    return out, AdaptationReport(len(requests), n_prompt, n_ph)
