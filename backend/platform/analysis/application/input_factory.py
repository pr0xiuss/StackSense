"""Factory and adapters constructing immutable AnalysisInput from Phase 2 contracts."""

import re
from io import BytesIO
from typing import BinaryIO
from uuid import UUID

from backend.platform.analysis.application.platform_gateway import (
    PlatformRepositoryGateway,
)
from backend.platform.analysis.domain.analysis import AnalysisConfiguration
from backend.platform.analysis.domain.constants import (
    DEFAULT_ARTIFACT_PAGE_SIZE,
    MAX_READ_BYTES_LIMIT,
)
from backend.platform.analysis.domain.input import (
    AnalysisArtifact,
    AnalysisInput,
    ArtifactCatalog,
    ArtifactContentReader,
)
from backend.platform.errors import (
    AnalysisInputError,
    AnalysisIntegrityError,
    ArtifactContentUnavailableError,
)
from backend.platform.ingestion.application.storage import StorageService
from backend.platform.ingestion.repositories.artifact_repo import ArtifactRepository
from backend.platform.ingestion.repositories.revision_repo import RevisionRepository
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)

_SHA256_HEX_RE = re.compile(r"[0-9a-fA-F]{64}")


def _require_sha256_content_hash(value: str, artifact_id: UUID) -> str:
    if not _SHA256_HEX_RE.fullmatch(value):
        raise AnalysisIntegrityError(
            "Artifact content hash is not a valid SHA-256 digest.",
            details={"artifact_id": str(artifact_id)},
        )
    return value.lower()


def is_safe_relative_path(path: str) -> bool:
    """Validate that path is a safe relative path with no directory traversal."""
    if not path or path.startswith("/") or path.startswith("\\") or "\0" in path:
        return False
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if part in ("..", ".", ""):
            return False
    return True


class StorageArtifactContentReader(ArtifactContentReader):
    """Encapsulated storage adapter providing lazy, bounded reads."""

    def __init__(
        self,
        storage_service: StorageService,
        key_map: dict[UUID, str],
    ) -> None:
        self._storage_service = storage_service
        self._key_map = key_map

    def _get_key(self, artifact: AnalysisArtifact) -> str:
        key = self._key_map.get(artifact.id)
        if not key:
            raise ArtifactContentUnavailableError(
                message=(
                    f"Storage key mapping not found for artifact '{artifact.path}'."
                ),
                details={
                    "artifact_id": str(artifact.id),
                    "artifact_path": artifact.path,
                },
            )
        return key

    def read_bytes(
        self,
        artifact: AnalysisArtifact,
        max_bytes: int | None = None,
    ) -> bytes:
        """Read content bytes up to max_bytes (bounded by MAX_READ_BYTES_LIMIT)."""
        key = self._get_key(artifact)
        try:
            stream = self._storage_service.get(key)
            limit = (
                min(max_bytes, MAX_READ_BYTES_LIMIT)
                if max_bytes is not None
                else MAX_READ_BYTES_LIMIT
            )
            content = stream.read(limit)
            return content
        except Exception as exc:
            if isinstance(exc, ArtifactContentUnavailableError):
                raise
            raise ArtifactContentUnavailableError(
                message=(
                    f"Failed to read storage content for artifact "
                    f"'{artifact.path}': {exc}"
                ),
                details={
                    "artifact_id": str(artifact.id),
                    "artifact_path": artifact.path,
                },
            ) from exc

    def open_stream(self, artifact: AnalysisArtifact) -> BinaryIO:
        """Open a readable binary stream for the artifact."""
        key = self._get_key(artifact)
        try:
            return self._storage_service.get(key)
        except Exception as exc:
            if isinstance(exc, ArtifactContentUnavailableError):
                raise
            raise ArtifactContentUnavailableError(
                message=(
                    f"Failed to open storage stream for artifact "
                    f"'{artifact.path}': {exc}"
                ),
                details={
                    "artifact_id": str(artifact.id),
                    "artifact_path": artifact.path,
                },
            ) from exc

    def exists(self, artifact: AnalysisArtifact) -> bool:
        """Check whether the underlying artifact content exists in storage."""
        key = self._key_map.get(artifact.id)
        if not key:
            return False
        try:
            return self._storage_service.exists(key)
        except Exception:
            return False


class AnalysisInputFactory:
    """Builds and validates immutable AnalysisInput from Phase 2 persistence records."""

    def __init__(
        self,
        revision_repo: RevisionRepository,
        artifact_repo: ArtifactRepository,
        storage_service: StorageService,
        repository_repo: RepositoryRepository | None = None,
        page_size: int = DEFAULT_ARTIFACT_PAGE_SIZE,
    ) -> None:
        self._revision_repo = revision_repo
        self._artifact_repo = artifact_repo
        self._storage_service = storage_service
        self._repository_repo = repository_repo
        self._page_size = page_size

    def build_analysis_input(
        self,
        analysis_id: UUID,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        configuration: AnalysisConfiguration | None = None,
    ) -> AnalysisInput:
        """Validate ownership chain and build immutable AnalysisInput."""
        # 1. Retrieve and validate Revision
        revision = self._revision_repo.get_by_id(revision_id)
        if revision is None:
            raise AnalysisInputError(
                message=f"Repository revision '{revision_id}' not found.",
                details={"revision_id": str(revision_id)},
            )

        # 2. Validate ownership chain
        if revision.project_id != project_id:
            raise AnalysisIntegrityError(
                message="Revision project ID does not match analysis project ID.",
                details={
                    "revision_id": str(revision_id),
                    "expected_project_id": str(project_id),
                    "actual_project_id": str(revision.project_id),
                },
            )
        if revision.repository_id != repository_id:
            raise AnalysisIntegrityError(
                message="Revision repository ID does not match analysis repository ID.",
                details={
                    "revision_id": str(revision_id),
                    "expected_repository_id": str(repository_id),
                    "actual_repository_id": str(revision.repository_id),
                },
            )

        # 3. Optional repository verification
        if self._repository_repo is not None:
            repository = self._repository_repo.get_by_id(repository_id)
            if repository is None or repository.project_id != project_id:
                raise AnalysisIntegrityError(
                    message="Repository not found or project mismatch.",
                    details={
                        "repository_id": str(repository_id),
                        "project_id": str(project_id),
                    },
                )

        # 4. Page through artifacts deterministically
        artifacts: list[AnalysisArtifact] = []
        key_map: dict[UUID, str] = {}
        offset = 0

        while True:
            batch = self._artifact_repo.list_by_revision(
                revision_id,
                limit=self._page_size,
                offset=offset,
            )
            if not batch:
                break

            for item in batch:
                # Validate artifact ownership chain
                if (
                    item.project_id != project_id
                    or item.repository_id != repository_id
                    or item.revision_id != revision_id
                ):
                    raise AnalysisIntegrityError(
                        message=(
                            f"Artifact '{item.id}' fails ownership chain validation."
                        ),
                        details={
                            "artifact_id": str(item.id),
                            "artifact_path": item.path,
                        },
                    )

                # Path safety verification
                if not is_safe_relative_path(item.path):
                    raise AnalysisIntegrityError(
                        message=(
                            f"Artifact path '{item.path}' contains invalid "
                            "or traversing path elements."
                        ),
                        details={
                            "artifact_id": str(item.id),
                            "artifact_path": item.path,
                        },
                    )

                artifact_domain = AnalysisArtifact(
                    id=item.id,
                    revision_id=item.revision_id,
                    path=item.path,
                    size_bytes=item.size_bytes,
                    content_hash=_require_sha256_content_hash(
                        item.content_hash, item.id
                    ),
                    category=item.category,
                    support_level=item.support_level,
                )
                artifacts.append(artifact_domain)
                key_map[item.id] = item.storage_key

            offset += len(batch)
            if len(batch) < self._page_size:
                break

        # 5. Metadata total files consistency check
        if revision.total_files != len(artifacts):
            raise AnalysisIntegrityError(
                message=(
                    f"Revision metadata total_files ({revision.total_files}) "
                    f"does not match discovered count ({len(artifacts)})."
                ),
                details={
                    "revision_id": str(revision_id),
                    "expected_files": revision.total_files,
                    "actual_files": len(artifacts),
                },
            )

        reader = StorageArtifactContentReader(
            storage_service=self._storage_service,
            key_map=key_map,
        )

        catalog = ArtifactCatalog(artifacts=tuple(artifacts))

        return AnalysisInput(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=revision.id,
            revision_identifier=revision.revision_identifier,
            source_hash=revision.source_hash,
            total_files=catalog.total_files,
            total_bytes=catalog.total_bytes,
            effective_configuration=configuration or AnalysisConfiguration(),
            artifact_catalog=catalog,
            content_reader=reader,
        )


class PlatformArtifactContentReader(ArtifactContentReader):
    """Lazy bounded reader for Express-owned artifact content."""

    def __init__(
        self,
        gateway: PlatformRepositoryGateway,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        artifact_ids: frozenset[UUID],
    ) -> None:
        self._gateway = gateway
        self._project_id = project_id
        self._repository_id = repository_id
        self._revision_id = revision_id
        self._artifact_ids = artifact_ids

    @property
    def concurrent_read_limit(self) -> int:
        """Maximum safe parallel reads supported by the platform gateway."""
        return self._gateway.concurrent_read_limit

    def _read(self, artifact: AnalysisArtifact, limit: int) -> bytes:
        if artifact.id not in self._artifact_ids:
            raise ArtifactContentUnavailableError(
                "Artifact is not part of the authorized immutable manifest.",
                details={"artifact_id": str(artifact.id)},
            )
        return self._gateway.read_artifact(
            self._project_id,
            self._repository_id,
            self._revision_id,
            artifact.id,
            max_bytes=limit,
        )

    def read_bytes(
        self, artifact: AnalysisArtifact, max_bytes: int | None = None
    ) -> bytes:
        limit = min(max_bytes or MAX_READ_BYTES_LIMIT, MAX_READ_BYTES_LIMIT)
        return self._read(artifact, limit)

    def open_stream(self, artifact: AnalysisArtifact) -> BinaryIO:
        return BytesIO(self._read(artifact, MAX_READ_BYTES_LIMIT))

    def exists(self, artifact: AnalysisArtifact) -> bool:
        if artifact.id not in self._artifact_ids:
            return False
        try:
            self._read(artifact, 1)
            return True
        except ArtifactContentUnavailableError:
            return False


class PlatformAnalysisInputFactory(AnalysisInputFactory):
    """Construct AnalysisInput exclusively through the authorized Express API."""

    def __init__(self, gateway: PlatformRepositoryGateway) -> None:
        self._gateway = gateway

    def build_analysis_input(
        self,
        analysis_id: UUID,
        project_id: UUID,
        repository_id: UUID,
        revision_id: UUID,
        configuration: AnalysisConfiguration | None = None,
    ) -> AnalysisInput:
        manifest = self._gateway.get_manifest(project_id, repository_id, revision_id)
        if (
            manifest.id != revision_id
            or manifest.project_id != project_id
            or manifest.repository_id != repository_id
        ):
            raise AnalysisIntegrityError(
                "Express manifest ownership chain does not match the analysis."
            )

        artifacts: list[AnalysisArtifact] = []
        for item in manifest.artifacts:
            if (
                item.project_id != project_id
                or item.repository_id != repository_id
                or item.revision_id != revision_id
            ):
                raise AnalysisIntegrityError(
                    "Express artifact ownership chain is invalid.",
                    details={"artifact_id": str(item.id)},
                )
            if not is_safe_relative_path(item.path):
                raise AnalysisIntegrityError(
                    "Express artifact path is unsafe.",
                    details={"artifact_id": str(item.id), "path": item.path},
                )
            artifacts.append(
                AnalysisArtifact(
                    id=item.id,
                    revision_id=item.revision_id,
                    path=item.path,
                    size_bytes=item.size_bytes,
                    content_hash=_require_sha256_content_hash(
                        item.content_hash, item.id
                    ),
                    category=item.category,
                    support_level=item.support_level,
                )
            )

        catalog = ArtifactCatalog(tuple(artifacts))
        if manifest.total_files != catalog.total_files:
            raise AnalysisIntegrityError(
                "Express manifest file count does not match its artifact catalog."
            )
        if manifest.total_bytes != catalog.total_bytes:
            raise AnalysisIntegrityError(
                "Express manifest byte count does not match its artifact catalog."
            )

        reader = PlatformArtifactContentReader(
            self._gateway,
            project_id,
            repository_id,
            revision_id,
            frozenset(artifact.id for artifact in artifacts),
        )
        return AnalysisInput(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=manifest.id,
            revision_identifier=manifest.revision_identifier,
            source_hash=manifest.source_hash,
            total_files=catalog.total_files,
            total_bytes=catalog.total_bytes,
            effective_configuration=configuration or AnalysisConfiguration(),
            artifact_catalog=catalog,
            content_reader=reader,
        )
