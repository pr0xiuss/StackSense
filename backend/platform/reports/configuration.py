"""Closed configuration and resource limits for Architecture Analysis Report."""

from __future__ import annotations

import hashlib
from typing import Literal, Self

from pydantic import Field, model_validator

from backend.platform.reports.contracts import (
    C4_VERSION,
    FrozenReportModel,
    PositiveInt,
)
from backend.platform.reports.model import c4_canonical_bytes


class RendererProfile(FrozenReportModel):
    """Pinned rendering profile guaranteeing deterministic output formatting."""

    profile_id: Literal["reportlab_dejavu_v1"] = "reportlab_dejavu_v1"
    version: Literal["1.0.0"] = "1.0.0"
    renderer: Literal["reportlab"] = "reportlab"
    renderer_version: Literal["5.1.0"] = "5.1.0"
    pypdf_version: Literal["7.1.1"] = "7.1.1"
    font_profile: Literal["dejavu_paths_2_37_v1"] = "dejavu_paths_2_37_v1"
    page_size: Literal["A4"] = "A4"
    orientation: Literal["portrait"] = "portrait"
    margin_points: int = 36
    min_readable_font_pt: int = 6
    max_tile_columns: int = 4
    max_tile_rows: int = 4
    deterministic_mode: Literal["pinned_canonical_v1"] = "pinned_canonical_v1"

    @model_validator(mode="after")
    def geometry(self) -> Self:
        if (
            self.margin_points != 36
            or not 6 <= self.min_readable_font_pt <= 14
            or not 1 <= self.max_tile_columns <= 4
            or not 1 <= self.max_tile_rows <= 4
        ):
            raise ValueError("report renderer profile unsupported")
        return self

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
    prepare_timeout_seconds: PositiveInt = 120
    render_timeout_seconds: PositiveInt = 60
    total_execution_timeout_seconds: PositiveInt = 240
    read_timeout_seconds: PositiveInt = 15
    watchdog_kill_grace_seconds: PositiveInt = 2

    # Child memory and concurrency
    child_memory_limit_mb: PositiveInt = 512
    max_concurrent_local_renders: PositiveInt = 1
    max_concurrent_project_renders: PositiveInt = 1

    # Cleanup, pins, and cursors
    orphan_grace_seconds: PositiveInt | None = None
    max_history_page_size: PositiveInt = 20
    cursor_ttl_seconds: PositiveInt = 600
    max_cursor_bytes: PositiveInt = 4096
    max_pins_per_generation: PositiveInt = 100
    pin_ttl_seconds: PositiveInt = 60

    @model_validator(mode="after")
    def ceilings(self) -> Self:
        caps = {
            "max_source_page_size": 500,
            "max_cumulative_source_rows": 500_000,
            "max_source_calls": 5000,
            "max_selected_inventory": 2000,
            "max_selected_references": 10000,
            "max_authoritative_diagnostics": 10000,
            "max_spec_bytes": 64 * 1024 * 1024,
            "max_embedded_assets_bytes": 128 * 1024 * 1024,
            "max_pdf_bytes": 64 * 1024 * 1024,
            "max_staged_bytes": 256 * 1024 * 1024,
            "max_pdf_pages": 256,
            "max_diagram_tiles": 64,
            "max_text_field_bytes": 65536,
            "prepare_timeout_seconds": 240,
            "render_timeout_seconds": 120,
            "total_execution_timeout_seconds": 300,
            "read_timeout_seconds": 60,
            "watchdog_kill_grace_seconds": 2,
            "child_memory_limit_mb": 1024,
            "max_concurrent_local_renders": 1,
            "max_concurrent_project_renders": 1,
            "max_history_page_size": 100,
            "cursor_ttl_seconds": 600,
            "max_cursor_bytes": 4096,
            "max_pins_per_generation": 100,
            "pin_ttl_seconds": 180,
        }
        for name, cap in caps.items():
            if getattr(self, name) > cap:
                raise ValueError(f"report hard ceiling exceeded: {name}")
        if self.pin_ttl_seconds < self.read_timeout_seconds + 30:
            raise ValueError("report read pin must cover read and stream budgets")
        for name, cap in {
            "hard_max_cumulative_rows": 500000,
            "hard_max_inventory": 2000,
            "hard_max_references": 10000,
            "hard_max_diagnostics": 10000,
            "hard_max_pdf_bytes": 67108864,
            "hard_max_pdf_pages": 256,
            "hard_max_diagram_tiles": 64,
        }.items():
            if getattr(self, name) != cap:
                raise ValueError(f"report hard ceiling is immutable: {name}")
        return self

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
    cursor_secret: str | None = None
