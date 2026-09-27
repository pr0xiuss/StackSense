"""Zip archive acquisition handler."""

import hashlib
import shutil
import zipfile
from pathlib import Path

from backend.platform.errors import SourceValidationError
from backend.platform.ingestion.application.acquisition import (
    AcquisitionHandler,
    AcquisitionResult,
)
from backend.platform.ingestion.domain.constants import (
    MAX_ARCHIVE_NESTING_DEPTH,
    MAX_COMPRESSION_RATIO,
    MAX_DIRECTORY_DEPTH,
    MAX_EXTRACTED_SIZE_BYTES,
    MAX_PATH_LENGTH,
    MAX_REPOSITORY_FILE_COUNT,
    MAX_REPOSITORY_SIZE_BYTES,
)

ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z"}


class ZipArchiveAcquisitionHandler(AcquisitionHandler):
    """Safely extracts zip archive repository sources with security defenses."""

    def can_handle(self, source_type: str) -> bool:
        return source_type.lower() in {"archive", "zip"}

    def acquire(
        self,
        source_reference: str,
        revision_identifier: str | None,
        temp_root: Path,
    ) -> AcquisitionResult:
        archive_path = Path(source_reference)
        if not archive_path.is_file():
            raise SourceValidationError(
                f"Archive source does not exist: {source_reference}"
            )

        archive_size = archive_path.stat().st_size
        if archive_size > MAX_REPOSITORY_SIZE_BYTES:
            raise SourceValidationError(
                f"Archive size ({archive_size} bytes) exceeds limit "
                f"({MAX_REPOSITORY_SIZE_BYTES} bytes)."
            )

        hasher = hashlib.sha256()
        with open(archive_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        source_hash = hasher.hexdigest()

        if not zipfile.is_zipfile(archive_path):
            raise SourceValidationError("Source file is not a valid zip archive.")

        extracted_dir = temp_root / "extracted"
        extracted_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                members = zf.infolist()

                if len(members) > MAX_REPOSITORY_FILE_COUNT:
                    raise SourceValidationError(
                        f"Archive contains {len(members)} files, exceeding limit "
                        f"of {MAX_REPOSITORY_FILE_COUNT}."
                    )

                total_uncompressed = 0
                for member in members:
                    clean_name = member.filename.replace("\\", "/").strip("/")

                    if not clean_name:
                        continue

                    parts = clean_name.split("/")
                    if ".." in parts or clean_name.startswith("/") or ":" in clean_name:
                        raise SourceValidationError(
                            f"Path traversal detected in archive member: "
                            f"{member.filename}"
                        )

                    if len(clean_name) > MAX_PATH_LENGTH:
                        raise SourceValidationError(
                            f"Archive member path exceeds {MAX_PATH_LENGTH} "
                            f"characters: {clean_name}"
                        )

                    depth = len(parts) - (1 if member.is_dir() else 0)
                    if depth > MAX_DIRECTORY_DEPTH:
                        raise SourceValidationError(
                            f"Directory depth ({depth}) exceeds limit of "
                            f"{MAX_DIRECTORY_DEPTH}: {clean_name}"
                        )

                    # Check nested archive extensions
                    file_ext = Path(clean_name).suffix.lower()
                    if file_ext in ARCHIVE_EXTENSIONS:
                        archive_nesting = sum(
                            1
                            for part in parts
                            if Path(part).suffix.lower() in ARCHIVE_EXTENSIONS
                        )
                        if archive_nesting > MAX_ARCHIVE_NESTING_DEPTH:
                            raise SourceValidationError(
                                f"Archive nesting depth exceeds limit of "
                                f"{MAX_ARCHIVE_NESTING_DEPTH}: {clean_name}"
                            )

                    # Zip bomb defenses
                    total_uncompressed += member.file_size
                    if total_uncompressed > MAX_EXTRACTED_SIZE_BYTES:
                        raise SourceValidationError(
                            f"Uncompressed archive exceeds limit of "
                            f"{MAX_EXTRACTED_SIZE_BYTES} bytes."
                        )

                    if member.compress_size > 0 and member.file_size > 1024 * 1024:
                        ratio = member.file_size / member.compress_size
                        if ratio > MAX_COMPRESSION_RATIO:
                            raise SourceValidationError(
                                f"High compression ratio ({ratio:.1f}:1) detected on "
                                f"{clean_name}, exceeding safety limit."
                            )

                    # Extract regular files
                    if not member.is_dir():
                        dest_file = extracted_dir / clean_name
                        dest_file.parent.mkdir(parents=True, exist_ok=True)

                        resolved = dest_file.resolve()
                        if not str(resolved).startswith(str(extracted_dir.resolve())):
                            raise SourceValidationError(
                                f"Member extraction escapes target: {clean_name}"
                            )

                        with (
                            zf.open(member) as source_stream,
                            open(dest_file, "wb") as target_file,
                        ):
                            shutil.copyfileobj(source_stream, target_file)

        except zipfile.BadZipFile as exc:
            raise SourceValidationError(f"Corrupt zip archive: {exc}") from exc

        resolved_rev = revision_identifier or source_hash[:12]

        return AcquisitionResult(
            root_path=extracted_dir,
            revision_identifier=resolved_rev,
            source_hash=source_hash,
            total_source_bytes=archive_size,
            cleanup_fn=lambda: shutil.rmtree(temp_root, ignore_errors=True),
        )
