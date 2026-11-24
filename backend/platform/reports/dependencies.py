"""Dependency injection providers for report generation, storage, and API services.

Composition only; fail-closed behavior ensures that an unapproved or
partially configured report environment does not announce production readiness.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from time import monotonic
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

from backend.platform.delivery.contracts import (
    HandlerProfile,
    ProducerProfile,
    WorkExecutionContext,
    WorkKind,
    WorkSlot,
)
from backend.platform.delivery.registry import HandlerRegistration
from backend.platform.reports.artifacts import (
    CandidateReportWriter,
    LocalReportArtifactStore,
)
from backend.platform.reports.configuration import (
    ReportLimits,
    ReportRuntimeConfig,
)
from backend.platform.reports.contracts import (
    PreparedReport,
    ReportInputSnapshot,
    ReportSpec,
)
from backend.platform.reports.cursors import ReportCursorSigner
from backend.platform.reports.model import c4_digest
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.render_runtime import IsolatedReportRenderRuntime
from backend.platform.reports.repository import (
    ReportDatabaseReadAuthority,
    ReportPublicationPort,
    metadata_operation,
    metadata_session,
)
from backend.platform.reports.service import (
    ReportReader,
    ReportService,
    ReportWorkHandler,
)


class TransactionalReportPreparer(ReportPreparer):
    """Compose frozen public readers within one M5-owned read-only snapshot."""

    def __init__(self, engine: Engine, config: ReportRuntimeConfig) -> None:
        self.engine, self.config = engine, config
        self.profile, self.limits = config.profile, config.limits

    def prepare(
        self, context: WorkExecutionContext
    ) -> tuple[ReportSpec, ReportInputSnapshot, PreparedReport]:
        from backend.platform.analysis.application.dependencies import (
            get_analysis_lifecycle_service,
            get_architecture_query_service,
            get_platform_repository_gateway,
        )
        from backend.platform.config import get_settings
        from backend.platform.diagrams.dependencies import get_diagram_reader

        remaining = min(
            self.limits.prepare_timeout_seconds,
            (context.deadline - datetime.now(UTC)).total_seconds(),
        )
        with (
            metadata_operation(monotonic() + remaining),
            metadata_session(
                self.engine, seconds=self.limits.prepare_timeout_seconds, read_only=True
            ) as session,
            contextmanager(get_platform_repository_gateway)(
                settings=get_settings()
            ) as gateway,
        ):
            preparer = ReportPreparer(
                get_architecture_query_service(session=session),
                get_analysis_lifecycle_service(session=session, source_gateway=gateway),
                get_diagram_reader(),
                self.config,
            )
            return preparer.prepare(context)


def get_report_limits() -> ReportLimits:
    """Return configured operational limits or default boundaries."""
    from backend.platform.config import get_settings

    raw = get_settings().report_deployment_json
    if raw is None or not raw.get_secret_value():
        return ReportLimits()
    try:
        return ReportRuntimeConfig.model_validate_json(raw.get_secret_value()).limits
    except ValueError as exc:
        raise ValueError("report_runtime_unavailable") from exc


def get_cursor_signer() -> ReportCursorSigner:
    """Return cursor signer configured with secret or secure test seed."""
    from backend.platform.config import get_settings

    settings = get_settings()
    secret = settings.report_cursor_secret
    if secret is None or len(secret.get_secret_value()) < 32:
        raise ValueError("report_runtime_unavailable")
    else:
        raw_secret = secret.get_secret_value()
    return ReportCursorSigner(key_id="k1", secret=raw_secret, ttl=600)


def get_report_artifact_store(
    actor_id: UUID | None = None,
) -> LocalReportArtifactStore:
    """Build artifact store using database read authority."""
    limits = get_report_limits()
    authority = ReportDatabaseReadAuthority(
        get_report_engine(),
        limits,
        actor_id=actor_id,
        purpose="export" if actor_id is None else "api",
    )
    raw = get_settings_config()
    return LocalReportArtifactStore(
        authority, limits=limits, root=Path(raw.storage_root)
    )


def get_settings_config() -> ReportRuntimeConfig:
    from backend.platform.config import get_settings

    raw = get_settings().report_deployment_json
    return (
        ReportRuntimeConfig()
        if raw is None
        else ReportRuntimeConfig.model_validate_json(raw.get_secret_value())
    )


@lru_cache(maxsize=1)
def get_report_engine() -> Engine:
    from backend.platform.dependency_injection import get_database_settings

    return create_engine(
        make_url(get_database_settings().database_url.get_secret_value()).set(
            drivername="postgresql+psycopg"
        ),
        poolclass=NullPool,
        connect_args={"connect_timeout": 1},
    )


def get_report_reader() -> ReportReader:
    """Return reader port wrapping the local artifact store."""
    return ReportReader(get_report_artifact_store())


def get_report_service(
    actor_id: UUID | None = None,
) -> ReportService:
    """Build ReportService with reader, limits, and cursor signer."""
    limits = get_report_limits()
    engine = get_report_engine()
    store = get_report_artifact_store(actor_id=actor_id)
    reader = ReportReader(store, limits=limits)
    signer = get_cursor_signer()
    return ReportService(
        engine=engine,
        reader=reader,
        limits=limits,
        cursor_signer=signer,
        actor_id=actor_id,
    )


def create_report_publication_factory() -> type[ReportPublicationPort]:
    """Return ReportPublicationPort class for M1 registration."""
    return ReportPublicationPort


def configured_report_registrations() -> tuple[HandlerRegistration, ...]:
    """Build HandlerRegistration for report work if enabled and approved."""
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import get_database_settings

    settings = get_settings()
    if (
        not settings.report_enabled
        or not settings.report_operational_approval
        or settings.report_deployment_json is None
    ):
        return ()

    config = ReportRuntimeConfig.model_validate_json(
        settings.report_deployment_json.get_secret_value()
    )
    if not config.production_registration_enabled:
        return ()

    fingerprint = c4_digest(
        "ss.report.configuration",
        {
            "profile": config.profile.model_dump(mode="python"),
            "limits": config.limits.model_dump(mode="python"),
        },
    )
    limits = config.limits
    database_url = get_database_settings().database_url.get_secret_value()
    engine = create_engine(
        make_url(database_url).set(drivername="postgresql+psycopg"),
        poolclass=NullPool,
        connect_args={"connect_timeout": 1},
    )

    binding = HandlerProfile(
        slot=WorkSlot(kind=WorkKind.REPORT, template="architecture_analysis"),
        profile=ProducerProfile(
            producer_id="stacksense.reports",
            producer_version="1.0.0",
            generator_version="1.0.0",
            output_schema_version="1.0.0",
            configuration_fingerprint=fingerprint,
        ),
    )

    preparer = TransactionalReportPreparer(engine, config)
    renderer = IsolatedReportRenderRuntime(limits)

    handler = ReportWorkHandler(
        binding=binding,
        engine_or_session=engine,
        preparer=preparer,
        renderer=renderer,
        limits=limits,
        writer_factory=lambda att, cid, aid, lim: CandidateReportWriter(
            att, cid, aid, lim, Path(config.storage_root)
        ),
    )

    return (
        HandlerRegistration(
            binding=binding,
            publication_factory=ReportPublicationPort,
            handler=handler,
        ),
    )


__all__ = [
    "configured_report_registrations",
    "create_report_publication_factory",
    "get_cursor_signer",
    "get_report_artifact_store",
    "get_report_limits",
    "get_report_reader",
    "get_report_service",
]
