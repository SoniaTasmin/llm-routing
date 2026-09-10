"""Mooncake conversation-trace loader — re-derived from upstream.

Reads the trace **from its original source**, not from the preprocessed CSV that
Vidur ``canary`` ships. That preprocessed copy is why falsifier F4 exists: it is
a third party's reduction of exactly the structure RQ1 measures, and adopting it
untested would make our headline finding rest on someone else's undocumented
transformation.

Upstream format (``FAST25-release/traces/conversation_trace.jsonl``), one JSON
object per line::

    {"timestamp": 0, "input_length": 6758, "output_length": 500,
     "hash_ids": [0, 1, 2, ..., 13]}

- ``timestamp``      milliseconds from trace start
- ``input_length``   prompt tokens
- ``output_length``  generated tokens
- ``hash_ids``       chained prefix-block ids, **512 tokens per block**

The 512-token block size is not documented in the file; it was established
empirically and holds for **12 031 / 12 031** records
(``len(hash_ids) == ceil(input_length / 512)``). ``verify_block_size`` re-checks
it on load rather than trusting this comment.

**Deliberate divergences from the CSV Vidur ships**, each recorded in
``docs/workload-mooncake-f4.md``:

- We do **not** add 512 tokens to every prompt. The shipped CSV does, uniformly,
  for reasons we could not determine from the source.
- We do **not** invent ``session_id``. Upstream has no session field; the shipped
  CSV's 7 417 sessions are a construction. Since our session-sticky routing
  policies key on exactly this field, inventing it would mean routing on someone
  else's inferred grouping while reporting results about Mooncake.
- We keep upstream's 512-token blocks by default rather than re-blocking to 16.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Optional

from ..schema import WorkloadManifest, WorkloadRequest, WorkloadError

UPSTREAM_URL = "https://github.com/kvcache-ai/Mooncake"
UPSTREAM_PATH = "FAST25-release/traces/conversation_trace.jsonl"
MOONCAKE_BLOCK_SIZE = 512


def verify_block_size(records: list[dict], block_size: int = MOONCAKE_BLOCK_SIZE) -> float:
    """Fraction of records where ``len(hash_ids) == ceil(input_length/block_size)``."""
    if not records:
        return 0.0
    ok = sum(
        1
        for r in records
        if len(r["hash_ids"]) == math.ceil(r["input_length"] / block_size)
    )
    return ok / len(records)


def load_mooncake(
    path: str | Path,
    *,
    max_total_tokens: Optional[int] = None,
    limit: Optional[int] = None,
    block_size: int = MOONCAKE_BLOCK_SIZE,
) -> tuple[list[WorkloadRequest], WorkloadManifest]:
    """Load the upstream Mooncake conversation trace into the unified schema.

    Args:
        path: the upstream ``conversation_trace.jsonl``.
        max_total_tokens: if set, **drop** requests whose prefill+decode exceeds
            this. Filtering is offered because no model configuration Vidur ships
            has a context window large enough for Mooncake's p95 request
            (falsifier F6) — but it is **not** applied by default, and the
            manifest records that it happened, because dropping the long tail
            changes the prefix-sharing structure RQ1 measures.
        limit: keep only the first N records after filtering.
        block_size: tokens per hash id. Verified against the data on load.

    Returns:
        Requests in arrival order, and a manifest carrying the upstream file's
        SHA-256 so a result can be traced to exact bytes.
    """
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    records = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]

    fit = verify_block_size(records, block_size)
    if fit < 1.0:
        raise WorkloadError(
            f"block_size={block_size} does not describe this trace: only "
            f"{100 * fit:.1f}% of records satisfy "
            "len(hash_ids) == ceil(input_length/block_size). Refusing to guess."
        )

    n_seen = len(records)
    if max_total_tokens is not None:
        records = [
            r
            for r in records
            if r["input_length"] + r["output_length"] <= max_total_tokens
        ]
    n_after_filter = len(records)
    if limit is not None:
        records = records[:limit]

    requests: list[WorkloadRequest] = []
    for i, r in enumerate(records):
        prefill = int(r["input_length"])
        # Only WHOLE blocks are hashed. Upstream's hash_ids includes a final id
        # for the trailing partial block; we drop it, because the unified schema
        # says a hash covers a complete block and the partial tail is recomputed.
        n_whole = prefill // block_size
        requests.append(
            WorkloadRequest(
                request_id=i,
                arrival_s=float(r["timestamp"]) / 1000.0,
                num_prefill_tokens=prefill,
                num_decode_tokens=int(r["output_length"]),
                block_hash_ids=tuple(r["hash_ids"][:n_whole]),
                block_size=block_size,
                session_id=None,  # upstream has none; we do not invent one
            )
        )

    transformation = (
        "timestamp ms -> arrival_s seconds; input_length -> num_prefill_tokens "
        "(unchanged); output_length -> num_decode_tokens (unchanged); hash_ids "
        f"truncated to floor(prefill/{block_size}) whole blocks; session_id left "
        "None (absent upstream)."
    )
    if max_total_tokens is not None:
        transformation += (
            f" FILTERED to total_tokens <= {max_total_tokens}: "
            f"{n_after_filter}/{n_seen} records kept."
        )
    if limit is not None:
        transformation += f" Truncated to first {limit} records."

    manifest = WorkloadManifest(
        name="mooncake-conversation",
        source="mooncake",
        prefix_structure="present",
        num_requests=len(requests),
        block_size=block_size,
        upstream_url=f"{UPSTREAM_URL} :: {UPSTREAM_PATH}",
        upstream_sha256=sha,
        transformation=transformation,
        notes=(
            "Re-derived from upstream per falsifier F4. NOT the preprocessed CSV "
            "shipped with Vidur canary; see docs/workload-mooncake-f4.md for the "
            "differences and why they matter."
        ),
    )
    return requests, manifest
