"""Local directory acquisition handler."""

import hashlib
from pathlib import Path

from backend.platform.errors import SourceValidationError
from backend.platform.ingestion.application.acquisition import (
    AcquisitionHandler,
    AcquisitionResult,
)
from backend.platform.ingestion.domain.constants import (
    MAX_REPOSITORY_SIZE_BYTES,
)


class LocalDirectoryAcquisitionHandler(AcquisitionHandler):
    """Acquires a repository directly from a local staging or filesystem directory."""

    def can_handle(self, source_type: str) -> bool:
        return source_type.lower() in {"directory", "dir", "local"}

    def acquire(
        self,
        source_reference: str,
        revision_identifier: str | None,
        temp_root: Path,
    ) -> AcquisitionResult:
        dir_path = Path(source_reference).resolve()
        if not dir_path.is_dir():
            raise SourceValidationError(
                f"Source directory does not exist or is not a directory: "
                f"{source_reference}"
            )

        hasher = hashlib.sha256()
        total_bytes = 0

        # Deterministically iterate regular files to compute source hash and size
        for file_path in sorted(p for p in dir_path.rglob("*") if p.is_file()):
            try:
                rel_path = file_path.relative_to(dir_path).as_posix()
            except ValueError as exc:
                raise SourceValidationError(
                    f"File path escapes directory root: {file_path}"
                ) from exc

            hasher.update(rel_path.encode("utf-8"))
            file_size = file_path.stat().st_size
            total_bytes += file_size
            if total_bytes > MAX_REPOSITORY_SIZE_BYTES:
                raise SourceValidationError(
                    f"Total repository size ({total_bytes} bytes) exceeds limit "
                    f"({MAX_REPOSITORY_SIZE_BYTES} bytes)."
                )

        source_hash = hasher.hexdigest()
        resolved_rev = revision_identifier or source_hash[:12]

        return AcquisitionResult(
            root_path=dir_path,
            revision_identifier=resolved_rev,
            source_hash=source_hash,
            total_source_bytes=total_bytes,
            cleanup_fn=None,  # Local source directory is not cleaned up
        )
