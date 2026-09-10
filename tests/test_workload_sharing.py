"""Realised-sharing measurement."""
import pytest

from workload.schema import WorkloadRequest
from workload.sharing import measure_realised_sharing


def mk(rid, ids, sess=None, bs=512):
    return WorkloadRequest(request_id=rid, arrival_s=float(rid),
                           num_prefill_tokens=len(ids) * bs, num_decode_tokens=8,
                           block_hash_ids=tuple(ids), block_size=bs, session_id=sess)


def test_no_sharing_is_zero():
    r = measure_realised_sharing([mk(0, [1, 2]), mk(1, [3, 4])])
    assert r.realised_sharing == 0.0
    assert r.unique_blocks == 4


def test_full_repeat_is_half():
    """Second request repeats the first: 2 of 4 blocks are reuse."""
    r = measure_realised_sharing([mk(0, [1, 2]), mk(1, [1, 2])])
    assert r.realised_sharing == 0.5
    assert r.reused_blocks == 2


def test_partial_prefix_counts_only_the_shared_head():
    r = measure_realised_sharing([mk(0, [1, 2, 3]), mk(1, [1, 2, 9])])
    assert r.reused_blocks == 2 and r.total_blocks == 6
    assert r.realised_sharing == pytest.approx(1 / 3)


def test_session_split_of_reuse():
    r = measure_realised_sharing([mk(0, [1, 2], sess=0), mk(1, [1, 2], sess=0),
                                  mk(2, [1, 2], sess=1)])
    assert r.within_session_blocks == 2 and r.cross_session_blocks == 2


def test_cache_blind_is_an_error_not_a_zero():
    """A cache-blind workload has no sharing to measure. Returning 0.0 would
    invite it being reported as a finding."""
    blind = WorkloadRequest(request_id=0, arrival_s=0.0, num_prefill_tokens=10,
                            num_decode_tokens=1)
    with pytest.raises(ValueError, match="cache-blind"):
        measure_realised_sharing([blind])


def test_mixed_block_sizes_rejected():
    with pytest.raises(ValueError, match="mixed block sizes"):
        measure_realised_sharing([mk(0, [1], bs=512), mk(1, [2], bs=16)])
