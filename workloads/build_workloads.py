#!/usr/bin/env python3
"""Regenerate every derived workload from its source.

    python workloads/build_workloads.py [--mooncake PATH] [--azure-dir DIR]

Writes JSONL + a `.manifest.json` sidecar per workload into `workloads/derived/`.
The JSONL is git-ignored (regenerable); the manifests are committed, because they
carry the upstream SHA-256 and the *measured* realised sharing that results are
allowed to cite.

Sources are not vendored — they are large and they are other people's data. Fetch
them per `REPRODUCE.md` §3b.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from workload.loaders.azure import load_azure            # noqa: E402
from workload.loaders.mooncake import load_mooncake      # noqa: E402
from workload.loaders.synthetic import (                 # noqa: E402
    FROZEN_PHI_SWEEP, generate_synthetic,
)
from workload.schema import write_workload               # noqa: E402
from workload.sharing import measure_realised_sharing    # noqa: E402

OUT = ROOT / "workloads" / "derived"
DEFAULT_MOONCAKE = ROOT / ".spike/mooncake_upstream/repo/FAST25-release/traces/conversation_trace.jsonl"
DEFAULT_AZURE_DIR = ROOT / ".spike/azure"
SEEDS = (1,)  # M5 raises this to >= 10 per PROJECT_SPEC.md 11


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mooncake", type=Path, default=DEFAULT_MOONCAKE)
    ap.add_argument("--azure-dir", type=Path, default=DEFAULT_AZURE_DIR)
    ap.add_argument("--synthetic-requests", type=int, default=4000)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    if args.mooncake.exists():
        reqs, man = load_mooncake(args.mooncake)
        # No filtering, no scaling: falsifier F6 is an OPEN user decision.
        # See docs/workload-mooncake-context-length-f6.md.
        write_workload(OUT / "mooncake-conversation.jsonl", reqs, man)
        rep = measure_realised_sharing(reqs)
        print(f"mooncake-conversation      n={man.num_requests:>6}  {rep.summary()}")
    else:
        print(f"SKIP mooncake: {args.mooncake} not found (see REPRODUCE.md 3b)")

    for variant in ("conv", "code"):
        src = args.azure_dir / f"AzureLLMInferenceTrace_{variant}.csv"
        if not src.exists():
            print(f"SKIP azure-{variant}: {src} not found (see REPRODUCE.md 3b)")
            continue
        reqs, man = load_azure(src, variant=variant)
        write_workload(OUT / f"azure-2023-{variant}.jsonl", reqs, man)
        print(f"azure-2023-{variant:<14} n={man.num_requests:>6}  "
              f"CACHE-BLIND (no sharing may be reported)")

    for seed in SEEDS:
        for phi in FROZEN_PHI_SWEEP:
            reqs, man = generate_synthetic(
                phi=phi, num_requests=args.synthetic_requests, seed=seed
            )
            write_workload(OUT / f"synthetic-phi{phi:g}-seed{seed}.jsonl", reqs, man)
            print(f"synthetic phi={phi:<5} seed={seed}  n={man.num_requests:>6}  "
                  f"nominal={phi:<5} MEASURED realised={man.realised_sharing:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
