"""Official-client Elasticsearch adapter; every operational budget is explicit.

Credentials are composed outside task payloads. Index names are concrete, never
aliases; write-block acknowledgement, complete shards and UUID checks fail closed.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from math import ceil, isfinite
from time import monotonic
from typing import Any
from uuid import uuid4

from backend.platform.knowledge.contracts import (
    SearchBackendUnavailableError,
    SearchCursorExpiredError,
    SearchDeadlineExceededError,
    SearchIntegrityError,
)
from backend.platform.knowledge.elasticsearch import (
    SEARCH_INDEX_SETTINGS,
    BulkIndexResult,
    RecordSummary,
    compute_mapping_hash,
    compute_settings_hash,
)


@dataclass(frozen=True)
class SearchBudgets:
    request_seconds: float
    bulk_documents: int
    bulk_bytes: int
    readback_page: int
    pit_seconds: float
    cancel_seconds: float

    def __post_init__(self) -> None:
        if any(
            not isfinite(v) or v <= 0
            for v in (
                self.request_seconds,
                self.bulk_documents,
                self.bulk_bytes,
                self.readback_page,
                self.pit_seconds,
                self.cancel_seconds,
            )
        ):
            raise ValueError("explicit positive search budgets required")
        if self.cancel_seconds >= self.request_seconds:
            raise ValueError("cancellation budget must fit the operation budget")


@dataclass(frozen=True)
class SearchClients:
    provisioner: Any
    writer: Any
    sealer: Any
    reader: Any
    cleanup: Any


class ElasticsearchBackend:
    @staticmethod
    def _pit_missing(value: Any) -> bool:
        """Recognize typed ES failures, never document fields or reason text."""
        pending = [value]
        inspected = 0
        while pending and inspected < 256:
            item = pending.pop()
            inspected += 1
            if isinstance(item, dict):
                if item.get("type") in {
                    "search_context_missing_exception",
                    "point_in_time_missing_exception",
                }:
                    return True
                for key in (
                    "error",
                    "caused_by",
                    "root_cause",
                    "failed_shards",
                    "failures",
                    "reason",
                ):
                    child = item.get(key)
                    if isinstance(child, (dict, list)):
                        pending.append(child)
            elif isinstance(item, list):
                pending.extend(item[:256])
        return False

    def __init__(self, clients: SearchClients, budgets: SearchBudgets) -> None:
        self.clients, self.budgets = clients, budgets
        self._deadline: ContextVar[float | None] = ContextVar(
            "search_deadline", default=None
        )

    @contextmanager
    def operation(self, deadline: float) -> Iterator[None]:
        token = self._deadline.set(deadline)
        try:
            self._remaining()
            yield
            self._remaining()
        finally:
            self._deadline.reset(token)

    def _remaining(self) -> float:
        deadline = self._deadline.get()
        remaining = (
            self.budgets.request_seconds if deadline is None else deadline - monotonic()
        )
        if remaining <= 0:
            raise SearchDeadlineExceededError()
        return min(remaining, self.budgets.request_seconds)

    def _call(
        self,
        client: Any,
        method: str,
        *,
        _check_after: bool = True,
        _request_budget: float | None = None,
        **kwargs: Any,
    ) -> Any:
        # Hidden client retries would exceed the shared operation deadline and
        # create uncertain in-flight writes at the sealing barrier.
        bounded = client.options(
            request_timeout=(
                min(self._remaining(), _request_budget)
                if _request_budget is not None
                else self._remaining()
            ),
            max_retries=0,
            retry_on_timeout=False,
            opaque_id="m2-" + uuid4().hex,
        )
        try:
            target = bounded
            for part in method.split("."):
                target = getattr(target, part)
            result = target(**kwargs)
            if _check_after:
                self._remaining()
            return result
        except SearchDeadlineExceededError, SearchIntegrityError:
            raise
        except Exception as exc:
            if method in {
                "search",
                "async_search.submit",
                "async_search.get",
            } and self._pit_missing(getattr(exc, "body", None)):
                raise SearchCursorExpiredError() from exc
            if isinstance(exc, TimeoutError) or type(exc).__name__.endswith("Timeout"):
                raise SearchDeadlineExceededError() from exc
            if getattr(exc, "status_code", None) == 404 and method in {
                "search",
                "async_search.submit",
                "async_search.get",
            }:
                raise SearchCursorExpiredError() from exc
            raise SearchBackendUnavailableError() from exc

    @staticmethod
    def _name(name: str) -> None:
        if not name.startswith("stacksense-search-") or any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name
        ):
            raise SearchIntegrityError("Invalid concrete search index")

    def create_index(
        self, index_name: str, settings: dict[str, Any], mappings: dict[str, Any]
    ) -> str:
        self._name(index_name)
        response = self._call(
            self.clients.provisioner,
            "indices.create",
            index=index_name,
            settings=settings,
            mappings=mappings,
        )
        if not response.get("acknowledged") or not response.get("shards_acknowledged"):
            raise SearchIntegrityError("Search index creation not acknowledged")
        return str(self.inspect_index(index_name)["uuid"])

    def inspect_index(self, index_name: str) -> dict[str, Any]:
        self._name(index_name)
        response = self._call(
            self.clients.reader,
            "indices.get",
            index=index_name,
            expand_wildcards="none",
            allow_no_indices=False,
        )
        if set(response) != {index_name}:
            raise SearchIntegrityError("Exact concrete index required")
        value = response[index_name]
        if value.get("aliases"):
            raise SearchIntegrityError(
                "Aliases are forbidden for immutable generations"
            )
        settings = value["settings"]["index"]
        normalized = {"index": {k: settings[k] for k in SEARCH_INDEX_SETTINGS["index"]}}
        for k, v in SEARCH_INDEX_SETTINGS["index"].items():
            if isinstance(v, int):
                normalized["index"][k] = int(normalized["index"][k])
        return {
            "uuid": settings["uuid"],
            "sealed": settings.get("blocks", {}).get("write") in (True, "true"),
            "mapping_hash": compute_mapping_hash(value["mappings"]),
            "settings_hash": compute_settings_hash(normalized),
        }

    def bulk_index_records(
        self, index_name: str, records: list[dict[str, Any]]
    ) -> BulkIndexResult:
        from backend.platform.knowledge.model import canonical_json

        self._name(index_name)
        successful = 0
        for start in range(0, len(records), self.budgets.bulk_documents):
            chunk = records[start : start + self.budgets.bulk_documents]
            operations = []
            for record in chunk:
                operations.extend(
                    [
                        {
                            "create": {
                                "_index": index_name,
                                "_id": record["storage_key"],
                            }
                        },
                        record,
                    ]
                )
            if (
                sum(len(canonical_json(op).encode()) + 1 for op in operations)
                > self.budgets.bulk_bytes
            ):
                raise SearchIntegrityError("Bulk payload exceeds explicit budget")
            response = self._call(self.clients.writer, "bulk", operations=operations)
            items = response.get("items", [])
            if len(items) != len(chunk):
                raise SearchIntegrityError("Incomplete bulk response")
            for expected, item in zip(chunk, items, strict=True):
                outcome = item.get("create", {})
                if outcome.get("status") == 409:
                    existing = self._call(
                        self.clients.reader,
                        "get",
                        index=index_name,
                        id=expected["storage_key"],
                    )
                    if canonical_json(existing["_source"]) != canonical_json(expected):
                        raise SearchIntegrityError("Candidate overwrite rejected")
                elif outcome.get("status") != 201:
                    continue
                successful += 1
        return BulkIndexResult(len(records), successful, len(records) - successful)

    def refresh_index(self, index_name: str) -> None:
        response = self._call(self.clients.sealer, "indices.refresh", index=index_name)
        if response.get("_shards", {}).get("failed", 0):
            raise SearchIntegrityError("Incomplete index refresh")

    def drain_and_seal_index(self, index_name: str) -> None:
        self._name(index_name)
        response = self._call(
            self.clients.sealer, "indices.add_block", index=index_name, block="write"
        )
        if (
            not response.get("acknowledged")
            or not response.get("shards_acknowledged")
            or response.get("indices") != [{"name": index_name, "blocked": True}]
        ):
            raise SearchIntegrityError("Physical sealing not fully acknowledged")
        if self.inspect_index(index_name)["sealed"] is not True:
            raise SearchIntegrityError("Physical write exclusion missing")
        self.refresh_index(index_name)

    def open_pit(self, index_name: str, ttl_seconds: float) -> str:
        self._name(index_name)
        response = self._call(
            self.clients.reader,
            "open_point_in_time",
            index=index_name,
            keep_alive=f"{ceil(ttl_seconds*1000)}ms",
            allow_partial_search_results=False,
        )
        return str(response["id"])

    def close_pit(self, pit_id: str) -> None:
        # Best-effort resource cleanup has only its explicit cancellation
        # allowance; successful operations still perform a final deadline check.
        deadline = self._deadline.get()
        token = self._deadline.set(
            min(deadline, monotonic() + self.budgets.cancel_seconds)
            if deadline is not None and deadline > monotonic()
            else monotonic() + self.budgets.cancel_seconds
        )
        try:
            try:
                self._call(self.clients.reader, "close_point_in_time", id=pit_id)
            except SearchBackendUnavailableError as exc:
                # Expired/previously closed PIT cleanup is idempotent. Do not
                # mask the original typed 410 with a spurious cleanup 503.
                if getattr(exc.__cause__, "status_code", None) != 404:
                    raise
        finally:
            self._deadline.reset(token)

    def _search(
        self,
        pit_id: str,
        query: dict[str, Any],
        size: int,
        after: list[Any] | None,
        sort: list[Any],
    ) -> Any:
        budget = self._remaining() - self.budgets.cancel_seconds
        if budget <= 0:
            raise SearchDeadlineExceededError()
        search_id = None
        try:
            result = self._call(
                self.clients.reader,
                "async_search.submit",
                _check_after=False,
                _request_budget=budget,
                pit={"id": pit_id},
                query=query,
                size=size,
                search_after=after,
                sort=sort,
                track_total_hits=True,
                allow_partial_search_results=False,
                timeout=f"{max(1,int(budget*1000))}ms",
                wait_for_completion_timeout="0ms",
                keep_on_completion=True,
                keep_alive=f"{max(1000,int(budget*1000))}ms",
            )
            search_id = result.get("id")
            if result.get("is_running"):
                remaining = self._remaining() - self.budgets.cancel_seconds
                if not search_id or remaining <= 0:
                    raise SearchDeadlineExceededError()
                result = self._call(
                    self.clients.reader,
                    "async_search.get",
                    id=search_id,
                    _request_budget=remaining,
                    wait_for_completion_timeout=f"{max(1,int(remaining*1000))}ms",
                )
            response = result.get("response", {})
            if self._pit_missing(result.get("error")) or self._pit_missing(
                response.get("_shards", {})
            ):
                raise SearchCursorExpiredError()
            if (
                result.get("is_running")
                or result.get("is_partial")
                or result.get("error")
            ):
                raise SearchDeadlineExceededError()
            response = result["response"]
        finally:
            if search_id:
                # DELETE cancels running work, unlike merely abandoning a
                # timed-out HTTP request. Its allowance is explicit and reserved.
                token = self._deadline.set(monotonic() + self.budgets.cancel_seconds)
                try:
                    try:
                        deleted = self._call(
                            self.clients.reader, "async_search.delete", id=search_id
                        )
                        if deleted.get("acknowledged") is not True:
                            raise SearchBackendUnavailableError(
                                "Search cancellation unconfirmed"
                            )
                    except SearchBackendUnavailableError as exc:
                        if getattr(exc.__cause__, "status_code", None) != 404:
                            raise
                finally:
                    self._deadline.reset(token)
        if response.get("timed_out") or response.get("_shards", {}).get("failed", 0):
            raise SearchDeadlineExceededError()
        return response

    def iter_records(self, index_name: str) -> Iterator[dict[str, Any]]:
        pit = self.open_pit(index_name, self.budgets.pit_seconds)
        after = None
        try:
            while True:
                response = self._search(
                    pit,
                    {"match_all": {}},
                    self.budgets.readback_page,
                    after,
                    ["_shard_doc"],
                )
                pit = response.get("pit_id", pit)
                hits = response["hits"]["hits"]
                for hit in hits:
                    record = hit["_source"]
                    if hit["_id"] != record.get("storage_key"):
                        raise SearchIntegrityError("Physical document key mismatch")
                    yield record
                if len(hits) < self.budgets.readback_page:
                    break
                after = hits[-1]["sort"]
        finally:
            self.close_pit(pit)

    def read_all_record_summaries(self, index_name: str) -> list[RecordSummary]:
        return [
            RecordSummary(
                r["storage_key"],
                r["knowledge_key"],
                r["document_kind"],
                r["record_semantic_digest"],
            )
            for r in self.iter_records(index_name)
        ]

    def search_page(
        self,
        index_name: str,
        *,
        pit_id: str,
        scope: Any,
        generation_id: str,
        index_uuid: str,
        query: str,
        document_kinds: tuple[str, ...] | None,
        entity_kinds: tuple[str, ...] | None,
        statuses: tuple[str, ...] | None,
        size: int,
        after: list[Any] | None,
    ) -> tuple[list[dict[str, Any]], int, str]:
        filters: list[dict[str, Any]] = [
            {"term": {"project_id": str(scope.project_id)}},
            {"term": {"architecture_version_id": str(scope.architecture_version_id)}},
            {"term": {"generation_id": generation_id}},
            {"term": {"index_uuid": index_uuid}},
            {"term": {"repository_id": str(scope.repository_id)}},
            {"term": {"analysis_id": str(scope.analysis_id)}},
            {"term": {"snapshot_id": str(scope.snapshot_id)}},
        ]
        for field, values in (
            ("document_kind", document_kinds),
            ("kind", entity_kinds),
            ("status", statuses),
        ):
            if values is not None:
                filters.append({"terms": {field: list(values)}})
        # Exact matches occupy a disjoint score interval. A boost alone is not
        # an ordering guarantee: sufficiently large BM25 scores can outrank it.
        clauses = [
            {
                "constant_score": {
                    "filter": {
                        "bool": {
                            "should": [
                                {"term": {"canonical_reference": query}},
                                {"term": {"title.keyword": query}},
                                {"term": {"knowledge_key": query}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    "boost": 1,
                }
            },
            {"multi_match": {"query": query, "fields": ["title^3", "text_fields.*"]}},
        ]
        response = self._search(
            pit_id,
            {
                "script_score": {
                    "query": {
                        "bool": {
                            "filter": filters,
                            "should": clauses,
                            "minimum_should_match": 1,
                        }
                    },
                    "script": {
                        "source": """
                    boolean exact = (
                        doc['canonical_reference'].size() != 0 &&
                        doc['canonical_reference'].value.equals(params.q)
                    ) || (
                        doc['title.keyword'].size() != 0 &&
                        doc['title.keyword'].value.equals(params.q)
                    ) || (
                        doc['knowledge_key'].size() != 0 &&
                        doc['knowledge_key'].value.equals(params.q)
                    );
                    return (exact ? 2.0 : 1.0)
                        + Math.min(0.99, _score / (1.0 + _score));
                """,
                        "params": {"q": query},
                    },
                }
            },
            size,
            after,
            [{"_score": "desc"}, {"knowledge_key": "asc"}, "_shard_doc"],
        )
        rows = []
        for hit in response["hits"]["hits"]:
            r = hit["_source"]
            r["_score"] = float(hit["_score"])
            r["_rank_tier"] = 1 if hit["_score"] >= 2 else 2
            r["_sort"] = hit["sort"]
            rows.append(r)
        return (
            rows,
            int(response["hits"]["total"]["value"]),
            str(response.get("pit_id", pit_id)),
        )

    def search_records(
        self,
        index_name: str,
        *,
        query: str,
        document_kinds: tuple[str, ...] | None = None,
        entity_kinds: tuple[str, ...] | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        raise SearchIntegrityError("Unbounded search is not a production capability")

    def delete_index(self, index_name: str) -> None:
        self._name(index_name)
        self._call(self.clients.cleanup, "indices.delete", index=index_name)

    def is_healthy(self) -> bool:
        try:
            return bool(self._call(self.clients.reader, "ping"))
        except SearchBackendUnavailableError:
            return False
