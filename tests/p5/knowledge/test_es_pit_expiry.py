"""Owner-approved M2 amendment: physical PIT loss preserves C1 expiry."""

from unittest.mock import Mock

import pytest

from backend.platform.knowledge.contracts import (
    SearchCursorExpiredError,
    SearchDeadlineExceededError,
)
from backend.platform.knowledge.es_backend import (
    ElasticsearchBackend,
    SearchBudgets,
    SearchClients,
)


@pytest.mark.parametrize("location", ["error", "shards"])
def test_async_missing_pit_is_expiry_and_still_cancels(location):
    reader = Mock()
    reader.options.return_value = reader
    missing = {"type": "search_context_missing_exception", "reason": "absent"}
    result = {"id": "async-id", "is_running": False, "is_partial": True}
    if location == "error":
        result["error"] = {"root_cause": [missing]}
    else:
        result["response"] = {
            "_shards": {"failed": 1, "failures": [{"reason": missing}]}
        }
    reader.async_search.submit.return_value = result
    reader.async_search.delete.return_value = {"acknowledged": True}
    backend = ElasticsearchBackend(
        SearchClients(reader, reader, reader, reader, reader),
        SearchBudgets(5, 10, 1000, 10, 30, 0.5),
    )
    with pytest.raises(SearchCursorExpiredError):
        backend._search("closed-pit", {"match_all": {}}, 1, None, ["_shard_doc"])
    reader.async_search.delete.assert_called_once_with(id="async-id")


def test_partial_search_is_not_misclassified_by_reason_text_or_document_fields():
    reader = Mock()
    reader.options.return_value = reader
    reader.async_search.submit.return_value = {
        "is_partial": True,
        "error": {
            "type": "timeout_exception",
            "reason": "search_context_missing_exception",
        },
        "response": {
            "hits": {
                "hits": [{"_source": {"type": "search_context_missing_exception"}}]
            }
        },
    }
    backend = ElasticsearchBackend(
        SearchClients(reader, reader, reader, reader, reader),
        SearchBudgets(5, 10, 1000, 10, 30, 0.5),
    )
    with pytest.raises(SearchDeadlineExceededError):
        backend._search("pit", {"match_all": {}}, 1, None, ["_shard_doc"])
