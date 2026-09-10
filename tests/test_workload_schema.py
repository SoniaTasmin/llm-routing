"""Schema invariants. These encode decisions, so a failure here is a research
problem, not just a bug."""
import json
import pytest

from workload.schema import (
    WorkloadError, WorkloadManifest, WorkloadRequest, read_workload, write_workload,
)


def _req(**kw):
    base = dict(request_id=0, arrival_s=0.0, num_prefill_tokens=1024,
                num_decode_tokens=64, block_hash_ids=(1, 2), block_size=512)
    base.update(kw)
    return WorkloadRequest(**base)


def test_hashes_must_cover_whole_blocks_only():
    _req(num_prefill_tokens=1024, block_hash_ids=(1, 2))          # exactly 2
    _req(num_prefill_tokens=1200, block_hash_ids=(1, 2))          # 2 whole + partial
    with pytest.raises(WorkloadError, match="expected"):
        _req(num_prefill_tokens=1024, block_hash_ids=(1, 2, 3))   # too many


def test_block_size_and_hashes_travel_together():
    with pytest.raises(WorkloadError, match="together"):
        _req(block_size=None)
    with pytest.raises(WorkloadError, match="together"):
        _req(block_hash_ids=None)


def test_rejects_degenerate_lengths():
    with pytest.raises(WorkloadError):
        _req(num_prefill_tokens=0, block_hash_ids=(), block_size=512)
    with pytest.raises(WorkloadError):
        _req(num_decode_tokens=0)
    with pytest.raises(WorkloadError):
        _req(arrival_s=-1.0)


def test_cache_blind_manifest_cannot_claim_sharing():
    """DECISIONS.md D-004: no cache-hit claim may come from a cache-blind trace."""
    WorkloadManifest(name="a", source="azure", prefix_structure="absent",
                     num_requests=1)
    with pytest.raises(WorkloadError, match="cache-blind"):
        WorkloadManifest(name="a", source="azure", prefix_structure="absent",
                         num_requests=1, realised_sharing=0.3)


def test_prefix_present_manifest_needs_block_size():
    with pytest.raises(WorkloadError, match="block_size"):
        WorkloadManifest(name="a", source="synthetic",
                         prefix_structure="present", num_requests=1)


def test_roundtrip_preserves_records(tmp_path):
    reqs = [_req(request_id=i, arrival_s=float(i)) for i in range(5)]
    man = WorkloadManifest(name="t", source="synthetic", prefix_structure="present",
                           num_requests=5, block_size=512)
    p = write_workload(tmp_path / "w.jsonl", reqs, man)
    back, man2 = read_workload(p)
    assert back == reqs
    assert man2.block_size == 512


def test_manifest_is_mandatory(tmp_path):
    p = tmp_path / "orphan.jsonl"
    p.write_text(json.dumps(_req().to_json()) + "\n")
    with pytest.raises(WorkloadError, match="no manifest"):
        read_workload(p)


def test_manifest_and_file_must_agree(tmp_path):
    reqs = [_req(request_id=i) for i in range(3)]
    man = WorkloadManifest(name="t", source="synthetic", prefix_structure="present",
                           num_requests=3, block_size=512)
    p = write_workload(tmp_path / "w.jsonl", reqs, man)
    p.write_text("")                      # truncate the data, leave the manifest
    with pytest.raises(WorkloadError, match="manifest says"):
        read_workload(p)


def test_declared_cache_blind_file_may_not_carry_hashes(tmp_path):
    reqs = [_req()]
    man = WorkloadManifest(name="t", source="azure", prefix_structure="absent",
                           num_requests=1)
    p = tmp_path / "w.jsonl"
    write_workload(p, reqs, man)
    with pytest.raises(WorkloadError, match="cache-blind but some"):
        read_workload(p)
