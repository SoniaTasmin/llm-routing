"""Profile auditor — the M1/M2 coverage checks, mechanised.

Three revisions of the F6 analysis carried wrong coverage numbers because they
were derived by hand: a column max read as joint coverage, rows conflated with
distinct points, and an aggregate taken across a TP column that was never
filtered. These tests pin the behaviour so the same class of error is caught by
CI rather than by a reviewer.
"""
import csv
import pytest

from workload.profile_audit import audit_attention_profile


def _write(tmp_path, rows):
    p = tmp_path / "attention.csv"
    cols = ["n_embd", "n_q_head", "n_kv_head", "block_size",
            "num_tensor_parallel_workers", "max_model_len", "batch_size",
            "prefill_chunk_size", "kv_cache_size", "is_prefill", "attention_backend"]
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            base = dict(n_embd=4096, n_q_head=32, n_kv_head=8, block_size=16,
                        num_tensor_parallel_workers=1, max_model_len=262144,
                        attention_backend="FLASHINFER")
            base.update(r)
            w.writerow(base)
    return p


def test_detects_when_the_tp_filter_would_empty_the_frame(tmp_path):
    """Vidur filters training rows by TP. Asking for a TP with no data leaves the
    predictor with nothing to fit, and the failure is otherwise silent."""
    p = _write(tmp_path, [dict(num_tensor_parallel_workers=8, batch_size=1,
                               prefill_chunk_size=0, kv_cache_size=32, is_prefill="False")])
    assert audit_attention_profile(p, tp=8).loadable
    assert not audit_attention_profile(p, tp=1).loadable


def test_detects_when_the_block_size_filter_would_empty_the_frame(tmp_path):
    """Gate G4: block_size is a filtered column, so 512 against 16-token
    profiles yields no training rows at all."""
    p = _write(tmp_path, [dict(block_size=16, batch_size=1, prefill_chunk_size=0,
                               kv_cache_size=32, is_prefill="False")])
    assert audit_attention_profile(p, block_size=16).loadable
    assert not audit_attention_profile(p, block_size=512).loadable


def test_rows_and_distinct_pairs_are_reported_separately(tmp_path):
    """Conflating these produced a wrong count in an earlier F6 revision."""
    dup = dict(batch_size=1, prefill_chunk_size=0, kv_cache_size=32, is_prefill="False")
    p = _write(tmp_path, [dup, dup, dict(dup, kv_cache_size=64)])
    a = audit_attention_profile(p)
    assert a.decode.rows == 3 and a.decode.distinct_pairs == 2


def test_coverage_is_judged_per_phase_not_by_a_column_maximum(tmp_path):
    """Prefill kv reaches far higher than decode kv. Taking the max over both
    phases is exactly the error that made an earlier revision claim 262,112."""
    p = _write(tmp_path, [
        dict(batch_size=1, prefill_chunk_size=4096, kv_cache_size=200000, is_prefill="True"),
        dict(batch_size=1, prefill_chunk_size=0, kv_cache_size=8192, is_prefill="False"),
    ])
    a = audit_attention_profile(p)
    assert a.prefill.max_kv == 200000
    assert a.decode.max_kv == 8192
    ok, why = a.covers_context(100000, 4096)
    assert not ok and "decode coverage stops" in why


def test_covers_context_accepts_a_request_inside_both_envelopes(tmp_path):
    p = _write(tmp_path, [
        dict(batch_size=1, prefill_chunk_size=4096, kv_cache_size=60000, is_prefill="True"),
        dict(batch_size=1, prefill_chunk_size=0, kv_cache_size=65536, is_prefill="False"),
    ])
    ok, why = audit_attention_profile(p).covers_context(64000, 4096)
    assert ok, why


def test_empty_profile_rejected(tmp_path):
    p = _write(tmp_path, [])
    with pytest.raises(ValueError, match="no rows"):
        audit_attention_profile(p)
