"""Workload transformations, applied only under a recorded decision.

A transformation changes the workload the study measures. None is applied by
default and none is applied silently: every one returns a report of exactly what
it did, which the caller writes into the workload manifest.

The native trace is **immutable**. Transformations always produce a separately
named variant, never an in-place edit, so the untransformed workload remains
available for comparison and for any later decision to run natively.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .schema import WorkloadError, WorkloadRequest


@dataclass(frozen=True)
class TruncationReport:
    """What a context-budget truncation actually did."""

    budget_tokens: int
    requests_in: int
    requests_out: int
    requests_truncated: int
    requests_dropped: int
    blocks_in: int
    blocks_out: int
    prefill_tokens_in: int
    prefill_tokens_out: int
    decode_tokens_in: int
    decode_tokens_out: int

    @property
    def block_retention(self) -> float:
        return self.blocks_out / self.blocks_in if self.blocks_in else 0.0

    @property
    def prefill_token_retention(self) -> float:
        return (
            self.prefill_tokens_out / self.prefill_tokens_in
            if self.prefill_tokens_in
            else 0.0
        )

    def as_dict(self) -> dict:
        return {
            "budget_tokens": self.budget_tokens,
            "requests_in": self.requests_in,
            "requests_out": self.requests_out,
            "requests_truncated": self.requests_truncated,
            "requests_dropped": self.requests_dropped,
            "blocks_in": self.blocks_in,
            "blocks_out": self.blocks_out,
            "block_retention": round(self.block_retention, 6),
            "prefill_tokens_in": self.prefill_tokens_in,
            "prefill_tokens_out": self.prefill_tokens_out,
            "prefill_token_retention": round(self.prefill_token_retention, 6),
            "decode_tokens_in": self.decode_tokens_in,
            "decode_tokens_out": self.decode_tokens_out,
            "decode_preserved": self.decode_tokens_in == self.decode_tokens_out,
        }

    def summary(self) -> str:
        return (
            f"truncated to {self.budget_tokens:,} total tokens: "
            f"{self.requests_truncated:,}/{self.requests_in:,} requests altered, "
            f"{self.requests_dropped} dropped, "
            f"{100 * self.block_retention:.2f}% of prefix blocks retained, "
            f"decode lengths "
            f"{'preserved' if self.decode_tokens_in == self.decode_tokens_out else 'ALTERED'}"
        )


def truncate_to_context_budget(
    requests: Sequence[WorkloadRequest], budget_tokens: int
) -> tuple[list[WorkloadRequest], TruncationReport]:
    """Cap each request's prompt so that prefill + decode <= ``budget_tokens``.

    What is preserved, deliberately:

    - **Arrival times** — untouched. The arrival process is a property of the
      workload we are not entitled to alter.
    - **Output lengths** — untouched. Only the *prompt* is capped, so the decode
      phase each request drives is the one Mooncake recorded.
    - **Request count** — nothing is dropped unless a request's decode length
      alone exceeds the budget, which is reported separately if it happens.

    What changes:

    - ``num_prefill_tokens`` is capped at ``budget_tokens - num_decode_tokens``.
    - ``block_hash_ids`` is truncated to the whole blocks that survive. Because
      prefix hashes are *chained*, truncating from the tail is the only
      structure-preserving edit available: the retained ids still identify the
      same prefixes they did before. Truncating from the head, or renumbering,
      would destroy the sharing relation the workload exists to carry.

    Truncation keeps each request's prompt **head**, which is where prefix reuse
    concentrates, and discards its tail, which is mostly unique. That inflates
    the realised sharing *ratio* — the effect is small at a large budget but it
    is real, and the caller must report it rather than treat the variant as
    equivalent to the native trace.
    """
    if budget_tokens < 1:
        raise WorkloadError(f"budget_tokens must be >= 1, got {budget_tokens}")

    out: list[WorkloadRequest] = []
    n_trunc = n_drop = 0
    blocks_in = blocks_out = 0
    pre_in = pre_out = dec_in = dec_out = 0

    for r in requests:
        blocks_in += len(r.block_hash_ids or ())
        pre_in += r.num_prefill_tokens
        dec_in += r.num_decode_tokens

        prefill_cap = budget_tokens - r.num_decode_tokens
        if prefill_cap < 1:
            # Decode alone exceeds the budget: capping the prompt cannot help.
            # Reported, never silently coerced.
            n_drop += 1
            continue

        if r.num_prefill_tokens <= prefill_cap:
            out.append(r)
            blocks_out += len(r.block_hash_ids or ())
            pre_out += r.num_prefill_tokens
            dec_out += r.num_decode_tokens
            continue

        new_prefill = prefill_cap
        if r.block_hash_ids is not None:
            n_whole = new_prefill // r.block_size
            new_hashes = r.block_hash_ids[:n_whole]
        else:
            new_hashes = None

        t = WorkloadRequest(
            request_id=r.request_id,
            arrival_s=r.arrival_s,                 # preserved
            num_prefill_tokens=new_prefill,
            num_decode_tokens=r.num_decode_tokens,  # preserved
            block_hash_ids=new_hashes,
            block_size=r.block_size,
            session_id=r.session_id,
        )
        out.append(t)
        n_trunc += 1
        blocks_out += len(new_hashes or ())
        pre_out += t.num_prefill_tokens
        dec_out += t.num_decode_tokens

    report = TruncationReport(
        budget_tokens=budget_tokens,
        requests_in=len(requests),
        requests_out=len(out),
        requests_truncated=n_trunc,
        requests_dropped=n_drop,
        blocks_in=blocks_in,
        blocks_out=blocks_out,
        prefill_tokens_in=pre_in,
        prefill_tokens_out=pre_out,
        decode_tokens_in=dec_in,
        decode_tokens_out=dec_out,
    )
    return out, report


# ---------------------------------------------------------------------------
# Gate G4: 512-token workload hashes -> 16-token simulator blocks
# ---------------------------------------------------------------------------

TAIL_ID_BASE = 1 << 40  # disjoint from any expanded id; never collides


@dataclass(frozen=True)
class ExpansionReport:
    """What the block-size expansion did, and how much it cannot know."""

    source_block_size: int
    target_block_size: int
    factor: int
    requests: int
    expanded_blocks: int      # derived from real 512-token hashes
    tail_blocks: int          # sub-512 remainder: sharing UNKNOWN, marked unique
    total_blocks: int

    @property
    def tail_fraction(self) -> float:
        return self.tail_blocks / self.total_blocks if self.total_blocks else 0.0

    def as_dict(self) -> dict:
        return {
            "source_block_size": self.source_block_size,
            "target_block_size": self.target_block_size,
            "factor": self.factor,
            "requests": self.requests,
            "expanded_blocks": self.expanded_blocks,
            "tail_blocks_unknown_sharing": self.tail_blocks,
            "total_blocks": self.total_blocks,
            "tail_fraction": round(self.tail_fraction, 6),
        }

    def summary(self) -> str:
        return (
            f"{self.source_block_size}->{self.target_block_size} expansion "
            f"(x{self.factor}): {self.total_blocks:,} blocks, of which "
            f"{self.tail_blocks:,} ({100*self.tail_fraction:.2f}%) are sub-"
            f"{self.source_block_size} tail blocks whose sharing is UNKNOWN and "
            "is therefore recorded as none. NOTE: this accounts for unhashed "
            "tails only. Fine-prefix sharing between UNEQUAL coarse blocks is "
            "also invisible and is not measurable from hashes alone, so true "
            "16-token sharing is >= what this produces, by an unknown amount."
        )


def expand_block_hashes(
    requests: Sequence[WorkloadRequest], target_block_size: int = 16
) -> tuple[list[WorkloadRequest], ExpansionReport]:
    """Re-express coarse prefix hashes at the simulator's finer block size.

    **Why this is needed.** Mooncake hashes at 512 tokens. Vidur's KV block size
    is 16 and is *forced*: ``_load_attention_df`` filters training rows on
    ``block_size`` and every shipped profile carries 16 only, so 512 would leave
    the predictor with no data. Handing 512-granularity ids to a 16-token cache
    would make each id cover 16 tokens instead of 512 — a 32x under-count of the
    cached region, biased toward making cache-aware routing look worse than it is.

    **Why the expansion is sound rather than invented.** Prefix hashes are
    *chained*: id ``h_i`` identifies the whole prefix through block ``i``. If two
    requests agree on their first ``k`` coarse ids, their first ``512k`` tokens
    are identical, hence their first ``32k`` 16-token blocks are identical too.
    Emitting ``child(h_i, j) = h_i * factor + j`` states exactly that and nothing
    more: the map is deterministic and depends only on ``(h_i, j)``, so agreement
    on coarse prefixes transfers to fine prefixes, and disagreement does not
    create agreement.

    **Two distinct things it cannot know**, and only the first is measurable:

    1. **Unhashed prompt tails.** A request's remainder below a 512-token
       boundary is never hashed upstream, yet contains up to 31 whole 16-token
       blocks. They are given **unique, never-matching** ids. This bias *is*
       quantified — ``ExpansionReport.tail_blocks`` — and it is the only part of
       the picture the measured transformation delta covers.

    2. **Fine-prefix sharing between *unequal* coarse blocks.** If two requests
       diverge at coarse block *i* (different ids there), their underlying
       512-token spans may still share a leading run of 16-token blocks — the
       texts could agree for 300 tokens and then differ. The expansion gives
       unequal parents disjoint children by construction, so that sharing is
       **invisible to us**, and it is **not measurable from the data we have**:
       Mooncake supplies hashes, not tokens, so there is nothing to compare
       below 512-token resolution.

    Both push the same way — the mapping **under-counts** true 16-token sharing
    and never fabricates it. But the reported delta bounds only (1).
    **True fine-grained sharing is >= what this produces, by an unknown amount.**
    """
    if not requests:
        raise WorkloadError("no requests to expand")
    src_bs = requests[0].block_size
    if src_bs is None:
        raise WorkloadError("cannot expand a cache-blind workload")
    if src_bs % target_block_size != 0:
        raise WorkloadError(
            f"source block size {src_bs} is not a multiple of target "
            f"{target_block_size}; there is no whole-block refinement"
        )
    factor = src_bs // target_block_size

    # Enforce, do not assume, that expanded ids and tail ids occupy disjoint
    # ranges. child(h, j) = h*factor + j, so the highest child id is
    # max_h*factor + factor-1; it must stay below TAIL_ID_BASE or a coarse-derived
    # block could silently alias a tail block and manufacture sharing.
    max_h = max(
        (max(r.block_hash_ids) for r in requests if r.block_hash_ids), default=-1
    )
    if max_h >= 0:
        highest_child = max_h * factor + (factor - 1)
        if highest_child >= TAIL_ID_BASE:
            raise WorkloadError(
                f"id-space collision: highest expanded id {highest_child} reaches "
                f"TAIL_ID_BASE {TAIL_ID_BASE}. Coarse-derived blocks would alias "
                "tail blocks and fabricate sharing. Raise TAIL_ID_BASE or "
                "renumber the source hashes."
            )

    out: list[WorkloadRequest] = []
    n_expanded = n_tail = 0
    tail_counter = 0

    for r in requests:
        if r.block_size != src_bs:
            raise WorkloadError(
                f"request {r.request_id}: mixed source block sizes "
                f"({src_bs} and {r.block_size})"
            )
        coarse = r.block_hash_ids or ()
        fine: list[int] = []
        for h in coarse:
            fine.extend(h * factor + j for j in range(factor))
        n_expanded += len(fine)

        # Whole target-blocks the coarse hashes could not describe.
        n_target_total = r.num_prefill_tokens // target_block_size
        for _ in range(n_target_total - len(fine)):
            fine.append(TAIL_ID_BASE + tail_counter)
            tail_counter += 1
            n_tail += 1

        out.append(
            WorkloadRequest(
                request_id=r.request_id,
                arrival_s=r.arrival_s,
                num_prefill_tokens=r.num_prefill_tokens,
                num_decode_tokens=r.num_decode_tokens,
                block_hash_ids=tuple(fine),
                block_size=target_block_size,
                session_id=r.session_id,
            )
        )

    # Post-conditions. Cheap relative to the transformation, and they guard the
    # two properties the soundness argument depends on.
    seen_tail: set[int] = set()
    for r in out:
        for bid in r.block_hash_ids or ():
            if bid >= TAIL_ID_BASE:
                if bid in seen_tail:
                    raise WorkloadError(
                        f"tail id {bid} reused; tail ids must be globally unique "
                        "within a workload or they would create phantom sharing"
                    )
                seen_tail.add(bid)
    if len(seen_tail) != n_tail:
        raise WorkloadError(
            f"tail id accounting mismatch: {len(seen_tail)} distinct ids for "
            f"{n_tail} tail blocks"
        )

    report = ExpansionReport(
        source_block_size=src_bs,
        target_block_size=target_block_size,
        factor=factor,
        requests=len(requests),
        expanded_blocks=n_expanded,
        tail_blocks=n_tail,
        total_blocks=n_expanded + n_tail,
    )
    return out, report
