"""Tests for AnalysisInput construction, lazy reads, and pagination."""

import hashlib
import io
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

import httpx
import pytest

from backend.platform.analysis.application.input_factory import (
    AnalysisInputFactory,
    PlatformAnalysisInputFactory,
    is_safe_relative_path,
)
from backend.platform.analysis.application.platform_gateway import (
    HttpPlatformRepositoryGateway,
    PlatformArtifact,
    PlatformRepositoryGateway,
    PlatformSnapshotManifest,
)
from backend.platform.analysis.domain.input import AnalysisArtifact
from backend.platform.errors import (
    AnalysisInputError,
    AnalysisIntegrityError,
    ArtifactContentUnavailableError,
)
from backend.platform.ingestion.application.storage import StorageService
from backend.platform.ingestion.domain.artifact import RepositoryArtifact
from backend.platform.ingestion.domain.constants import ArtifactCategory, SupportLevel
from backend.platform.ingestion.domain.revision import RepositoryRevision
from backend.platform.ingestion.repositories.artifact_repo import ArtifactRepository
from backend.platform.ingestion.repositories.revision_repo import RevisionRepository
from backend.platform.repositories.domain.repository import Repository
from backend.platform.repositories.repositories.repository_repo import (
    RepositoryRepository,
)


class FakeRevisionRepository(RevisionRepository):
    def __init__(self, revisions: list[RepositoryRevision] | None = None) -> None:
        self._revisions: dict[UUID, RepositoryRevision] = {
            r.id: r for r in (revisions or [])
        }

    def save(self, revision: RepositoryRevision) -> RepositoryRevision:
        self._revisions[revision.id] = revision
        return revision

    def get_by_id(self, revision_id: UUID) -> RepositoryRevision | None:
        return self._revisions.get(revision_id)

    def get_by_repository_and_identifier(
        self,
        repository_id: UUID,
        revision_identifier: str,
    ) -> RepositoryRevision | None:
        for r in self._revisions.values():
            if (
                r.repository_id == repository_id
                and r.revision_identifier == revision_identifier
            ):
                return r
        return None

    def list_by_repository(
        self,
        repository_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[RepositoryRevision]:
        matches = [
            r for r in self._revisions.values() if r.repository_id == repository_id
        ]
        return matches[offset : offset + limit]


class FakeArtifactRepository(ArtifactRepository):
    def __init__(self, artifacts: list[RepositoryArtifact] | None = None) -> None:
        self._artifacts = list(artifacts or [])

    def save_batch(self, artifacts: list[RepositoryArtifact]) -> None:
        self._artifacts.extend(artifacts)

    def list_by_revision(
        self,
        revision_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[RepositoryArtifact]:
        matches = [a for a in self._artifacts if a.revision_id == revision_id]
        return matches[offset : offset + limit]


class FakeStorageService(StorageService):
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self._files: dict[str, bytes] = dict(files or {})
        self.get_call_count = 0

    def put(self, key: str, data: BinaryIO | bytes) -> str:
        if isinstance(data, bytes):
            self._files[key] = data
        else:
            self._files[key] = data.read()
        return key

    def get(self, key: str) -> BinaryIO:
        self.get_call_count += 1
        if key not in self._files:
            raise KeyError(f"Storage key '{key}' not found.")
        return io.BytesIO(self._files[key])

    def exists(self, key: str) -> bool:
        return key in self._files

    def delete(self, key: str) -> None:
        self._files.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        keys_to_del = [k for k in self._files if k.startswith(prefix)]
        for k in keys_to_del:
            del self._files[k]


class FakeRepositoryRepository(RepositoryRepository):
    def __init__(self, repositories: list[Repository] | None = None) -> None:
        self._repos = {r.id: r for r in (repositories or [])}

    def save(self, repository: Repository) -> Repository:
        self._repos[repository.id] = repository
        return repository

    def get_by_id(self, repository_id: UUID) -> Repository | None:
        return self._repos.get(repository_id)

    def get_by_project_and_name(self, project_id: UUID, name: str) -> Repository | None:
        for r in self._repos.values():
            if r.project_id == project_id and r.name == name:
                return r
        return None

    def list_by_project(
        self, project_id: UUID, *, limit: int, offset: int
    ) -> list[Repository]:
        matches = [r for r in self._repos.values() if r.project_id == project_id]
        return matches[offset : offset + limit]

    def update(self, repository: Repository) -> Repository:
        self._repos[repository.id] = repository
        return repository

    def delete(self, repository_id: UUID) -> None:
        self._repos.pop(repository_id, None)


# --- Helper Fixtures ---


def _setup_test_data() -> tuple[
    UUID,
    UUID,
    UUID,
    UUID,
    RepositoryRevision,
    list[RepositoryArtifact],
    dict[str, bytes],
]:
    project_id = uuid4()
    repo_id = uuid4()
    revision_id = uuid4()
    analysis_id = uuid4()
    now = datetime.now(UTC)

    files_content = {
        "storage/key/1": b"def hello(): return 'world'",
        "storage/key/2": b"console.log('hi');",
        "storage/key/3": b"# Readme content",
    }

    artifacts = [
        # Intentionally unordered to test deterministic sorting
        RepositoryArtifact(
            id=uuid4(),
            project_id=project_id,
            repository_id=repo_id,
            revision_id=revision_id,
            path="src/index.js",
            size_bytes=len(files_content["storage/key/2"]),
            content_hash=hashlib.sha256(files_content["storage/key/2"]).hexdigest(),
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
            storage_key="storage/key/2",
            created_at=now,
        ),
        RepositoryArtifact(
            id=uuid4(),
            project_id=project_id,
            repository_id=repo_id,
            revision_id=revision_id,
            path="src/app.py",
            size_bytes=len(files_content["storage/key/1"]),
            content_hash=hashlib.sha256(files_content["storage/key/1"]).hexdigest(),
            category=ArtifactCategory.SOURCE_CODE,
            support_level=SupportLevel.FULL,
            storage_key="storage/key/1",
            created_at=now,
        ),
        RepositoryArtifact(
            id=uuid4(),
            project_id=project_id,
            repository_id=repo_id,
            revision_id=revision_id,
            path="README.md",
            size_bytes=len(files_content["storage/key/3"]),
            content_hash=hashlib.sha256(files_content["storage/key/3"]).hexdigest(),
            category=ArtifactCategory.DOCUMENTATION,
            support_level=SupportLevel.METADATA,
            storage_key="storage/key/3",
            created_at=now,
        ),
    ]

    total_bytes = sum(a.size_bytes for a in artifacts)
    revision = RepositoryRevision(
        id=revision_id,
        project_id=project_id,
        repository_id=repo_id,
        ingestion_id=uuid4(),
        revision_identifier="commit-abc",
        source_hash="sha256-tree",
        total_files=len(artifacts),
        total_bytes=total_bytes,
        created_at=now,
    )

    return (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    )


# --- Input Construction & Deterministic Ordering ---


def test_build_analysis_input_success_and_deterministic_order() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    rev_repo = FakeRevisionRepository([revision])
    art_repo = FakeArtifactRepository(artifacts)
    storage = FakeStorageService(files_content)

    factory = AnalysisInputFactory(
        revision_repo=rev_repo,
        artifact_repo=art_repo,
        storage_service=storage,
    )

    analysis_input = factory.build_analysis_input(
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repo_id,
        revision_id=revision_id,
    )

    assert analysis_input.analysis_id == analysis_id
    assert analysis_input.project_id == project_id
    assert analysis_input.repository_id == repo_id
    assert analysis_input.snapshot_id == revision_id
    assert analysis_input.total_files == 3

    # Verify deterministic sorting by path
    paths = analysis_input.artifact_catalog.paths()
    assert paths == ("README.md", "src/app.py", "src/index.js")

    # Verify storage was NOT read during input construction (lazy)
    assert storage.get_call_count == 0


def test_storage_keys_are_not_exposed_on_domain_artifacts() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(artifacts),
        storage_service=FakeStorageService(files_content),
    )

    analysis_input = factory.build_analysis_input(
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repo_id,
        revision_id=revision_id,
    )

    for artifact in analysis_input.artifact_catalog.artifacts:
        assert isinstance(artifact, AnalysisArtifact)
        assert not hasattr(artifact, "storage_key")


def test_lazy_content_reading_and_bounding() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    storage = FakeStorageService(files_content)
    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(artifacts),
        storage_service=storage,
    )

    analysis_input = factory.build_analysis_input(
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repo_id,
        revision_id=revision_id,
    )

    app_py = analysis_input.artifact_catalog.get_by_path("src/app.py")
    assert app_py is not None

    # Lazy read on demand
    assert storage.get_call_count == 0
    content = analysis_input.content_reader.read_bytes(app_py)
    assert content == b"def hello(): return 'world'"
    assert storage.get_call_count == 1

    # Bounded read
    bounded_content = analysis_input.content_reader.read_bytes(app_py, max_bytes=3)
    assert bounded_content == b"def"

    # Exists check
    assert analysis_input.content_reader.exists(app_py) is True

    # Open stream
    stream = analysis_input.content_reader.open_stream(app_py)
    assert stream.read() == b"def hello(): return 'world'"


def test_missing_storage_content_raises_unavailable() -> None:
    project_id, repo_id, revision_id, analysis_id, revision, artifacts, _ = (
        _setup_test_data()
    )

    # Empty storage: files are missing
    empty_storage = FakeStorageService({})
    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(artifacts),
        storage_service=empty_storage,
    )

    analysis_input = factory.build_analysis_input(
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repo_id,
        revision_id=revision_id,
    )

    app_py = analysis_input.artifact_catalog.get_by_path("src/app.py")
    assert app_py is not None

    with pytest.raises(ArtifactContentUnavailableError):
        analysis_input.content_reader.read_bytes(app_py)

    with pytest.raises(ArtifactContentUnavailableError):
        analysis_input.content_reader.open_stream(app_py)


# --- Ownership Chain & Integrity Validation Tests ---


def test_missing_revision_raises_input_error() -> None:
    project_id, repo_id, revision_id, analysis_id, _, _, _ = _setup_test_data()

    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([]),
        artifact_repo=FakeArtifactRepository([]),
        storage_service=FakeStorageService({}),
    )

    with pytest.raises(AnalysisInputError) as exc:
        factory.build_analysis_input(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repo_id,
            revision_id=revision_id,
        )
    assert exc.value.code == "analysis_input_invalid"


def test_revision_project_mismatch_raises_integrity_error() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(artifacts),
        storage_service=FakeStorageService(files_content),
    )

    with pytest.raises(AnalysisIntegrityError) as exc:
        factory.build_analysis_input(
            analysis_id=analysis_id,
            project_id=uuid4(),  # Different project
            repository_id=repo_id,
            revision_id=revision_id,
        )
    assert exc.value.code == "analysis_integrity_violation"


def test_revision_repository_mismatch_raises_integrity_error() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(artifacts),
        storage_service=FakeStorageService(files_content),
    )

    with pytest.raises(AnalysisIntegrityError) as exc:
        factory.build_analysis_input(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=uuid4(),  # Different repository
            revision_id=revision_id,
        )
    assert exc.value.code == "analysis_integrity_violation"


def test_artifact_ownership_mismatch_raises_integrity_error() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    # Tamper with one artifact's project_id
    tampered_artifacts = list(artifacts)
    tampered_artifacts[0] = RepositoryArtifact(
        id=tampered_artifacts[0].id,
        project_id=uuid4(),  # Tampered project_id
        repository_id=repo_id,
        revision_id=revision_id,
        path=tampered_artifacts[0].path,
        size_bytes=tampered_artifacts[0].size_bytes,
        content_hash=tampered_artifacts[0].content_hash,
        category=tampered_artifacts[0].category,
        support_level=tampered_artifacts[0].support_level,
        storage_key=tampered_artifacts[0].storage_key,
        created_at=tampered_artifacts[0].created_at,
    )

    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(tampered_artifacts),
        storage_service=FakeStorageService(files_content),
    )

    with pytest.raises(AnalysisIntegrityError) as exc:
        factory.build_analysis_input(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repo_id,
            revision_id=revision_id,
        )
    assert exc.value.code == "analysis_integrity_violation"


def test_malicious_artifact_path_traversal_raises_integrity_error() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    bad_artifacts = list(artifacts)
    bad_artifacts[0] = RepositoryArtifact(
        id=bad_artifacts[0].id,
        project_id=project_id,
        repository_id=repo_id,
        revision_id=revision_id,
        path="../etc/passwd",  # Traversal attempt
        size_bytes=bad_artifacts[0].size_bytes,
        content_hash=bad_artifacts[0].content_hash,
        category=bad_artifacts[0].category,
        support_level=bad_artifacts[0].support_level,
        storage_key=bad_artifacts[0].storage_key,
        created_at=bad_artifacts[0].created_at,
    )

    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(bad_artifacts),
        storage_service=FakeStorageService(files_content),
    )

    with pytest.raises(AnalysisIntegrityError) as exc:
        factory.build_analysis_input(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repo_id,
            revision_id=revision_id,
        )
    assert "traversing" in str(exc.value.message).lower()


def test_total_files_mismatch_raises_integrity_error() -> None:
    (
        project_id,
        repo_id,
        revision_id,
        analysis_id,
        revision,
        artifacts,
        files_content,
    ) = _setup_test_data()

    # Pass only 2 artifacts while revision says 3 total_files
    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(artifacts[:2]),
        storage_service=FakeStorageService(files_content),
    )

    with pytest.raises(AnalysisIntegrityError) as exc:
        factory.build_analysis_input(
            analysis_id=analysis_id,
            project_id=project_id,
            repository_id=repo_id,
            revision_id=revision_id,
        )
    assert "total_files" in str(exc.value.message)


def test_artifact_paging_across_multiple_pages() -> None:
    project_id = uuid4()
    repo_id = uuid4()
    revision_id = uuid4()
    analysis_id = uuid4()
    now = datetime.now(UTC)

    # Create 5 artifacts and set page_size to 2
    artifacts = []
    files_content = {}
    for i in range(5):
        key = f"key_{i}"
        files_content[key] = f"content {i}".encode()
        artifacts.append(
            RepositoryArtifact(
                id=uuid4(),
                project_id=project_id,
                repository_id=repo_id,
                revision_id=revision_id,
                path=f"file_{i}.txt",
                size_bytes=len(files_content[key]),
                content_hash=hashlib.sha256(files_content[key]).hexdigest(),
                category=ArtifactCategory.SOURCE_CODE,
                support_level=SupportLevel.FULL,
                storage_key=key,
                created_at=now,
            )
        )

    revision = RepositoryRevision(
        id=revision_id,
        project_id=project_id,
        repository_id=repo_id,
        ingestion_id=uuid4(),
        revision_identifier="commit-1",
        source_hash="tree-hash",
        total_files=5,
        total_bytes=sum(a.size_bytes for a in artifacts),
        created_at=now,
    )

    factory = AnalysisInputFactory(
        revision_repo=FakeRevisionRepository([revision]),
        artifact_repo=FakeArtifactRepository(artifacts),
        storage_service=FakeStorageService(files_content),
        page_size=2,  # Force multiple pages
    )

    analysis_input = factory.build_analysis_input(
        analysis_id=analysis_id,
        project_id=project_id,
        repository_id=repo_id,
        revision_id=revision_id,
    )

    assert analysis_input.total_files == 5
    assert len(analysis_input.artifact_catalog.artifacts) == 5


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/main.py", True),
        ("README.md", True),
        (".gitignore", True),
        ("nested/deep/directory/file.ts", True),
        ("../etc/passwd", False),
        ("/root/file.py", False),
        ("foo/../bar", False),
        ("foo/./bar", False),
        ("foo//bar", False),
        ("", False),
        ("null\0byte", False),
    ],
)
def test_is_safe_relative_path(path: str, expected: bool) -> None:
    assert is_safe_relative_path(path) is expected


def test_platform_factory_preserves_immutable_input_and_bounded_content() -> None:
    project_id = uuid4()
    repository_id = uuid4()
    revision_id = uuid4()
    artifact_id = uuid4()

    class Gateway(PlatformRepositoryGateway):
        requested_max_bytes: int | None = None

        def get_manifest(self, *_: UUID) -> PlatformSnapshotManifest:
            artifact = PlatformArtifact(
                id=artifact_id,
                project_id=project_id,
                repository_id=repository_id,
                revision_id=revision_id,
                path="src/main.py",
                size_bytes=4,
                content_hash=hashlib.sha256(b"data").hexdigest(),
                category=ArtifactCategory.SOURCE_CODE,
                support_level=SupportLevel.FULL,
            )
            return PlatformSnapshotManifest(
                id=revision_id,
                project_id=project_id,
                repository_id=repository_id,
                revision_identifier="abc123",
                source_hash="tree",
                total_files=1,
                total_bytes=4,
                artifacts=(artifact,),
            )

        def read_artifact(
            self,
            _project_id: UUID,
            _repository_id: UUID,
            _revision_id: UUID,
            _artifact_id: UUID,
            *,
            max_bytes: int,
        ) -> bytes:
            self.requested_max_bytes = max_bytes
            return b"data"[:max_bytes]

    gateway = Gateway()
    analysis_input = PlatformAnalysisInputFactory(gateway).build_analysis_input(
        uuid4(), project_id, repository_id, revision_id
    )
    artifact = analysis_input.artifact_catalog.artifacts[0]

    assert analysis_input.snapshot_id == revision_id
    assert analysis_input.content_reader.read_bytes(artifact, max_bytes=2) == b"da"
    assert gateway.requested_max_bytes == 2
    assert "storage_key" not in type(artifact).__annotations__


def test_http_platform_gateway_reuses_injected_client_and_authorizes_reads() -> None:
    project_id = uuid4()
    repository_id = uuid4()
    revision_id = uuid4()
    artifact_id = uuid4()
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["X-Service-Token"] == "service-secret"
        if request.url.path.endswith("/manifest"):
            return httpx.Response(
                200,
                json={
                    "revision": {
                        "id": str(revision_id),
                        "project_id": str(project_id),
                        "repository_id": str(repository_id),
                        "revision_identifier": "main",
                        "source_hash": "tree",
                        "total_files": 1,
                        "total_bytes": 4,
                    },
                    "artifacts": [
                        {
                            "id": str(artifact_id),
                            "project_id": str(project_id),
                            "repository_id": str(repository_id),
                            "revision_id": str(revision_id),
                            "path": "src/main.py",
                            "size_bytes": 4,
                            "content_hash": hashlib.sha256(b"data").hexdigest(),
                            "category": ArtifactCategory.SOURCE_CODE.value,
                            "support_level": SupportLevel.FULL.value,
                        }
                    ],
                },
            )
        assert request.url.params["max_bytes"] == "2"
        return httpx.Response(200, content=b"data")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    gateway = HttpPlatformRepositoryGateway(
        "http://platform.test/api/v1/internal",
        "service-secret",
        5.0,
        client=client,
    )

    manifest = gateway.get_manifest(project_id, repository_id, revision_id)
    content = gateway.read_artifact(
        project_id,
        repository_id,
        revision_id,
        artifact_id,
        max_bytes=2,
    )
    gateway.close()

    assert manifest.artifacts[0].id == artifact_id
    assert content == b"da"
    assert len(requests) == 2
    assert not client.is_closed
    client.close()
