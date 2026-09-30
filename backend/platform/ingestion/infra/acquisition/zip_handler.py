"""Zip acquisition handler (legacy wrapper around ArchiveAcquisitionHandler)."""

from backend.platform.ingestion.infra.acquisition.archive_handler import (
    ArchiveAcquisitionHandler,
)


class ZipArchiveAcquisitionHandler(ArchiveAcquisitionHandler):
    """Safely extracts zip and tar archive repository sources with security defenses."""
