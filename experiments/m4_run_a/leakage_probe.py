#!/usr/bin/env python3
"""Regression case: can a request's FUTURE-OUTPUT hashes change its
admission-time cache estimate?

Probes the vendored Vidur canary directly. Run with the canary venv, which has
Vidur's dependencies:

    cd .spike/vidur-canary && ./.venv/bin/python \\
        ../../experiments/m4_run_a/leakage_probe.py

Two requests share an identical prompt and differ ONLY in the hashes covering
tokens the model has not generated yet. If their admission-time
`get_cached_prefill_length` differs, a router that consults it is being informed
by the request's own future output.
"""
import sys

from vidur.entities.request import Request
from vidur.kv_cache.replica_kv_cache_manager import ReplicaKVCacheManager

BS = 16
PROMPT = 2 * BS          # 2 complete prompt blocks
OUTPUT = 2 * BS          # 2 output blocks


def mgr():
    return ReplicaKVCacheManager(
        block_size=BS, num_gpu_blocks=256, enable_caching=True,
        caching_hash_algo="builtin", num_preallocate_tokens=0,
    )


def req(hashes):
    return Request(arrived_at=0.0, num_prefill_tokens=PROMPT,
                   num_decode_tokens=OUTPUT, block_hash_ids=list(hashes),
                   block_size=BS)


def main() -> int:
    m = mgr()

    # An EARLIER conversation: same prompt, and its output has been generated
    # and cached. This is the ordinary case the prefix cache exists to exploit.
    prior = req([101, 102, 201, 202])
    blocks, n = m.get_computed_blocks(prior)
    m.allocate_slots(prior, PROMPT + OUTPUT, blocks)
    prior.set_num_processed_tokens(PROMPT + OUTPUT) if hasattr(
        prior, "set_num_processed_tokens") else None
    # Cache everything the prior request computed, output included.
    m.allocate_slots(prior, 0, []) if False else None
    print(f"prior request cached; pool usage = {m.usage:.3f}")

    # Two NEW requests, identical prompts, differing only in output hashes.
    same_output = req([101, 102, 201, 202])   # output coincides with the prior
    diff_output = req([101, 102, 901, 902])   # output differs; unique ids

    _, n_same = m.get_computed_blocks(same_output)
    _, n_diff = m.get_computed_blocks(diff_output)

    print()
    print(f"  prompt tokens                         : {PROMPT}")
    print(f"  cached-prefill estimate, SAME output  : {n_same}")
    print(f"  cached-prefill estimate, DIFFERENT out: {n_diff}")
    print()
    if n_same != n_diff:
        print("LEAKAGE CONFIRMED: changing only future-output hashes changed the")
        print("admission-time cache estimate that B3/B4 route on.")
        rc = 1
    else:
        print("No difference observed at this point on the path.")
        rc = 0
    if n_same > PROMPT or n_diff > PROMPT:
        print(f"ALSO: estimate EXCEEDS the prompt length ({PROMPT}); output tokens")
        print("are being credited as cached prompt tokens.")
        rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
