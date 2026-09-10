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
from workload.transforms import truncate_to_context_budget  # noqa: E402
from workload.sharing import measure_realised_sharing    # noqa: E402

OUT = ROOT / "workloads" / "derived"
DEFAULT_MOONCAKE = ROOT / ".spike/mooncake_upstream/repo/FAST25-release/traces/conversation_trace.jsonl"
DEFAULT_AZURE_DIR = ROOT / ".spike/azure"
D_PRIME_BUDGET = 65536   # D-008 provisional context budget
SEEDS = (1,)  # M5 raises this to >= 10 per PROJECT_SPEC.md 11


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mooncake", type=Path, default=DEFAULT_MOONCAKE)
    ap.add_argument("--azure-dir", type=Path, default=DEFAULT_AZURE_DIR)
    ap.add_argument("--synthetic-requests", type=int, default=4000)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    if args.mooncake.exists():
        # ---- native trace: IMMUTABLE, no filtering, no scaling, no truncation
        reqs, man = load_mooncake(args.mooncake)
        write_workload(OUT / "mooncake-conversation.jsonl", reqs, man)
        native_rep = measure_realised_sharing(reqs)
        print(f"mooncake-conversation           n={man.num_requests:>6}  {native_rep.summary()}")

        # ---- D' variant: context-budget truncation (D-008, PROVISIONAL)
        import copy
        tr, trep = truncate_to_context_budget(reqs, D_PRIME_BUDGET)
        trep_sharing = measure_realised_sharing(tr)
        tman = copy.deepcopy(man)
        tman.name = f"mooncake-conversation-trunc{D_PRIME_BUDGET}"
        tman.num_requests = len(tr)
        tman.realised_sharing = trep_sharing.realised_sharing
        tman.transformation = (
            man.transformation
            + f" THEN truncated to a {D_PRIME_BUDGET}-token context budget "
              "(D-008, provisional): prompts capped at budget minus output "
              "length; arrival times and output lengths preserved; block hashes "
              "truncated to surviving whole blocks."
        )
        tman.notes = (
            "PROVISIONAL D' VARIANT (D-008). Derived from the native trace, which "
            "remains available unmodified alongside it.\n"
            "ASSUMPTION (unvalidated): simulated with the shipped Vidur "
            "'meta-llama/Meta-Llama-3-8B' timing profile used as a PROXY for a "
            "Llama-3.1-8B-class model. The architectures match on every parameter "
            "determining FLOPs and KV bytes per token, which SUPPORTS the proxy "
            "but does not establish it. Whether additional profiling is required "
            "is for M3/M11 validation to determine.\n"
            f"Realised sharing rises from {native_rep.realised_sharing:.4f} "
            f"(native) to {trep_sharing.realised_sharing:.4f} because truncation "
            "keeps prompt heads, where reuse concentrates, and discards tails."
        )
        tman.extra = {
            "derived_from": "mooncake-conversation",
            "native_realised_sharing": round(native_rep.realised_sharing, 6),
            "sharing_delta_pp": round(
                100 * (trep_sharing.realised_sharing - native_rep.realised_sharing), 4
            ),
            "truncation": trep.as_dict(),
            "timing_proxy": {
                "profile_used": "meta-llama/Meta-Llama-3-8B (Vidur canary 25e0082)",
                "intended_model_class": "Llama-3.1-8B",
                "status": "UNVALIDATED PROXY",
                "validation_owner": "M3 profiling review / M11 E8 fidelity",
            },
            "gates_open": [
                "M4: end-to-end long-context run has not been performed",
                "M4: random-forest behaviour outside training range unverified",
                "M11: timing proxy unvalidated against real vLLM",
            ],
        }
        write_workload(
            OUT / f"mooncake-conversation-trunc{D_PRIME_BUDGET}.jsonl", tr, tman
        )
        print(f"mooncake-trunc{D_PRIME_BUDGET:<6}          n={tman.num_requests:>6}  "
              f"{trep_sharing.summary()}")
        print(f"    {trep.summary()}")
        print(f"    sharing delta vs native: "
              f"{100*(trep_sharing.realised_sharing-native_rep.realised_sharing):+.2f} pp")
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
