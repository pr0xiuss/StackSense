"""Acquisition infrastructure handlers."""

from backend.platform.ingestion.infra.acquisition.archive_extractor import (
    ArchiveExtractor,
    ExtractedArchive,
)
from backend.platform.ingestion.infra.acquisition.archive_handler import (
    ArchiveAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.directory_handler import (
    LocalDirectoryAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.github_handler import (
    GitHubAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.server_path_handler import (
    ServerPathAcquisitionHandler,
)
from backend.platform.ingestion.infra.acquisition.zip_handler import (
    ZipArchiveAcquisitionHandler,
)

__all__ = [
    "ArchiveAcquisitionHandler",
    "ArchiveExtractor",
    "ExtractedArchive",
    "GitHubAcquisitionHandler",
    "LocalDirectoryAcquisitionHandler",
    "ServerPathAcquisitionHandler",
    "ZipArchiveAcquisitionHandler",
]
