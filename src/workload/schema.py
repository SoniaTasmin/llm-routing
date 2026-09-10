"""Unified workload record format.

Every workload this project simulates — Mooncake, Azure, or synthetic — is
converted to the one record type defined here before anything downstream sees
it. Routers, the simulator adapter and the analysis harness read this schema and
nothing else, so that a policy cannot accidentally behave differently on one
source because it saw a differently-shaped record.

Design rules, each of which exists because of something the M1 spike found:

1. **Cache-blindness is declared, never inferred.** A workload without prefix
   structure sets ``prefix_structure="absent"`` in its manifest. Downstream code
   must branch on that flag, not on ``block_hash_ids is None``. Azure traces
   carry no prompt content (``DECISIONS.md`` D-004), and a missing field could
   equally mean "we forgot to populate it" — which is exactly the kind of silent
   ambiguity that would let a cache-hit number be reported for a trace that
   cannot have one.

2. **Block hashes are supplied by us, never computed by the simulator.** Vidur
   ``canary``'s fallback hashing path is broken (confirmed ``TypeError``, see
   ``simulator/vendor/PROVENANCE.md``). Every workload that claims prefix
   structure must therefore carry explicit ``block_hash_ids``.

3. **Prefix semantics are chained.** ``block_hash_ids[i]`` identifies the whole
   prefix up to and including block ``i``, not just block ``i``'s own tokens.
   Two requests share a prefix of ``k`` blocks iff their id lists agree on the
   first ``k`` entries. This matches vLLM's block-pool construction and
   Mooncake's own ``hash_ids``.

4. **Realised sharing is measured, never assumed.** ``PROJECT_SPEC.md`` §7
   requires the synthetic generator to report the sharing it actually produced
   alongside the nominal phi it was asked for. See ``workload.sharing``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, Literal, Optional, Sequence

SCHEMA_VERSION = "1.0"

PrefixStructure = Literal["present", "absent"]


class WorkloadError(ValueError):
    """Raised when a workload record or manifest violates the schema."""


@dataclass(frozen=True)
class WorkloadRequest:
    """One request, in the only format the rest of the project consumes.

    Attributes:
        request_id: Stable identifier, unique within a workload. Assigned by the
            loader in arrival order.
        arrival_s: Arrival time in **seconds** from the start of the trace.
            Seconds, not milliseconds or nanoseconds, because the three sources
            disagree and picking one here is cheaper than remembering which.
        num_prefill_tokens: Prompt length in tokens. Must be >= 1.
        num_decode_tokens: Generated length in tokens. Must be >= 1.
        block_hash_ids: Chained prefix-block ids covering the **prefill** tokens
            only, or ``None`` for a cache-blind workload. Decode tokens are
            excluded deliberately: a request's generated tokens are not known to
            a router at admission time, so including them would leak future
            information into a routing decision.
        block_size: Tokens per block hash. Required iff ``block_hash_ids`` is
            set.
        session_id: Conversation grouping, or ``None`` if the source does not
            provide one. **Never invented by a loader** — see
            ``docs/workload-schema.md`` on why Mooncake's shipped ``session_id``
            is not adopted.
    """

    request_id: int
    arrival_s: float
    num_prefill_tokens: int
    num_decode_tokens: int
    block_hash_ids: Optional[tuple[int, ...]] = None
    block_size: Optional[int] = None
    session_id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.num_prefill_tokens < 1:
            raise WorkloadError(
                f"request {self.request_id}: num_prefill_tokens must be >= 1, "
                f"got {self.num_prefill_tokens}"
            )
        if self.num_decode_tokens < 1:
            raise WorkloadError(
                f"request {self.request_id}: num_decode_tokens must be >= 1, "
                f"got {self.num_decode_tokens}"
            )
        if self.arrival_s < 0:
            raise WorkloadError(
                f"request {self.request_id}: arrival_s must be >= 0, "
                f"got {self.arrival_s}"
            )
        if (self.block_hash_ids is None) != (self.block_size is None):
            raise WorkloadError(
                f"request {self.request_id}: block_hash_ids and block_size must "
                "be supplied together or not at all"
            )
        if self.block_hash_ids is not None:
            expected = self.num_prefill_tokens // self.block_size
            if len(self.block_hash_ids) != expected:
                raise WorkloadError(
                    f"request {self.request_id}: expected "
                    f"{expected} block hashes for {self.num_prefill_tokens} "
                    f"prefill tokens at block_size {self.block_size}, got "
                    f"{len(self.block_hash_ids)}. Only WHOLE blocks are hashed; "
                    "the trailing partial block is always recomputed."
                )

    @property
    def total_tokens(self) -> int:
        return self.num_prefill_tokens + self.num_decode_tokens

    def to_json(self) -> dict:
        d = asdict(self)
        if self.block_hash_ids is not None:
            d["block_hash_ids"] = list(self.block_hash_ids)
        return d

    @classmethod
    def from_json(cls, d: dict) -> "WorkloadRequest":
        bh = d.get("block_hash_ids")
        return cls(
            request_id=int(d["request_id"]),
            arrival_s=float(d["arrival_s"]),
            num_prefill_tokens=int(d["num_prefill_tokens"]),
            num_decode_tokens=int(d["num_decode_tokens"]),
            block_hash_ids=tuple(bh) if bh is not None else None,
            block_size=d.get("block_size"),
            session_id=d.get("session_id"),
        )


@dataclass
class WorkloadManifest:
    """Provenance and declared properties of one workload.

    Written beside every workload file. Exists so that a result can always be
    traced back to the exact bytes and transformation that produced it, and so
    that cache-blindness is an assertion someone made rather than a field
    someone forgot.
    """

    name: str
    source: str
    prefix_structure: PrefixStructure
    num_requests: int
    schema_version: str = SCHEMA_VERSION
    block_size: Optional[int] = None
    upstream_url: Optional[str] = None
    upstream_commit: Optional[str] = None
    upstream_sha256: Optional[str] = None
    transformation: str = ""
    nominal_phi: Optional[float] = None
    realised_sharing: Optional[float] = None
    seed: Optional[int] = None
    notes: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.prefix_structure not in ("present", "absent"):
            raise WorkloadError(
                f"prefix_structure must be 'present' or 'absent', "
                f"got {self.prefix_structure!r}"
            )
        if self.prefix_structure == "present" and self.block_size is None:
            raise WorkloadError(
                "a workload declaring prefix_structure='present' must state its "
                "block_size"
            )
        if self.prefix_structure == "absent" and self.realised_sharing not in (None, 0.0):
            raise WorkloadError(
                "a cache-blind workload cannot report a non-zero realised "
                "sharing rate — see DECISIONS.md D-004"
            )

    @property
    def cache_blind(self) -> bool:
        return self.prefix_structure == "absent"


def write_workload(
    path: str | Path,
    requests: Sequence[WorkloadRequest],
    manifest: WorkloadManifest,
) -> Path:
    """Write a workload as JSONL plus a sidecar ``.manifest.json``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if manifest.num_requests != len(requests):
        raise WorkloadError(
            f"manifest says {manifest.num_requests} requests, got {len(requests)}"
        )
    with path.open("w") as f:
        for r in requests:
            f.write(json.dumps(r.to_json()) + "\n")
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    with manifest_path.open("w") as f:
        json.dump(asdict(manifest), f, indent=2)
        f.write("\n")
    return path


def read_workload(path: str | Path) -> tuple[list[WorkloadRequest], WorkloadManifest]:
    """Read a workload and its manifest, validating every record."""
    path = Path(path)
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    if not manifest_path.exists():
        raise WorkloadError(
            f"no manifest beside {path}. A workload without provenance is not "
            "usable in this project."
        )
    with manifest_path.open() as f:
        manifest = WorkloadManifest(**json.load(f))
    requests = [WorkloadRequest.from_json(json.loads(l)) for l in path.open() if l.strip()]
    if len(requests) != manifest.num_requests:
        raise WorkloadError(
            f"{path}: manifest says {manifest.num_requests} requests, file has "
            f"{len(requests)}"
        )
    if manifest.prefix_structure == "absent" and any(
        r.block_hash_ids is not None for r in requests
    ):
        raise WorkloadError(
            f"{path}: manifest declares the workload cache-blind but some "
            "records carry block hashes"
        )
    if manifest.prefix_structure == "present" and any(
        r.block_hash_ids is None for r in requests
    ):
        raise WorkloadError(
            f"{path}: manifest declares prefix structure present but some "
            "records lack block hashes"
        )
    return requests, manifest


def iter_workload(path: str | Path) -> Iterator[WorkloadRequest]:
    """Stream a workload without holding it all in memory."""
    with Path(path).open() as f:
        for line in f:
            if line.strip():
                yield WorkloadRequest.from_json(json.loads(line))
