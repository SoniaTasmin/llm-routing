#!/usr/bin/env python3
"""Run A input: a deterministic <=128-request subset of D' that fits 4,096 tokens.

Deterministic by construction: the first N requests, in arrival order, whose
prefill+decode fits the budget. No sampling, no seed, no ambiguity about which
requests were used.

This is an INTEGRATION CHECK input. It is not representative of D', and nothing
measured on it transfers to Llama-3.1-class or 65,536-token contexts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from workload.schema import read_workload, write_workload, WorkloadManifest  # noqa: E402
from workload.sharing import measure_realised_sharing                        # noqa: E402
from workload.transforms import expand_block_hashes                          # noqa: E402

SRC = ROOT / "workloads/derived/mooncake-conversation-trunc65536.jsonl"
OUT = ROOT / "experiments/m4_run_a/run_a_workload.jsonl"
BUDGET = 4096
MAX_REQUESTS = 128
TARGET_BLOCK_SIZE = 16


def main() -> int:
    src_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    reqs, man = read_workload(SRC)

    fitting = [r for r in reqs if r.total_tokens <= BUDGET][:MAX_REQUESTS]
    if not fitting:
        print("no requests fit the budget", file=sys.stderr)
        return 1

    expanded, erep = expand_block_hashes(fitting, TARGET_BLOCK_SIZE)
    sharing = measure_realised_sharing(expanded)

    out_man = WorkloadManifest(
        name=f"run-a-integration-check-{BUDGET}",
        source="mooncake",
        prefix_structure="present",
        num_requests=len(expanded),
        block_size=TARGET_BLOCK_SIZE,
        upstream_url=man.upstream_url,
        upstream_sha256=man.upstream_sha256,
        realised_sharing=sharing.realised_sharing,
        transformation=(
            f"{man.name} (sha256 {src_sha[:16]}...) -> first {MAX_REQUESTS} requests "
            f"in arrival order with prefill+decode <= {BUDGET} -> block hashes "
            f"expanded {man.block_size}->{TARGET_BLOCK_SIZE} (G4a)"
        ),
        notes=(
            "RUN A INTEGRATION-CHECK INPUT ONLY. Deliberately tiny and "
            "unrepresentative. Nothing measured on this workload is evidence "
            "about D' long-context feasibility or timing fidelity."
        ),
        extra={
            "source_artifact": str(SRC.relative_to(ROOT)),
            "source_sha256": src_sha,
            "budget_tokens": BUDGET,
            "expansion": erep.as_dict(),
        },
    )
    write_workload(OUT, expanded, out_man)

    print(f"source          : {SRC.name}")
    print(f"source sha256   : {src_sha}")
    print(f"requests        : {len(expanded)} (of {len(reqs)} in D')")
    print(f"max total tokens: {max(r.total_tokens for r in expanded)} (budget {BUDGET})")
    print(f"block_size      : {TARGET_BLOCK_SIZE}")
    print(f"{erep.summary()}")
    print(f"realised sharing: {100*sharing.realised_sharing:.2f}%")
    print(f"written         : {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
