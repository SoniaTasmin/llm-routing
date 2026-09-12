#!/usr/bin/env python3
"""Convert a unified workload into the CSV Vidur canary's TraceRequestGenerator reads.

Columns, per `vidur/request_generator/trace_request_generator.py`:
    arrived_at, num_prefill_tokens, num_decode_tokens, block_hash_ids,
    block_size, session_id
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
from workload.schema import read_workload          # noqa: E402
from workload.vidur_adapter import to_vidur_hashes  # noqa: E402


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    reqs, man = read_workload(src)
    # Vidur does `session_id.astype(int)` unconditionally when the column exists,
    # so an empty cell raises IntCastingNaNError. Our Mooncake workload has no
    # session ids by decision (upstream has none and we decline to invent them),
    # and Vidur shims a MISSING column to None. So: omit the column entirely
    # rather than emit blanks. Absent means absent.
    has_sessions = any(r.session_id is not None for r in reqs)
    if has_sessions and not all(r.session_id is not None for r in reqs):
        raise SystemExit(
            "refusing to write a partially-populated session_id column: Vidur "
            "casts it to int unconditionally and would fail on the gaps"
        )
    # Vidur requires hashes over prompt+output; our canonical records are
    # prompt-only by design. The adapter appends request-unique placeholders,
    # which bounds the admission-time cache walk to complete prompt blocks by
    # construction. See src/workload/vidur_adapter.py.
    hash_lists, arep = to_vidur_hashes(reqs)

    cols = ["arrived_at", "num_prefill_tokens", "num_decode_tokens",
            "block_hash_ids", "block_size"] + (["session_id"] if has_sessions else [])
    with dst.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r, ids in zip(reqs, hash_lists):
            row = [r.arrival_s, r.num_prefill_tokens, r.num_decode_tokens,
                   json.dumps(ids), r.block_size]
            if has_sessions:
                row.append(r.session_id)
            w.writerow(row)
    print(f"{len(reqs)} requests -> {dst}  (block_size={man.block_size}, "
          f"session_id column {'written' if has_sessions else 'OMITTED - none exist'})")
    print(f"  {arep.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
