"""Closed configuration and resource limits for Architecture Analysis Report."""

from __future__ import annotations

import hashlib

from pydantic import Field

from backend.platform.reports.contracts import (
    C4_VERSION,
    FrozenReportModel,
    PositiveInt,
)
from backend.platform.reports.model import c4_canonical_bytes


class RendererProfile(FrozenReportModel):
    """Pinned rendering profile guaranteeing deterministic output formatting."""

    profile_id: str = "reportlab_dejavu_v1"
    version: str = "1.0.0"
    renderer: str = "reportlab"
    renderer_version: str = "5.1.0"
    pypdf_version: str = "7.1.1"
    font_profile: str = "dejavu_paths_2_37_v1"
    page_size: str = "A4"
    orientation: str = "portrait"
    margin_points: float = 36.0
    min_readable_font_pt: float = 6.0
    max_tile_columns: int = 4
    max_tile_rows: int = 4
    deterministic_mode: str = "pinned_canonical_v1"

    def profile_digest(self) -> str:
        payload = ["ss.renderer.profile", C4_VERSION, self.model_dump(mode="python")]
        return hashlib.sha256(c4_canonical_bytes(payload)).hexdigest()


class ReportLimits(FrozenReportModel):
    """Initial engineering settings and hard safety ceilings per §15.5.8."""

    # Public source limits
    max_source_page_size: PositiveInt = 100
    max_cumulative_source_rows: PositiveInt = 200_000
    max_source_calls: PositiveInt = 2_500
    hard_max_cumulative_rows: PositiveInt = 500_000

    # Content selection limits
    max_selected_inventory: PositiveInt = 200
    max_selected_references: PositiveInt = 2_000
    max_authoritative_diagnostics: PositiveInt = 1_000
    hard_max_inventory: PositiveInt = 2_000
    hard_max_references: PositiveInt = 10_000
    hard_max_diagnostics: PositiveInt = 10_000

    # Byte and page ceilings
    max_spec_bytes: PositiveInt = 16 * 1024 * 1024  # 16 MiB
    max_embedded_assets_bytes: PositiveInt = 64 * 1024 * 1024  # 64 MiB
    max_pdf_bytes: PositiveInt = 32 * 1024 * 1024  # 32 MiB
    max_staged_bytes: PositiveInt = 128 * 1024 * 1024  # 128 MiB
    hard_max_pdf_bytes: PositiveInt = 64 * 1024 * 1024  # 64 MiB

    max_pdf_pages: PositiveInt = 128
    hard_max_pdf_pages: PositiveInt = 256
    max_diagram_tiles: PositiveInt = 16
    hard_max_diagram_tiles: PositiveInt = 64
    max_text_field_bytes: PositiveInt = 16 * 1024  # 16 KiB

    # Timeouts (seconds)
    prepare_timeout_seconds: float = 120.0
    render_timeout_seconds: float = 60.0
    total_execution_timeout_seconds: float = 240.0
    read_timeout_seconds: float = 15.0
    watchdog_kill_grace_seconds: float = 2.0

    # Child memory and concurrency
    child_memory_limit_mb: PositiveInt = 512
    max_concurrent_local_renders: PositiveInt = 1
    max_concurrent_project_renders: PositiveInt = 1

    # Cleanup, pins, and cursors
    orphan_grace_seconds: float = 300.0
    max_history_page_size: PositiveInt = 20
    cursor_ttl_seconds: float = 600.0
    max_cursor_bytes: PositiveInt = 4096
    max_pins_per_generation: PositiveInt = 100
    pin_ttl_seconds: float = 300.0

    def limits_digest(self) -> str:
        payload = ["ss.report.limits", C4_VERSION, self.model_dump(mode="python")]
        return hashlib.sha256(c4_canonical_bytes(payload)).hexdigest()


class ReportRuntimeConfig(FrozenReportModel):
    """Runtime configuration uniting profile, limits, and storage paths."""

    profile: RendererProfile = Field(default_factory=RendererProfile)
    limits: ReportLimits = Field(default_factory=ReportLimits)
    storage_root: str = "/var/lib/stacksense/reports"
    production_registration_enabled: bool = False
    cursor_key_id: str = "report-cursor-key-v1"
    cursor_secret: str = "report-cursor-hmac-secret-development"
