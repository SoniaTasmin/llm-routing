"""Audit a Vidur attention profile for usability and coverage.

Runs on CPU against any `attention.csv` in Vidur's schema — the shipped one, or
one we produce at M3. It answers two questions that the M1/M2 audits showed are
easy to get wrong:

1. **Will Vidur actually load this?** `_load_attention_df`
   (`sklearn_execution_time_predictor.py`) filters training rows on model shape,
   `block_size` **and** `num_tensor_parallel_workers`. If any filter empties the
   frame the predictor has nothing to train on — and the failure is silent until
   a fit produces nonsense. This checks the filter yields rows.

2. **What is jointly covered?** A column maximum is not coverage. Prefill and
   decode have different envelopes, and the decode grid is pruned by an
   aggregate-token limit, so per-phase joint coverage is the only honest summary.

Reporting `(batch, kv)` *pairs* separately from *rows* is deliberate: the two
differ by repeated measurements, and conflating them produced a wrong count in
an earlier revision of the F6 analysis.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PhaseCoverage:
    rows: int
    distinct_pairs: int
    batch_sizes: list[int] = field(default_factory=list)
    max_kv_by_batch: dict[int, int] = field(default_factory=dict)
    max_chunk: int = 0
    max_kv: int = 0
    max_chunk_plus_kv: int = 0


@dataclass
class ProfileAudit:
    path: str
    total_rows: int
    tps_present: list[int]
    block_sizes: list[int]
    max_model_len: list[int]
    prefill: Optional[PhaseCoverage]
    decode: Optional[PhaseCoverage]
    tp: int
    block_size: int

    @property
    def loadable(self) -> bool:
        """Would Vidur's `_load_attention_df` filter yield any training rows?"""
        return (
            self.tp in self.tps_present
            and self.block_size in self.block_sizes
            and (self.prefill is not None or self.decode is not None)
        )

    def covers_context(self, total_tokens: int, chunk_size: int) -> tuple[bool, str]:
        """Can a request of `total_tokens` be simulated inside sampled coverage?

        Prefill: every chunk boundary 0, chunk, 2*chunk, ... must be a sampled
        kv value at that chunk size. Decode: the request's peak context must not
        exceed the decode envelope.
        """
        if self.decode is None or self.prefill is None:
            return False, "profile lacks one of the two phases"
        if total_tokens > self.decode.max_kv:
            return (
                False,
                f"decode coverage stops at {self.decode.max_kv:,} tokens; "
                f"{total_tokens:,} would require extrapolation",
            )
        if chunk_size > self.prefill.max_chunk:
            return (
                False,
                f"chunk {chunk_size} exceeds profiled max chunk "
                f"{self.prefill.max_chunk}",
            )
        if total_tokens > self.prefill.max_chunk_plus_kv:
            return (
                False,
                f"prefill chunk+kv reaches {self.prefill.max_chunk_plus_kv:,}, "
                f"short of {total_tokens:,}",
            )
        return True, "within sampled coverage"

    def report(self) -> str:
        lines = [
            f"profile: {self.path}",
            f"  total rows          : {self.total_rows:,}",
            f"  TPs present         : {self.tps_present}",
            f"  block_size present  : {self.block_sizes}",
            f"  max_model_len       : {self.max_model_len}",
            f"  filtering for TP={self.tp}, block_size={self.block_size} -> "
            f"{'LOADABLE' if self.loadable else 'EMPTY (predictor would have no training data)'}",
        ]
        for name, cov in (("prefill", self.prefill), ("decode", self.decode)):
            if cov is None:
                lines.append(f"  {name}: absent")
                continue
            lines.append(
                f"  {name}: {cov.rows:,} rows, {cov.distinct_pairs:,} distinct pairs "
                f"({cov.rows - cov.distinct_pairs:,} repeats), "
                f"{len(cov.batch_sizes)} batch sizes"
            )
            if name == "prefill":
                lines.append(
                    f"    max chunk={cov.max_chunk:,}  max kv={cov.max_kv:,}  "
                    f"max chunk+kv={cov.max_chunk_plus_kv:,}"
                )
            else:
                full = [b for b, k in cov.max_kv_by_batch.items() if k == cov.max_kv]
                lines.append(
                    f"    max kv={cov.max_kv:,}, reached at {len(full)} batch sizes "
                    f"(up to batch {max(full) if full else 0})"
                )
        return "\n".join(lines)


def audit_attention_profile(
    path: str | Path, *, tp: int = 1, block_size: int = 16
) -> ProfileAudit:
    rows = list(csv.DictReader(open(path)))
    if not rows:
        raise ValueError(f"{path}: no rows")

    tps = sorted({int(r["num_tensor_parallel_workers"]) for r in rows})
    bss = sorted({int(r["block_size"]) for r in rows})
    mml = sorted({int(r["max_model_len"]) for r in rows})

    sel = [
        r
        for r in rows
        if int(r["num_tensor_parallel_workers"]) == tp
        and int(r["block_size"]) == block_size
    ]

    def cov(subset, is_prefill: bool) -> Optional[PhaseCoverage]:
        if not subset:
            return None
        pairs = {
            (int(r["batch_size"]), int(r["kv_cache_size"]), int(r["prefill_chunk_size"]))
            for r in subset
        }
        by = defaultdict(int)
        for r in subset:
            b, k = int(r["batch_size"]), int(r["kv_cache_size"])
            by[b] = max(by[b], k)
        c = PhaseCoverage(
            rows=len(subset),
            distinct_pairs=len(pairs),
            batch_sizes=sorted(by),
            max_kv_by_batch=dict(by),
            max_kv=max(int(r["kv_cache_size"]) for r in subset),
        )
        if is_prefill:
            c.max_chunk = max(int(r["prefill_chunk_size"]) for r in subset)
            c.max_chunk_plus_kv = max(
                int(r["prefill_chunk_size"]) + int(r["kv_cache_size"]) for r in subset
            )
        return c

    pre = cov([r for r in sel if r["is_prefill"].lower() == "true"], True)
    dec = cov([r for r in sel if r["is_prefill"].lower() != "true"], False)

    return ProfileAudit(
        path=str(path),
        total_rows=len(rows),
        tps_present=tps,
        block_sizes=bss,
        max_model_len=mml,
        prefill=pre,
        decode=dec,
        tp=tp,
        block_size=block_size,
    )
