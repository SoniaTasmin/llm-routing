"""Azure LLM inference trace loader — the cache-blind control.

``DECISIONS.md`` D-004 fixes the role of this trace: it supplies realistic
arrival and length distributions and **nothing else**. The public Azure traces
record no prompt content and no prefix identifiers, so no cache-hit or
prefix-sharing claim may be derived from them. That is not a limitation to work
around; it is the point. Azure is the **null condition** against which RQ1's
cache effects are contrasted.

This loader therefore refuses, by construction, to emit block hashes. The
manifest it writes declares ``prefix_structure="absent"``, and
``WorkloadManifest`` rejects any attempt to attach a non-zero realised sharing
rate to such a workload. Cache-blindness is an assertion someone made, checkable
in the file, rather than a field that happens to be empty.

Upstream: ``https://github.com/Azure/AzurePublicDataset`` —
``AzureLLMInferenceTrace_conv.csv`` and ``AzureLLMInferenceTrace_code.csv``
(2023 release). Columns::

    TIMESTAMP,ContextTokens,GeneratedTokens
    2023-11-16 18:14:32.0000000,1234,123
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..schema import WorkloadError, WorkloadManifest, WorkloadRequest

UPSTREAM_URL = "https://github.com/Azure/AzurePublicDataset"

_TS_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")


def _parse_ts(s: str) -> datetime:
    s = s.strip()
    # Azure writes 7 fractional digits; datetime accepts at most 6.
    if "." in s:
        head, frac = s.split(".", 1)
        s = f"{head}.{frac[:6]}"
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise WorkloadError(f"unparseable Azure timestamp: {s!r}")


def load_azure(
    path: str | Path,
    *,
    limit: Optional[int] = None,
    variant: str = "conv",
) -> tuple[list[WorkloadRequest], WorkloadManifest]:
    """Load an Azure LLM inference trace as a cache-blind workload.

    Args:
        path: ``AzureLLMInferenceTrace_conv.csv`` or ``..._code.csv``.
        limit: keep only the first N records.
        variant: ``"conv"`` or ``"code"``, recorded in the manifest name.

    Returns:
        Requests in arrival order with ``block_hash_ids=None``, and a manifest
        declaring ``prefix_structure="absent"``.
    """
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()

    rows = list(csv.DictReader(raw.decode().splitlines()))
    if not rows:
        raise WorkloadError(f"{path}: no rows")
    required = {"TIMESTAMP", "ContextTokens", "GeneratedTokens"}
    missing = required - set(rows[0].keys())
    if missing:
        raise WorkloadError(f"{path}: missing columns {sorted(missing)}")

    if limit is not None:
        rows = rows[:limit]

    t0 = _parse_ts(rows[0]["TIMESTAMP"])
    requests: list[WorkloadRequest] = []
    skipped = 0
    for i, row in enumerate(rows):
        prefill = int(row["ContextTokens"])
        decode = int(row["GeneratedTokens"])
        # The public trace contains a small number of zero-length rows. Dropping
        # them is recorded in the manifest rather than done silently, because a
        # changed request count changes every rate we later compute.
        if prefill < 1 or decode < 1:
            skipped += 1
            continue
        requests.append(
            WorkloadRequest(
                request_id=len(requests),
                arrival_s=(_parse_ts(row["TIMESTAMP"]) - t0).total_seconds(),
                num_prefill_tokens=prefill,
                num_decode_tokens=decode,
                block_hash_ids=None,   # cache-blind by construction
                block_size=None,
                session_id=None,
            )
        )

    transformation = (
        "TIMESTAMP -> arrival_s (seconds from first record); ContextTokens -> "
        "num_prefill_tokens; GeneratedTokens -> num_decode_tokens; NO prefix "
        "structure emitted."
    )
    if skipped:
        transformation += f" Dropped {skipped} rows with a zero-length prompt or completion."
    if limit is not None:
        transformation += f" Truncated to first {limit} rows."

    manifest = WorkloadManifest(
        name=f"azure-2023-{variant}",
        source="azure",
        prefix_structure="absent",
        num_requests=len(requests),
        block_size=None,
        upstream_url=UPSTREAM_URL,
        upstream_sha256=sha,
        transformation=transformation,
        realised_sharing=None,
        notes=(
            "CACHE-BLIND CONTROL (DECISIONS.md D-004). The Azure public traces "
            "carry no prompt content and no prefix identifiers. No cache-hit or "
            "prefix-sharing claim may be derived from this workload. Its purpose "
            "is realistic arrival and length distributions, and to serve as the "
            "null condition for RQ1."
        ),
    )
    return requests, manifest
