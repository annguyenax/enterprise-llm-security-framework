"""Deterministic in-sample test doubles for A03/A04/A05.

No network, no live app servers, no real providers. Every double mimics
the fail-closed behavior the frozen spec requires: timeouts and faults
become BLOCKED/ERROR results with a reason, never empty successes, never
unauthorized chunks, never downstream calls after a failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LABEL = "mock/in-sample"


class RetrievalTimeout(Exception):
    """In-sample retrieval exceeded its deadline."""


class RetrievalFault(Exception):
    """Injected in-sample retrieval failure."""


class EmbeddingFault(Exception):
    """Injected in-sample embedding failure."""


class ACLFault(Exception):
    """Injected in-sample authorization failure."""


class ProviderTimeout(Exception):
    """In-sample provider double exceeded its deadline."""


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    owner: str


@dataclass(frozen=True)
class BlockedResult:
    ok: bool
    status: str  # "success" | "BLOCKED" | "ERROR"
    reason: str
    chunks: tuple = ()
    provider_called: bool = False
    label: str = LABEL


@dataclass(frozen=True)
class ProviderErrorRecord:
    ok: bool
    status: str
    reason: str
    has_response: bool
    counted_as_success: bool
    latency_sample: object
    availability: str
    label: str = LABEL


class RetrievalDouble:
    """In-memory retrieval with timeout/fault injection."""

    def __init__(self, chunks: tuple[Chunk, ...] = ()) -> None:
        self._chunks = tuple(chunks)
        self._fault: str | None = None
        self._staged: tuple[Chunk, ...] = ()
        self.calls: list[dict] = []

    def inject(self, fault: str | None) -> None:
        assert fault in (None, "timeout", "fault")
        self._fault = fault

    def stage_partial(self, chunks: tuple[Chunk, ...]) -> None:
        """Stage chunks that a timeout must still drop (no partial leak)."""
        self._staged = tuple(chunks)

    def search(self, query: str, timeout_ms: int = 100) -> list[Chunk]:
        # Staged chunks are in the pending result set. A timeout/fault must
        # drop them; a success path includes them so a leak would be visible.
        pending = list(self._chunks) + list(self._staged)
        self.calls.append({"query": query, "timeout_ms": timeout_ms})
        if self._fault == "timeout":
            self._staged = ()
            raise RetrievalTimeout(
                f"in-sample retrieval exceeded timeout_ms={timeout_ms}")
        if self._fault == "fault":
            self._staged = ()
            raise RetrievalFault("in-sample retrieval fault injected")
        self._staged = ()
        return pending


class ProviderDouble:
    """Mock provider double; never a real LLM; never touches the network."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._timeout = False

    def inject_timeout(self) -> None:
        self._timeout = True

    def generate(self, prompt: str, timeout_ms: int = 100) -> dict:
        self.calls.append({"prompt": prompt, "timeout_ms": timeout_ms})
        if self._timeout:
            raise ProviderTimeout(
                f"in-sample provider double exceeded timeout_ms={timeout_ms}")
        return {"text": "in-sample mock response", "is_real": False,
                "label": LABEL}


class EmbeddingDouble:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self._fault = False

    def inject_fault(self) -> None:
        self._fault = True

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._fault:
            raise EmbeddingFault("in-sample embedding fault injected")
        return [[0.25] * 4 for _ in texts]


class ACLDouble:
    """Authorization double. Unknown verdicts (None) deny; faults raise."""

    def __init__(self, grants: dict[tuple[str, str], bool] | None = None,
                 script: list[str] | None = None) -> None:
        self._grants = dict(grants or {})
        self._script = list(script or [])
        self.calls: list[tuple[str, str]] = []

    def check(self, user: str, chunk_id: str) -> bool | None:
        self.calls.append((user, chunk_id))
        if self._script:
            step = self._script.pop(0)
            if step == "fault":
                raise ACLFault("in-sample ACL fault injected")
            if step == "deny":
                return False
            if step == "unknown":
                return None
            return True
        return self._grants.get((user, chunk_id))

    def inject_fault(self) -> None:
        self._script.append("fault")


class ChunkCacheDouble:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Chunk, ...]] = {}

    def put(self, query: str, chunks: tuple[Chunk, ...]) -> None:
        self._store[query] = tuple(chunks)

    def get(self, query: str) -> tuple[Chunk, ...] | None:
        hit = self._store.get(query)
        return tuple(hit) if hit is not None else None


class GuardOutcomeRecorder:
    """Counts guard successes; timeouts/errors must never increment it."""

    def __init__(self) -> None:
        self.outcomes: list[str] = []

    def record(self, outcome: str) -> None:
        self.outcomes.append(outcome)

    @property
    def guard_successes(self) -> int:
        return sum(1 for o in self.outcomes if o == "guard-success")


class LatencyRecorder:
    """Collects success-scope latency samples only."""

    def __init__(self) -> None:
        self.samples: list[float] = []


def guarded_retrieve(retrieval: RetrievalDouble, query: str,
                     timeout_ms: int = 100) -> BlockedResult:
    """Retrieval stage: timeout/fault -> BLOCKED with reason, zero chunks."""
    try:
        chunks = retrieval.search(query, timeout_ms=timeout_ms)
    except RetrievalTimeout as exc:
        return BlockedResult(False, "BLOCKED",
                             f"retrieval timeout, fail-closed ({LABEL}): {exc}")
    except RetrievalFault as exc:
        return BlockedResult(False, "BLOCKED",
                             f"retrieval fault, fail-closed ({LABEL}): {exc}")
    return BlockedResult(True, "success", "", tuple(chunks))


def retrieve_then_generate(retrieval: RetrievalDouble, provider: ProviderDouble,
                           query: str, timeout_ms: int = 100) -> BlockedResult:
    """Two-stage pipeline: the provider is contacted only after retrieval
    succeeds, so a retrieval timeout provably causes no downstream call."""
    first = guarded_retrieve(retrieval, query, timeout_ms=timeout_ms)
    if not first.ok:
        return BlockedResult(False, first.status, first.reason, (),
                             provider_called=False)
    provider.generate(query, timeout_ms=timeout_ms)
    return BlockedResult(True, "success", "", first.chunks,
                         provider_called=True)


def guarded_generate(provider: ProviderDouble, prompt: str, *,
                     outcomes: GuardOutcomeRecorder,
                     latency: LatencyRecorder,
                     timeout_ms: int = 100) -> dict | ProviderErrorRecord:
    """Provider stage: double timeout -> ERROR record, never a success,
    never a latency sample, never availability evidence."""
    try:
        response = provider.generate(prompt, timeout_ms=timeout_ms)
    except ProviderTimeout as exc:
        outcomes.record("BLOCK")
        return ProviderErrorRecord(
            ok=False, status="ERROR",
            reason=f"provider double timeout, fail-closed ({LABEL}): {exc}",
            has_response=False, counted_as_success=False,
            latency_sample=None,
            availability="unknown: an in-sample double error proves nothing "
                         "about real provider availability")
    outcomes.record("guard-success")
    latency.samples.append(1.0)  # In-sample unit sample, success scope only.
    return {"ok": True, "status": "success", "response": response,
            "label": LABEL}


def secure_retrieve(retrieval: RetrievalDouble, embedding: EmbeddingDouble,
                    acl: ACLDouble, cache: ChunkCacheDouble, *,
                    query: str, user: str,
                    timeout_ms: int = 100) -> BlockedResult:
    """Fail-closed pipeline: any retrieval/embedding/ACL fault, or any
    undefined authorization verdict, yields BLOCKED with ZERO chunks.

    Cached candidates are re-checked against the ACL on every call, so a
    cache hit can neither bypass a fault nor leak an unauthorized chunk.
    Partial progress (retrieved chunks, earlier grants) is dropped as soon
    as a later stage fails.
    """
    cached = cache.get(query)
    if cached is None:
        try:
            candidates = tuple(retrieval.search(query, timeout_ms=timeout_ms))
        except (RetrievalTimeout, RetrievalFault) as exc:
            return BlockedResult(
                False, "BLOCKED",
                f"retrieval stage failed, fail-closed ({LABEL}): {exc}")
    else:
        candidates = cached
    try:
        embedding.embed([c.text for c in candidates])
    except EmbeddingFault as exc:
        return BlockedResult(
            False, "BLOCKED",
            f"embedding stage failed, dropping {len(candidates)} retrieved "
            f"candidate(s) ({LABEL}): {exc}")
    authorized: list[Chunk] = []
    try:
        for chunk in candidates:
            verdict = acl.check(user, chunk.id)
            if verdict is True:
                authorized.append(chunk)
            elif verdict is False:
                continue  # Explicit deny for this chunk only.
            else:
                return BlockedResult(
                    False, "BLOCKED",
                    f"undefined authorization for chunk {chunk.id!r}, "
                    f"fail-closed, no continuation as granted ({LABEL})")
    except ACLFault as exc:
        return BlockedResult(
            False, "BLOCKED",
            f"ACL fault after {len(authorized)} grant(s); partial output "
            f"dropped, zero chunks returned ({LABEL}): {exc}")
    if candidates and not authorized:
        return BlockedResult(True, "success",
                             "all candidates denied by explicit ACL verdicts; "
                             f"zero chunks ({LABEL})", ())
    return BlockedResult(True, "success", "", tuple(authorized))


def sample_chunks() -> tuple[Chunk, ...]:
    return (Chunk("c1", "in-sample chunk one", "alice"),
            Chunk("c2", "in-sample chunk two", "alice"))
