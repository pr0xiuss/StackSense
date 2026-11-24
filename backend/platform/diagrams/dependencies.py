"""Application composition only; no implicit dispatch or insecure store fallback."""

from __future__ import annotations

import os
import pwd
import stat
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from backend.platform.analysis.architecture.dto import ArchitectureVersionResponse
from backend.platform.delivery.contracts import (
    DiagramTemplate,
    HandlerProfile,
    ProducerProfile,
    WorkKind,
    WorkSlot,
)
from backend.platform.delivery.registry import HandlerRegistration
from backend.platform.diagrams import artifacts
from backend.platform.diagrams.artifacts import (
    CandidateArtifactWriter,
    LocalGeneratedArtifactStore,
)
from backend.platform.diagrams.configuration import DiagramLimits, DiagramRuntimeConfig
from backend.platform.diagrams.contracts import PreparedDiagram
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.layout import (
    ElkLayoutEngine,
    create_layout_profile,
    verify_installation,
)
from backend.platform.diagrams.linux_runtime import delegation_root, protected_regular
from backend.platform.diagrams.query import (
    DiagramSourceAdapter,
    SourceBudget,
    canonical_read_source,
)
from backend.platform.diagrams.repository import (
    DatabaseReadAuthority,
    DiagramPublicationPort,
    DiagramRepository,
)
from backend.platform.diagrams.service import (
    DiagramReader,
    DiagramService,
    DiagramWorkHandler,
)


def _storage_preflight() -> None:
    """Fail closed; a proof installation must never announce production capability."""
    root = Path("/opt/stacksense/diagram-artifacts")
    if any(
        (root / "deployment" / name).exists()
        for name in (
            "proof-enabled",
            "seal-fault-cases.json",
        )
    ):
        raise ValueError("diagram_store_unavailable")
    protected_regular(root / "seal-generation")
    worker, owner = pwd.getpwnam("stacksense-worker"), pwd.getpwnam(
        "stacksense-artifacts"
    )
    if os.geteuid() != worker.pw_uid or owner.pw_uid in (0, worker.pw_uid):
        raise ValueError("diagram_store_unavailable")
    for name in ("sealed", "staging", "locks"):
        path = artifacts.STORE_ROOT / name
        info = path.lstat()
        expected = worker.pw_uid if name == "staging" else owner.pw_uid
        if (
            path.is_symlink()
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != expected
            or info.st_mode & 0o022
        ):
            raise ValueError("diagram_store_unavailable")
    if not os.access(artifacts.STORE_ROOT / "staging", os.W_OK) or os.access(
        artifacts.STORE_ROOT / "sealed", os.W_OK
    ):
        raise ValueError("diagram_store_unavailable")


def configured_diagram_registrations() -> tuple[HandlerRegistration, ...]:
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import (
        get_database_settings,
    )

    settings = get_settings()
    if (
        not settings.diagram_enabled
        or not settings.diagram_operational_approval
        or settings.diagram_deployment_json is None
    ):
        return ()
    config = DiagramRuntimeConfig.model_validate_json(
        settings.diagram_deployment_json.get_secret_value()
    )
    if not config.enabled:
        return ()
    # No partial registration: all prerequisites and profiles must validate first.
    lock = verify_installation()
    delegation_root()
    _storage_preflight()
    fonts = DiagramFonts()
    try:
        font_digest = fonts.manifest_digest()
    finally:
        fonts.close()
    fingerprint = config.fingerprint(
        {**{f.path: f.sha256 for f in lock.files}, "font_manifest": font_digest}
    )
    limits = config.operational_limits
    database_url = get_database_settings().database_url.get_secret_value()
    # M4 owns these short metadata checkouts; bound connection acquisition too.
    metadata_engine = create_engine(
        make_url(database_url).set(drivername="postgresql+psycopg"),
        poolclass=NullPool,
        connect_args={"connect_timeout": limits.lock_seconds},
    )
    repository = DiagramRepository(metadata_engine)

    def source(budget: SourceBudget) -> AbstractContextManager[DiagramSourceAdapter]:
        return canonical_read_source(database_url, budget)

    registrations = []
    for template in DiagramTemplate:
        binding = HandlerProfile(
            slot=WorkSlot(kind=WorkKind.DIAGRAM, template=template),
            profile=ProducerProfile(
                producer_id="stacksense.diagrams",
                producer_version="1.0.0",
                generator_version="1.0.0",
                output_schema_version="1.0.0",
                configuration_fingerprint=fingerprint,
            ),
        )
        name = {
            DiagramTemplate.OVERVIEW: "architecture_compound_v1",
            DiagramTemplate.COMPONENT: "architecture_compound_v1",
            DiagramTemplate.DEPENDENCY: "dependency_layered_v1",
            DiagramTemplate.DATA_FLOW: "static_flow_v1",
        }[template]
        registrations.append(
            HandlerRegistration(
                binding=binding,
                publication_factory=DiagramPublicationPort,
                handler=DiagramWorkHandler(
                    binding=binding,
                    repository=repository,
                    source=source,
                    layout=ElkLayoutEngine(limits, font_manifest_digest=font_digest),
                    profile=create_layout_profile(name, lock, font_digest),
                    limits=limits,
                    writer=CandidateArtifactWriter(),
                ),
            )
        )
    return tuple(registrations)


def get_diagram_reader() -> DiagramReader:
    """Trusted report consumer factory; B4 provides authorized actor-scoped reads."""
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import get_database_engine

    raw = get_settings().diagram_deployment_json
    if raw is None:
        raise ValueError("diagram_store_unavailable")
    config = DiagramRuntimeConfig.model_validate_json(raw.get_secret_value())
    limits = config.operational_limits
    return DiagramReader(
        LocalGeneratedArtifactStore(
            DatabaseReadAuthority(get_database_engine(), limits, actor_id=None),
            limits,
        ),
        limits,
    )


def get_diagram_limits() -> DiagramLimits:
    from backend.platform.config import get_settings
    from backend.platform.diagrams.configuration import DiagramLimits

    raw = get_settings().diagram_deployment_json
    if raw is None or not raw.get_secret_value():
        return DiagramLimits()
    try:
        return DiagramRuntimeConfig.model_validate_json(
            raw.get_secret_value()
        ).operational_limits
    except ValueError as exc:
        raise ValueError("diagram_runtime_unavailable") from exc


def get_diagram_service(actor_id: UUID) -> DiagramService:
    """Read composition is independent of new-work capability and Node startup."""
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import (
        get_database_settings,
    )
    from backend.platform.diagrams.cursors import CursorSigner
    from backend.platform.diagrams.repository import DiagramQueryRepository

    raw = get_settings().diagram_deployment_json
    if raw is None:
        raise ValueError("diagram_store_unavailable")
    try:
        config = DiagramRuntimeConfig.model_validate_json(raw.get_secret_value())
    except ValueError as exc:
        raise ValueError("diagram_runtime_unavailable") from exc
    limits = config.operational_limits
    url = get_database_settings().database_url.get_secret_value()
    engine = create_engine(
        make_url(url).set(drivername="postgresql+psycopg"),
        poolclass=NullPool,
        connect_args={"connect_timeout": limits.lock_seconds},
    )

    def source(budget: SourceBudget) -> AbstractContextManager[DiagramSourceAdapter]:
        return canonical_read_source(url, budget)

    def layout(base: PreparedDiagram) -> ElkLayoutEngine:
        lock = verify_installation()
        delegation_root()
        with_fonts = DiagramFonts()
        try:
            font_digest = with_fonts.manifest_digest()
        finally:
            with_fonts.close()
        expected = create_layout_profile(base.layout.profile.id, lock, font_digest)
        if expected != base.layout.profile:
            raise ValueError("diagram_runtime_unavailable")
        return ElkLayoutEngine(limits, font_manifest_digest=font_digest)

    return DiagramService(
        DiagramQueryRepository(engine),
        DiagramReader(
            LocalGeneratedArtifactStore(
                DatabaseReadAuthority(engine, limits, actor_id=actor_id, purpose="api"),
                limits,
            ),
            limits,
        ),
        limits,
        CursorSigner(
            config.cursor_key_id, config.cursor_secret, limits.cursor_ttl_seconds
        ),
        source,
        layout,
    )


def get_diagram_version_reader() -> (
    Callable[[UUID, UUID, float], ArchitectureVersionResponse]
):
    """Lazy public canonical header reader with an owned, cancellable session."""
    from backend.platform.dependency_injection import get_database_settings

    limits = get_diagram_limits()
    url = get_database_settings().database_url.get_secret_value()

    def read(
        version: UUID, project: UUID, deadline: float
    ) -> ArchitectureVersionResponse:
        budget = SourceBudget(limits, deadline, lambda: None)
        with canonical_read_source(url, budget) as source:
            return source.version(version, project, budget)

    return read
