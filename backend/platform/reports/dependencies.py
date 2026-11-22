"""Dependency injection providers for report generation, storage, and API services.

Composition only; fail-closed behavior ensures that an unapproved or
partially configured report environment does not announce production readiness.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from backend.platform.delivery.contracts import (
    HandlerProfile,
    ProducerProfile,
    WorkKind,
    WorkSlot,
)
from backend.platform.delivery.registry import HandlerRegistration
from backend.platform.reports.artifacts import LocalReportArtifactStore
from backend.platform.reports.configuration import (
    ReportLimits,
    ReportRuntimeConfig,
)
from backend.platform.reports.cursors import ReportCursorSigner
from backend.platform.reports.pdf import ReportLabPdfRenderer
from backend.platform.reports.preparation import ReportPreparer
from backend.platform.reports.repository import (
    ReportDatabaseReadAuthority,
    ReportPublicationPort,
)
from backend.platform.reports.service import (
    ReportReader,
    ReportService,
    ReportWorkHandler,
)


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
        raw_secret = "0" * 32
    else:
        raw_secret = secret.get_secret_value()
    return ReportCursorSigner(key_id="k1", secret=raw_secret, ttl=600)


def get_report_artifact_store(
    actor_id: UUID | None = None,
) -> LocalReportArtifactStore:
    """Build artifact store using database read authority."""
    from backend.platform.dependency_injection import get_database_engine

    limits = get_report_limits()
    authority = ReportDatabaseReadAuthority(
        get_database_engine(),
        limits,
        actor_id=actor_id,
        purpose="report" if actor_id is None else "api",
    )
    return LocalReportArtifactStore(authority, limits=limits)


def get_report_reader() -> ReportReader:
    """Return reader port wrapping the local artifact store."""
    return ReportReader(get_report_artifact_store())


def get_report_service(
    actor_id: UUID | None = None,
) -> ReportService:
    """Build ReportService with reader, limits, and cursor signer."""
    from backend.platform.dependency_injection import get_database_engine

    limits = get_report_limits()
    engine = get_database_engine()
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
    from backend.platform.analysis.application.dependencies import (
        get_analysis_lifecycle_service,
        get_architecture_query_service,
    )
    from backend.platform.config import get_settings
    from backend.platform.dependency_injection import get_database_settings
    from backend.platform.diagrams.dependencies import get_diagram_reader

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

    fingerprint = config.profile.profile_digest()
    limits = config.limits
    database_url = get_database_settings().database_url.get_secret_value()
    engine = create_engine(
        make_url(database_url).set(drivername="postgresql+psycopg"),
        poolclass=NullPool,
        connect_args={"connect_timeout": int(limits.total_execution_timeout_seconds)},
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

    preparer = ReportPreparer(
        architecture_query=get_architecture_query_service(),
        analysis_lifecycle=get_analysis_lifecycle_service(),
        diagram_reader=get_diagram_reader(),
    )
    renderer = ReportLabPdfRenderer()

    handler = ReportWorkHandler(
        binding=binding,
        engine_or_session=engine,
        preparer=preparer,
        renderer=renderer,
        limits=limits,
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
