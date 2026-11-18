"""Explicit deployment values; no test limits or credentials become defaults."""

import importlib
import importlib.metadata
from functools import lru_cache
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from backend.platform.delivery.contracts import HandlerProfile
from backend.platform.knowledge.contracts import SearchBackendUnavailableError
from backend.platform.knowledge.es_backend import (
    ElasticsearchBackend,
    SearchBudgets,
    SearchClients,
)


class SearchDeployment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    binding: HandlerProfile
    endpoint: str
    ca_certs: str
    server_version: Literal["9.5.6"]
    client_version: Literal["9.5.1"]
    provisioner_api_key: SecretStr
    writer_api_key: SecretStr
    sealer_api_key: SecretStr
    reader_api_key: SecretStr
    cleanup_api_key: SecretStr
    request_seconds: float = Field(gt=0, allow_inf_nan=False)
    bulk_documents: int = Field(gt=0)
    bulk_bytes: int = Field(gt=0)
    readback_page: int = Field(gt=0)
    pit_seconds: float = Field(gt=0, allow_inf_nan=False)
    cancel_seconds: float = Field(gt=0, allow_inf_nan=False)
    status_page_size: int = Field(gt=0, le=500)
    status_max_pages: int = Field(gt=0)
    index_settings: dict[str, Any]

    @model_validator(mode="after")
    def cancellation_fits_deadline(self) -> Self:
        if self.cancel_seconds >= self.request_seconds:
            raise ValueError("Cancellation allowance must fit the request budget")
        return self

    @field_validator("index_settings")
    @classmethod
    def settings_allowlist(cls, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != {"index"} or not isinstance(value["index"], dict):
            raise ValueError("Explicit physical index settings required")
        settings = value["index"]
        if set(settings) != {
            "number_of_shards",
            "number_of_replicas",
            "auto_expand_replicas",
            "refresh_interval",
        }:
            raise ValueError("Unknown or missing physical index setting")
        if (
            type(settings["number_of_shards"]) is not int
            or settings["number_of_shards"] <= 0
            or type(settings["number_of_replicas"]) is not int
            or settings["number_of_replicas"] < 0
        ):
            raise ValueError(
                "Explicit positive shard/nonnegative replica counts required"
            )
        from typing import Annotated

        from pydantic import TypeAdapter

        TypeAdapter(
            Annotated[str, Field(pattern=r"^(false|[0-9]+-([0-9]+|all))$")]
        ).validate_python(settings["auto_expand_replicas"])
        TypeAdapter(
            Annotated[str, Field(pattern=r"^(-1|[1-9][0-9]*(ms|s|m))$")]
        ).validate_python(settings["refresh_interval"])
        return value


def parse_deployment(raw: str) -> SearchDeployment:
    try:
        return SearchDeployment.model_validate_json(raw)
    except ValueError:
        raise SearchBackendUnavailableError(
            "Invalid search deployment configuration"
        ) from None


@lru_cache(maxsize=1)
def configured_backend(raw: str) -> ElasticsearchBackend:
    config = parse_deployment(raw)
    if not config.endpoint.startswith("https://"):
        raise SearchBackendUnavailableError("Search requires TLS")
    try:
        module = importlib.import_module("elasticsearch")
        version = importlib.metadata.version("elasticsearch")
    except (ImportError, AttributeError) as exc:
        raise SearchBackendUnavailableError(
            "Official search client is not installed"
        ) from exc
    if version != config.client_version:
        raise SearchBackendUnavailableError("Search client version mismatch")

    def client(key: SecretStr) -> Any:
        return module.Elasticsearch(
            config.endpoint,
            ca_certs=config.ca_certs,
            api_key=key.get_secret_value(),
            verify_certs=True,
            max_retries=0,
            retry_on_timeout=False,
            request_timeout=config.request_seconds,
        )

    opened = []
    try:
        for key in (
            config.provisioner_api_key,
            config.writer_api_key,
            config.sealer_api_key,
            config.reader_api_key,
            config.cleanup_api_key,
        ):
            opened.append(client(key))
        clients = SearchClients(*opened)
        # Compatibility discovery needs cluster monitor privileges; keep them
        # on provisioning credentials, never on the data-read credential.
        info = clients.provisioner.info()
        if info["version"]["number"] != config.server_version:
            raise SearchBackendUnavailableError("Search server version mismatch")
    except Exception:
        for configured_client in opened:
            configured_client.close()
        raise SearchBackendUnavailableError(
            "Search server compatibility could not be verified"
        ) from None
    return ElasticsearchBackend(
        clients,
        SearchBudgets(
            config.request_seconds,
            config.bulk_documents,
            config.bulk_bytes,
            config.readback_page,
            config.pit_seconds,
            config.cancel_seconds,
        ),
    )
