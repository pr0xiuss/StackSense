"""Authorized Express platform API adapter for immutable analysis sources."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import httpx

from backend.platform.analysis.domain.constants import MAX_READ_BYTES_LIMIT
from backend.platform.errors import (
    AnalysisInputError,
    AnalysisIntegrityError,
    ArtifactContentUnavailableError,
)
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel


@dataclass(frozen=True, slots=True)
class PlatformArtifact:
    id: UUID
    project_id: UUID
    repository_id: UUID
    revision_id: UUID
    path: str
    size_bytes: int
    content_hash: str
    category: ArtifactCategory
    support_level: SupportLevel


@dataclass(frozen=True, slots=True)
class PlatformSnapshotManifest:
    id: UUID
    project_id: UUID
    repository_id: UUID
    revision_identifier: str
    source_hash: str
    total_files: int
    total_bytes: int
    artifacts: tuple[PlatformArtifact, ...]


class PlatformRepositoryGateway:
    """Port for reading Express-owned immutable revision data."""

    def get_manifest(
        self, project_id: UUID, repository_id: UUID, revision_id: UUID
    ) -> PlatformSnapshotManifest:
        raise NotImplementedError

    def read_artifact(
        self,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        artifact_id: UUID,
        *,
        max_bytes: int,
    ) -> bytes:
        raise NotImplementedError


class HttpPlatformRepositoryGateway(PlatformRepositoryGateway):
    """HTTP implementation that never accesses the Express MongoDB directly."""

    def __init__(
        self, base_url: str, service_token: str, timeout_seconds: float
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {"X-Service-Token": self._service_token}

    def get_manifest(
        self, project_id: UUID, repository_id: UUID, revision_id: UUID
    ) -> PlatformSnapshotManifest:
        url = (
            f"{self._base_url}/projects/{project_id}/repositories/{repository_id}"
            f"/revisions/{revision_id}/manifest"
        )
        try:
            response = httpx.get(
                url, headers=self._headers(), timeout=self._timeout_seconds
            )
            response.raise_for_status()
            payload = response.json()
            revision = payload["revision"]
            artifacts = tuple(
                PlatformArtifact(
                    id=UUID(item["id"]),
                    project_id=UUID(item["project_id"]),
                    repository_id=UUID(item["repository_id"]),
                    revision_id=UUID(item["revision_id"]),
                    path=str(item["path"]),
                    size_bytes=int(item["size_bytes"]),
                    content_hash=str(item["content_hash"]),
                    category=ArtifactCategory(item["category"]),
                    support_level=SupportLevel(item["support_level"]),
                )
                for item in payload["artifacts"]
            )
            return PlatformSnapshotManifest(
                id=UUID(revision["id"]),
                project_id=UUID(revision["project_id"]),
                repository_id=UUID(revision["repository_id"]),
                revision_identifier=str(revision["revision_identifier"]),
                source_hash=str(revision["source_hash"]),
                total_files=int(revision["total_files"]),
                total_bytes=int(revision["total_bytes"]),
                artifacts=artifacts,
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {404, 422}:
                raise AnalysisInputError(
                    "Express platform rejected the repository revision reference.",
                    details={"revision_id": str(revision_id)},
                ) from exc
            raise AnalysisIntegrityError(
                "Express platform manifest authorization failed.",
                details={"status_code": status},
            ) from exc
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise AnalysisInputError(
                "Express platform manifest is unavailable or invalid.",
                details={"revision_id": str(revision_id)},
            ) from exc

    def read_artifact(
        self,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        artifact_id: UUID,
        *,
        max_bytes: int,
    ) -> bytes:
        bounded = max(1, min(max_bytes, MAX_READ_BYTES_LIMIT))
        url = (
            f"{self._base_url}/projects/{project_id}/repositories/{repository_id}"
            f"/revisions/{revision_id}/artifacts/{artifact_id}/content"
        )
        try:
            response = httpx.get(
                url,
                headers=self._headers(),
                params={"max_bytes": bounded},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            return response.content[:bounded]
        except httpx.HTTPError as exc:
            raise ArtifactContentUnavailableError(
                "Express platform artifact content is unavailable.",
                details={"artifact_id": str(artifact_id)},
            ) from exc
