"""Adapter invariants — the no-future-information rule, and Vidur's contract.

The leakage these guard against is demonstrated, not hypothesised:
`experiments/m4_run_a/leakage_probe.py` measured an admission-time estimate of
64 tokens for a 32-token prompt when output hashes coincided with cached blocks.
"""
import pytest

from workload.schema import WorkloadError, WorkloadRequest
from workload.vidur_adapter import (
    OUTPUT_PLACEHOLDER_BASE, AdaptationReport, to_vidur_hashes,
)

BS = 16


def r(rid, prefill, decode, prompt_ids):
    return WorkloadRequest(rid, float(rid), prefill, decode, tuple(prompt_ids), BS)


def test_satisfies_vidurs_whole_sequence_contract():
    """vidur/entities/request.py asserts
    0 <= prefill + decode - block_size*len(hashes) < block_size."""
    for prefill, decode in [(32, 32), (2290, 316), (17, 1), (512, 3), (48, 17)]:
        req = r(0, prefill, decode, list(range(prefill // BS)))
        (ids,), _ = to_vidur_hashes([req])
        last = prefill + decode - BS * len(ids)
        assert 0 <= last < BS, f"contract violated for {(prefill, decode)}"


def test_prompt_identities_are_preserved_exactly():
    req = r(0, 64, 32, [11, 22, 33, 44])
    (ids,), _ = to_vidur_hashes([req])
    assert ids[:4] == [11, 22, 33, 44]


def test_everything_past_the_prompt_is_a_placeholder():
    """Including the block straddling the prompt/output boundary: its contents
    mix prompt and generated tokens, so its identity is unknown."""
    req = r(0, 40, 40, [1, 2])          # 2 complete prompt blocks; token 40 is mid-block
    (ids,), _ = to_vidur_hashes([req])
    assert ids[:2] == [1, 2]
    assert all(i >= OUTPUT_PLACEHOLDER_BASE for i in ids[2:])
    assert len(ids) == (40 + 40) // BS


def test_placeholders_never_collide_across_requests():
    """A collision would imply two requests share generated content we know
    nothing about."""
    reqs = [r(i, 64, 64, [1, 2, 3, 4]) for i in range(50)]
    lists, rep = to_vidur_hashes(reqs)
    ph = [i for ids in lists for i in ids if i >= OUTPUT_PLACEHOLDER_BASE]
    assert len(ph) == len(set(ph)) == rep.placeholder_blocks


def test_identical_prompts_share_prompt_blocks_but_not_output():
    """The invariant: same prompt -> same prompt ids; output stays private."""
    a, b = r(0, 64, 64, [1, 2, 3, 4]), r(1, 64, 64, [1, 2, 3, 4])
    (ia, ib), _ = to_vidur_hashes([a, b])
    assert ia[:4] == ib[:4]
    assert set(ia[4:]).isdisjoint(ib[4:])


def test_no_future_information_invariant():
    """A router walking the chain must stop at the prompt boundary. Placeholders
    are unique, so the first one is guaranteed absent from any shared pool: the
    longest achievable shared prefix is exactly the complete prompt blocks."""
    a, b = r(0, 64, 64, [1, 2, 3, 4]), r(1, 64, 64, [1, 2, 3, 4])
    (ia, ib), _ = to_vidur_hashes([a, b])
    shared = 0
    for x, y in zip(ia, ib):
        if x != y:
            break
        shared += 1
    assert shared == 64 // BS, "shared prefix must not extend past the prompt"
    assert shared * BS <= a.num_prefill_tokens


def test_output_placeholders_cannot_collide_with_prompt_ids():
    huge = OUTPUT_PLACEHOLDER_BASE
    with pytest.raises(WorkloadError, match="collides"):
        to_vidur_hashes([r(0, 32, 32, [huge, huge + 1])])


def test_schema_prevents_malformed_input_before_the_adapter_sees_it():
    """3 hashes for 4 complete prompt blocks never reaches the adapter: the
    schema rejects it at construction. The adapter keeps its own check as
    defence in depth for records built by other means."""
    with pytest.raises(WorkloadError, match="expected"):
        WorkloadRequest(0, 0.0, 64, 32, (1, 2, 3), BS)


def test_rejects_cache_blind_records():
    with pytest.raises(WorkloadError, match="cache-blind"):
        to_vidur_hashes([WorkloadRequest(0, 0.0, 64, 32)])


def test_decode_work_is_untouched():
    """The adapter changes cache identities only; the simulator must still be
    asked for the full requested decode."""
    req = r(0, 2290, 316, list(range(2290 // BS)))
    (ids,), _ = to_vidur_hashes([req])
    assert req.num_decode_tokens == 316 and req.num_prefill_tokens == 2290
    assert len(ids) == (2290 + 316) // BS
