"""CLI for the profile auditor: `python -m workload.profile_audit_cli <csv>`."""
from __future__ import annotations

import argparse

from .profile_audit import audit_attention_profile


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit a Vidur attention profile.")
    ap.add_argument("path")
    ap.add_argument("--tp", type=int, default=1)
    ap.add_argument("--block-size", type=int, default=16)
    ap.add_argument("--require-context", type=int, default=None,
                    help="fail unless a request of this many total tokens is covered")
    ap.add_argument("--chunk", type=int, default=4096)
    args = ap.parse_args()

    a = audit_attention_profile(args.path, tp=args.tp, block_size=args.block_size)
    print(a.report())
    if not a.loadable:
        print("\nFAIL: Vidur's _load_attention_df filter would yield no training rows.")
        return 1
    if args.require_context is not None:
        ok, why = a.covers_context(args.require_context, args.chunk)
        print(f"\ncovers {args.require_context:,} tokens at chunk {args.chunk}: {ok} — {why}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
