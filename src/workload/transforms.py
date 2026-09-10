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
