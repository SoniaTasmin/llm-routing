"""Measuring realised prefix sharing.

``PROJECT_SPEC.md`` §7 is explicit: the synthetic generator "must **measure** the
realised prefix-sharing rate of the emitted workload and report it alongside the
nominal phi. Nominal phi may not be reported as if it were measured." This module
is the one place that measurement is defined, so Mooncake and the synthetic sweep
are scored the same way and their numbers are comparable.

**Definition.** Requests are processed in arrival order. A prefix block is
*reused* if its chained hash id has already been emitted by an earlier request.
Realised sharing is the fraction of prefill **tokens** in whole blocks that are
reused:

    realised_sharing = reused_block_tokens / total_block_tokens

Tokens in a request's trailing partial block are excluded from both numerator and
denominator, because partial blocks are never hashed and are always recomputed.

**What this deliberately is not.** It is an *upper bound* on the cache hit rate a
real system could achieve: it assumes infinite cache capacity and no eviction. A
simulator with a finite, evicting cache will report a lower number. The two are
different quantities and must not be compared as if they were the same — this one
characterises the *workload*, the simulator's number characterises a
*workload-plus-system* pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .schema import WorkloadRequest


@dataclass(frozen=True)
class SharingReport:
    total_blocks: int
    reused_blocks: int
    unique_blocks: int
    total_block_tokens: int
    reused_block_tokens: int
    realised_sharing: float
    within_session_blocks: Optional[int] = None
    cross_session_blocks: Optional[int] = None

    def summary(self) -> str:
        s = (
            f"realised prefix sharing: {100 * self.realised_sharing:.2f}% "
            f"({self.reused_blocks:,}/{self.total_blocks:,} blocks reused, "
            f"{self.unique_blocks:,} unique)"
        )
        if self.within_session_blocks is not None:
            s += (
                f"; reuse split: within-session {self.within_session_blocks:,}, "
                f"cross-session {self.cross_session_blocks:,}"
            )
        return s


def measure_realised_sharing(requests: Iterable[WorkloadRequest]) -> SharingReport:
    """Measure realised prefix sharing over a workload, in arrival order.

    Raises:
        ValueError: if any request lacks block hashes. A cache-blind workload has
            no realised sharing to measure and asking for it is a bug, not a
            zero — see ``DECISIONS.md`` D-004.
    """
    seen: dict[int, Optional[int]] = {}
    total = reused = 0
    within = cross = 0
    have_sessions = True
    block_size: Optional[int] = None

    for r in requests:
        if r.block_hash_ids is None:
            raise ValueError(
                f"request {r.request_id} has no block hashes. Realised sharing "
                "is undefined for a cache-blind workload."
            )
        if block_size is None:
            block_size = r.block_size
        elif r.block_size != block_size:
            raise ValueError(
                "mixed block sizes in one workload "
                f"({block_size} and {r.block_size}); sharing would not be "
                "comparable across records"
            )
        if r.session_id is None:
            have_sessions = False
        for bid in r.block_hash_ids:
            total += 1
            if bid in seen:
                reused += 1
                if have_sessions and seen[bid] == r.session_id:
                    within += 1
                else:
                    cross += 1
            else:
                seen[bid] = r.session_id

    if total == 0:
        return SharingReport(0, 0, 0, 0, 0, 0.0)

    bs = block_size or 0
    return SharingReport(
        total_blocks=total,
        reused_blocks=reused,
        unique_blocks=len(seen),
        total_block_tokens=total * bs,
        reused_block_tokens=reused * bs,
        realised_sharing=reused / total,
        within_session_blocks=within if have_sessions else None,
        cross_session_blocks=cross if have_sessions else None,
    )
