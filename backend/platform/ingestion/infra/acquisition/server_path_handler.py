"""Server filesystem path acquisition handler (Advanced)."""

import hashlib
import shutil
from pathlib import Path

from backend.platform.config import get_settings
from backend.platform.errors import (
    ServerPathNotAllowedError,
    ServerPathNotFoundError,
    SourceValidationError,
    UnsupportedArchiveFormatError,
)
from backend.platform.ingestion.application.acquisition import (
    AcquisitionHandler,
    AcquisitionResult,
)
from backend.platform.ingestion.domain.constants import (
    MAX_REPOSITORY_SIZE_BYTES,
    SourceType,
)
from backend.platform.ingestion.infra.acquisition.archive_extractor import (
    ArchiveExtractor,
)


class ServerPathAcquisitionHandler(AcquisitionHandler):
    """Safely acquires repository content from a controlled server filesystem path."""

    def __init__(self, allowed_roots: list[str] | None = None) -> None:
        self._custom_allowed_roots = allowed_roots

    def can_handle(self, source_type: str) -> bool:
        return source_type.lower() in (
            "server_path",
            SourceType.SERVER_PATH.value,
            "directory",
            "dir",
            "local",
        )

    def acquire(
        self,
        source_reference: str,
        revision_identifier: str | None,
        temp_root: Path,
    ) -> AcquisitionResult:
        settings = get_settings()
        roots_config = (
            self._custom_allowed_roots
            if self._custom_allowed_roots is not None
            else settings.allowed_source_roots
        )
        allowed_roots = [Path(r).resolve() for r in roots_config]

        candidate = Path(source_reference).resolve()

        # Jail verification against allowed roots (also detects symlink escape)
        is_allowed = False
        for root in allowed_roots:
            try:
                candidate.relative_to(root)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            raise ServerPathNotAllowedError(
                f"Server path '{source_reference}' is outside the allowed source roots."
            )

        if not candidate.exists():
            raise ServerPathNotFoundError(
                f"Server path does not exist: '{source_reference}'."
            )

        # Handle file archives (.zip, .tar, .tar.gz, .tgz)
        if candidate.is_file():
            name_lower = candidate.name.lower()
            is_supported = (
                name_lower.endswith(".zip")
                or name_lower.endswith(".tar")
                or name_lower.endswith(".tar.gz")
                or name_lower.endswith(".tgz")
            )
            if not is_supported:
                raise UnsupportedArchiveFormatError(
                    f"Server path file '{candidate.name}' is not a supported "
                    "archive format (.zip, .tar, .tar.gz, .tgz)."
                )

            extracted = ArchiveExtractor.extract(
                archive_path=candidate,
                destination_dir=temp_root / "extracted",
                unwrap_single_root=False,
            )
            resolved_rev = revision_identifier or extracted.source_hash[:12]
            return AcquisitionResult(
                root_path=extracted.root_path,
                revision_identifier=resolved_rev,
                source_hash=extracted.source_hash,
                total_source_bytes=extracted.archive_size,
                cleanup_fn=lambda: shutil.rmtree(temp_root, ignore_errors=True),
            )

        # Handle staged directories (for staging/development workflows)
        # Note on in-place lifecycle (IR-M4-004):
        # Server filesystem directories are managed by administrators within
        # configured allowed_source_roots. StackSense inspects and ingests
        # these files directly in-place rather than creating an expensive
        # copy on disk. Crucially, cleanup_fn is None to ensure that the
        # persistent server directory is never deleted upon job completion.
        if candidate.is_dir():
            hasher = hashlib.sha256()
            total_bytes = 0

            for file_path in sorted(p for p in candidate.rglob("*") if p.is_file()):
                try:
                    rel_path = file_path.relative_to(candidate).as_posix()
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
                root_path=candidate,
                revision_identifier=resolved_rev,
                source_hash=source_hash,
                total_source_bytes=total_bytes,
                cleanup_fn=None,  # Do not delete server directory
            )

        raise SourceValidationError(
            f"Server path is neither a file nor a directory: '{source_reference}'."
        )
