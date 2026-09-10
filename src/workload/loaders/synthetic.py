"""Synthetic workload generator with controlled prefix sharing.

``PROJECT_SPEC.md`` §7 fixes the sweep at phi in {0, 0.25, 0.5, 0.75, 0.9} and
adds a requirement that is easy to state and easy to quietly violate: the
generator must **measure the realised prefix-sharing rate** of what it emitted
and report it next to the nominal phi. Nominal phi may not be reported as if it
were measured. This module therefore always returns both, and writes both into
the manifest.

**Construction — a growing conversation.** Prefix hashes are chained, so two
requests share a prefix of ``k`` blocks exactly when their first ``k`` block ids
are equal. The generator models a **multi-turn conversation**, which is the
mechanism that produces prefix sharing in real serving: turn *t*'s prompt
contains everything said so far, plus that turn's new content. A session holds a
block chain that only ever **grows**::

    turn 1 (opener):   chain = [f0 .. f_{n0-1}]                 sharing 0
    turn t (t > 1):    chain = <entire previous chain> + [new blocks]

so the inherited part is the whole previous chain, of length ``L``, and the
request's own length is ``n = L + new``. Per-request sharing is therefore
``L / (L + new)``, and to hit a target phi the generator appends::

    new = max(1, round(L * (1 - phi) / phi))

which makes ``L / (L + new) ≈ phi`` exactly. A session retires once its chain
would exceed ``max_blocks``, and a fresh one opens in its place.

**An earlier construction replaced the session chain instead of growing it**, and
clamped ``k`` to whatever length the chosen session happened to have. That capped
realised sharing at ~0.69 for a nominal phi of 0.9, because chains collapsed to a
mean length of 5 blocks and 40 % of requests could not find a session long enough
to inherit from. The tests caught it. Recorded here because the failure was not
in the measurement — which was correct throughout — but in assuming a
construction would deliver the rate it was designed for.

**Realised sharing still lands below nominal phi**, and always will: the opening
turn of every session inherits nothing. The gap shrinks as sessions grow longer,
and it is exactly why ``PROJECT_SPEC.md`` §7 requires the number to be measured
rather than assumed.

**Block hashes are emitted explicitly** rather than left for the simulator to
compute from token ids. Vidur ``canary``'s fallback hashing path raises
``TypeError`` (confirmed by execution; see ``simulator/vendor/PROVENANCE.md``),
so a generator that omitted them would fail at simulation time — and the schema
forbids it anyway.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Optional

from ..schema import WorkloadError, WorkloadManifest, WorkloadRequest
from ..sharing import measure_realised_sharing

FROZEN_PHI_SWEEP = (0.0, 0.25, 0.5, 0.75, 0.9)


def generate_synthetic(
    *,
    phi: float,
    num_requests: int,
    seed: int,
    block_size: int = 512,
    min_blocks: int = 2,
    max_blocks: int = 64,
    decode_min: int = 64,
    decode_max: int = 512,
    arrival_rate_per_s: float = 10.0,
    session_pool_size: int = 64,
) -> tuple[list[WorkloadRequest], WorkloadManifest]:
    """Generate a synthetic workload with a target prefix-sharing rate.

    Args:
        phi: nominal target fraction of each request's prefill blocks that are
            inherited from an earlier request. Must be in [0, 1].
        num_requests: how many requests to emit.
        seed: RNG seed. The same seed and arguments always produce the same
            workload — required for the paired, seeded design in
            ``PROJECT_SPEC.md`` §11.
        block_size: tokens per hash block.
        min_blocks, max_blocks: inclusive range for a request's whole-block count.
        decode_min, decode_max: inclusive range for generated tokens.
        arrival_rate_per_s: Poisson arrival rate.
        session_pool_size: how many conversations are live at once. Smaller pools
            concentrate reuse; larger pools spread it.

    Returns:
        Requests in arrival order, and a manifest carrying **both** the nominal
        phi and the measured realised sharing.
    """
    if not 0.0 <= phi <= 1.0:
        raise WorkloadError(f"phi must be in [0, 1], got {phi}")
    if num_requests < 1:
        raise WorkloadError("num_requests must be >= 1")
    if min_blocks < 1 or max_blocks < min_blocks:
        raise WorkloadError("need 1 <= min_blocks <= max_blocks")

    rng = random.Random(seed)
    next_hash_id = 0
    requests: list[WorkloadRequest] = []
    t = 0.0

    # A session must open long enough that its first follow-up turn can actually
    # hit the target: we need round(L*(1-phi)/phi) >= 1, i.e. L >= phi/(1-phi).
    # At phi=0.9 that is 9 blocks; at phi=0.25 it is well under min_blocks.
    if phi >= 1.0:
        raise WorkloadError("phi must be < 1: perfect sharing has no new content")
    opener_blocks = max(min_blocks, math.ceil(phi / (1.0 - phi))) if phi > 0 else min_blocks
    if opener_blocks > max_blocks:
        raise WorkloadError(
            f"phi={phi:g} needs an opening chain of {opener_blocks} blocks to be "
            f"reachable, but max_blocks is {max_blocks}. Raise max_blocks."
        )

    # sessions: session_id -> chained block ids of the latest turn
    sessions: dict[int, list[int]] = {}
    next_session_id = 0

    def open_session() -> int:
        nonlocal next_hash_id, next_session_id
        sid = next_session_id
        next_session_id += 1
        chain = list(range(next_hash_id, next_hash_id + opener_blocks))
        next_hash_id += opener_blocks
        sessions[sid] = chain
        return sid

    for i in range(num_requests):
        t += rng.expovariate(arrival_rate_per_s)

        while len(sessions) < session_pool_size:
            open_session()

        sid = rng.choice(sorted(sessions))
        chain = sessions[sid]
        L = len(chain)

        if phi <= 0.0:
            # No sharing at all: every request is a fresh chain.
            n_blocks = rng.randint(min_blocks, max_blocks)
            chain = list(range(next_hash_id, next_hash_id + n_blocks))
            next_hash_id += n_blocks
            new_chain = chain
        else:
            new = max(1, int(round(L * (1.0 - phi) / phi)))
            if L + new > max_blocks:
                # Conversation has run its course; retire it and open a fresh one.
                del sessions[sid]
                sid = open_session()
                new_chain = list(sessions[sid])
            else:
                new_chain = list(chain) + list(range(next_hash_id, next_hash_id + new))
                next_hash_id += new
            sessions[sid] = new_chain

        n_blocks = len(new_chain)
        # A trailing partial block is realistic and is never hashed. Keeping one
        # here means the schema's "hashes cover whole blocks only" invariant is
        # actually exercised by the synthetic sweep rather than only by Mooncake.
        partial = rng.randrange(block_size)
        prefill = n_blocks * block_size + partial

        requests.append(
            WorkloadRequest(
                request_id=i,
                arrival_s=t,
                num_prefill_tokens=prefill,
                num_decode_tokens=rng.randint(decode_min, decode_max),
                block_hash_ids=tuple(new_chain),
                block_size=block_size,
                session_id=sid,
            )
        )

    report = measure_realised_sharing(requests)

    manifest = WorkloadManifest(
        name=f"synthetic-phi{phi:g}-seed{seed}",
        source="synthetic",
        prefix_structure="present",
        num_requests=len(requests),
        block_size=block_size,
        nominal_phi=phi,
        realised_sharing=report.realised_sharing,
        seed=seed,
        transformation=(
            f"generated: growing-conversation sessions, opener {max(min_blocks, math.ceil(phi/(1-phi))) if phi>0 else min_blocks} blocks, "
            f"per turn new = max(1, round(L*(1-phi)/phi)), chain cap {max_blocks} blocks, "
            f"decode ~ U[{decode_min},{decode_max}], arrivals ~ Poisson("
            f"{arrival_rate_per_s}/s), session pool {session_pool_size}"
        ),
        notes=(
            f"NOMINAL phi = {phi:g}; MEASURED realised sharing = "
            f"{report.realised_sharing:.4f}. These are different quantities and "
            "only the measured one may be reported as a property of this "
            "workload (PROJECT_SPEC.md §7). Realised sits below nominal by "
            "construction: session-opening requests have nothing to inherit."
        ),
        extra={
            "total_blocks": report.total_blocks,
            "reused_blocks": report.reused_blocks,
            "unique_blocks": report.unique_blocks,
            "within_session_blocks": report.within_session_blocks,
            "cross_session_blocks": report.cross_session_blocks,
        },
    )
    return requests, manifest
