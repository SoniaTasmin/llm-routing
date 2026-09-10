"""Loader and generator correctness — only what establishes that they are right."""
import math
import pytest

from workload.loaders.mooncake import load_mooncake, verify_block_size, MOONCAKE_BLOCK_SIZE
from workload.loaders.azure import load_azure
from workload.loaders.synthetic import FROZEN_PHI_SWEEP, generate_synthetic
from workload.schema import WorkloadError
from workload.sharing import measure_realised_sharing


# ---------------------------------------------------------------- synthetic

@pytest.mark.parametrize("phi", FROZEN_PHI_SWEEP)
def test_realised_sharing_tracks_nominal_phi(phi):
    reqs, man = generate_synthetic(phi=phi, num_requests=4000, seed=1)
    assert man.nominal_phi == phi
    measured = measure_realised_sharing(reqs).realised_sharing
    assert man.realised_sharing == pytest.approx(measured)
    if phi == 0.0:
        assert measured == 0.0
    else:
        # Realised sits below nominal by construction (session openers inherit
        # nothing) but must track it, not drift arbitrarily.
        # Realised must sit below nominal (session openers inherit nothing)
        # but track it closely. The 0.05 band is what the growing-conversation
        # construction achieves; an earlier construction managed only 0.69 for a
        # nominal 0.9 and this assertion is what caught it.
        assert 0.0 < measured < phi
        assert measured > phi - 0.05, (
            f"phi={phi}: realised {measured:.3f} fell too far below nominal"
        )


def test_phi_is_monotonic():
    got = [
        generate_synthetic(phi=p, num_requests=3000, seed=7)[1].realised_sharing
        for p in FROZEN_PHI_SWEEP
    ]
    assert got == sorted(got), f"realised sharing not monotonic in phi: {got}"


def test_same_seed_same_workload():
    a, ma = generate_synthetic(phi=0.5, num_requests=500, seed=42)
    b, mb = generate_synthetic(phi=0.5, num_requests=500, seed=42)
    assert a == b and ma.realised_sharing == mb.realised_sharing


def test_different_seed_different_workload():
    a, _ = generate_synthetic(phi=0.5, num_requests=500, seed=1)
    b, _ = generate_synthetic(phi=0.5, num_requests=500, seed=2)
    assert a != b


def test_generator_emits_hashes_because_vidur_cannot():
    """canary's fallback hashing path raises TypeError; we must supply hashes."""
    reqs, _ = generate_synthetic(phi=0.5, num_requests=50, seed=3)
    assert all(r.block_hash_ids is not None for r in reqs)


def test_arrivals_are_ordered():
    reqs, _ = generate_synthetic(phi=0.25, num_requests=500, seed=5)
    assert all(a.arrival_s <= b.arrival_s for a, b in zip(reqs, reqs[1:]))


def test_rejects_out_of_range_phi():
    with pytest.raises(WorkloadError):
        generate_synthetic(phi=1.5, num_requests=10, seed=0)


# ---------------------------------------------------------------- mooncake

def test_mooncake_block_size_verifier(tmp_path):
    import json
    good = tmp_path / "g.jsonl"
    good.write_text("\n".join(json.dumps(
        {"timestamp": i * 100, "input_length": 1024, "output_length": 64,
         "hash_ids": [i, i + 1]}) for i in range(5)))
    reqs, man = load_mooncake(good)
    assert len(reqs) == 5 and man.prefix_structure == "present"
    assert man.block_size == MOONCAKE_BLOCK_SIZE
    assert reqs[0].arrival_s == 0.0 and reqs[1].arrival_s == 0.1

    bad = tmp_path / "b.jsonl"
    bad.write_text(json.dumps(
        {"timestamp": 0, "input_length": 1024, "output_length": 64,
         "hash_ids": [1, 2, 3, 4, 5, 6]}))
    with pytest.raises(WorkloadError, match="does not describe this trace"):
        load_mooncake(bad)


def test_mooncake_does_not_invent_sessions(tmp_path):
    import json
    p = tmp_path / "m.jsonl"
    p.write_text(json.dumps({"timestamp": 0, "input_length": 1024,
                             "output_length": 64, "hash_ids": [0, 1]}))
    reqs, _ = load_mooncake(p)
    assert reqs[0].session_id is None, (
        "upstream Mooncake has no session field; inventing one would mean our "
        "sticky-routing results depend on a grouping we made up"
    )


# ---------------------------------------------------------------- azure

def test_azure_is_cache_blind_by_construction(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("TIMESTAMP,ContextTokens,GeneratedTokens\n"
                 "2023-11-16 18:14:32.0000000,1234,123\n"
                 "2023-11-16 18:14:33.5000000,222,45\n")
    reqs, man = load_azure(p)
    assert man.prefix_structure == "absent" and man.cache_blind
    assert man.realised_sharing is None
    assert all(r.block_hash_ids is None for r in reqs)
    assert reqs[1].arrival_s == pytest.approx(1.5)


def test_azure_drops_degenerate_rows_and_says_so(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("TIMESTAMP,ContextTokens,GeneratedTokens\n"
                 "2023-11-16 18:14:32.0000000,0,123\n"
                 "2023-11-16 18:14:33.0000000,10,5\n")
    reqs, man = load_azure(p)
    assert len(reqs) == 1
    assert "Dropped 1 rows" in man.transformation


def test_azure_rejects_wrong_columns(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("foo,bar\n1,2\n")
    with pytest.raises(WorkloadError, match="missing columns"):
        load_azure(p)
