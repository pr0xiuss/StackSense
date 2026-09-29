"""Archive acquisition handler supporting .zip, .tar, .tar.gz, and .tgz formats."""

import shutil
from pathlib import Path

from backend.platform.ingestion.application.acquisition import (
    AcquisitionHandler,
    AcquisitionResult,
)
from backend.platform.ingestion.domain.constants import SourceType
from backend.platform.ingestion.infra.acquisition.archive_extractor import (
    ArchiveExtractor,
)


class ArchiveAcquisitionHandler(AcquisitionHandler):
    """Safely acquires and extracts repository source archives."""

    def can_handle(self, source_type: str) -> bool:
        return source_type.lower() in ("archive", SourceType.ARCHIVE.value, "zip")

    def acquire(
        self,
        source_reference: str,
        revision_identifier: str | None,
        temp_root: Path,
    ) -> AcquisitionResult:
        archive_path = Path(source_reference)
        extracted = ArchiveExtractor.extract(
            archive_path=archive_path,
            destination_dir=temp_root / "extracted",
            unwrap_single_root=True,
        )

        resolved_rev = revision_identifier or extracted.source_hash[:12]

        return AcquisitionResult(
            root_path=extracted.root_path,
            revision_identifier=resolved_rev,
            source_hash=extracted.source_hash,
            total_source_bytes=extracted.archive_size,
            cleanup_fn=lambda: shutil.rmtree(temp_root, ignore_errors=True),
        )
