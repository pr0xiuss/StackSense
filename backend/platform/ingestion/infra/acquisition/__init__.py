"""Acquisition infrastructure handlers."""

from backend.platform.ingestion.infra.acquisition.directory_handler import (
    LocalDirectoryAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.zip_handler import (
    ZipArchiveAcquisitionHandler,
)

__all__ = [
    "LocalDirectoryAcquisitionHandler",
    "ZipArchiveAcquisitionHandler",
]
