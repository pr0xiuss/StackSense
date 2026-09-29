"""Safe extraction utility for repository archives (.zip, .tar, .tar.gz, .tgz)."""

import hashlib
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from backend.platform.errors import (
    MaxFileCountExceededError,
    SourceValidationError,
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


@dataclass(frozen=True, slots=True)
class ExtractedArchive:
    """Result of safe archive extraction."""

    root_path: Path
    source_hash: str
    archive_size: int


class ArchiveExtractor:
    """Safe extraction utility for archives with security defenses."""

    @classmethod
    def extract(
        cls,
        archive_path: Path,
        destination_dir: Path,
        *,
        unwrap_single_root: bool = False,
    ) -> ExtractedArchive:
        """Extract archive with resource and traversal defenses.

        Args:
            archive_path: Path to the archive file on disk.
            destination_dir: Directory where archive contents will be extracted.
            unwrap_single_root: If True and the archive has one top directory,
                root_path points to that directory.

        Returns:
            ExtractedArchive containing root_path, source_hash, and archive_size.
        """
        if not archive_path.is_file():
            raise SourceValidationError(
                f"Archive source does not exist: {archive_path}"
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

        destination_dir.mkdir(parents=True, exist_ok=True)
        dest_resolved = destination_dir.resolve()

        if zipfile.is_zipfile(archive_path):
            cls._extract_zip(archive_path, destination_dir, dest_resolved)
        elif tarfile.is_tarfile(archive_path):
            cls._extract_tar(archive_path, archive_size, destination_dir, dest_resolved)
        else:
            name_lower = archive_path.name.lower()
            if name_lower.endswith(".zip"):
                raise SourceValidationError("Source file is not a valid zip archive.")
            if (
                name_lower.endswith(".tar")
                or name_lower.endswith(".tar.gz")
                or name_lower.endswith(".tgz")
            ):
                raise SourceValidationError("Source file is not a valid tar archive.")
            raise SourceValidationError(
                f"Source file '{archive_path.name}' is not a valid archive."
            )

        root_path = destination_dir
        if unwrap_single_root:
            children = list(destination_dir.iterdir())
            if len(children) == 1 and children[0].is_dir():
                root_path = children[0]

        return ExtractedArchive(
            root_path=root_path,
            source_hash=source_hash,
            archive_size=archive_size,
        )

    @classmethod
    def _extract_zip(
        cls,
        archive_path: Path,
        destination_dir: Path,
        dest_resolved: Path,
    ) -> None:
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                members = zf.infolist()

                if len(members) > MAX_REPOSITORY_FILE_COUNT:
                    raise MaxFileCountExceededError(
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

                    if not member.is_dir():
                        dest_file = destination_dir / clean_name
                        dest_file.parent.mkdir(parents=True, exist_ok=True)

                        resolved = dest_file.resolve()
                        if not str(resolved).startswith(str(dest_resolved)):
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

    @classmethod
    def _extract_tar(
        cls,
        archive_path: Path,
        archive_size: int,
        destination_dir: Path,
        dest_resolved: Path,
    ) -> None:
        try:
            with tarfile.open(archive_path, "r:*") as tf:
                members = tf.getmembers()

                if len(members) > MAX_REPOSITORY_FILE_COUNT:
                    raise MaxFileCountExceededError(
                        f"Archive contains {len(members)} files, exceeding limit "
                        f"of {MAX_REPOSITORY_FILE_COUNT}."
                    )

                total_uncompressed = 0
                for member in members:
                    clean_name = member.name.replace("\\", "/").strip("/")
                    if not clean_name:
                        continue

                    parts = clean_name.split("/")
                    if ".." in parts or clean_name.startswith("/") or ":" in clean_name:
                        raise SourceValidationError(
                            f"Path traversal detected in archive member: "
                            f"{member.name}"
                        )

                    if len(clean_name) > MAX_PATH_LENGTH:
                        raise SourceValidationError(
                            f"Archive member path exceeds {MAX_PATH_LENGTH} "
                            f"characters: {clean_name}"
                        )

                    depth = len(parts) - (1 if member.isdir() else 0)
                    if depth > MAX_DIRECTORY_DEPTH:
                        raise SourceValidationError(
                            f"Directory depth ({depth}) exceeds limit of "
                            f"{MAX_DIRECTORY_DEPTH}: {clean_name}"
                        )

                    # Reject special devices and FIFOs
                    if member.ischr() or member.isblk() or member.isfifo():
                        raise SourceValidationError(
                            f"Prohibited special device or FIFO entry: {clean_name}"
                        )

                    # Reject symbolic and hard links
                    if member.issym() or member.islnk():
                        raise SourceValidationError(
                            f"Archive member '{clean_name}' is a link. "
                            "Symbolic and hard links are not permitted."
                        )

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

                    total_uncompressed += member.size
                    if total_uncompressed > MAX_EXTRACTED_SIZE_BYTES:
                        raise SourceValidationError(
                            f"Uncompressed archive exceeds limit of "
                            f"{MAX_EXTRACTED_SIZE_BYTES} bytes."
                        )

                    if archive_size > 0 and member.size > 1024 * 1024:
                        ratio = total_uncompressed / archive_size
                        if ratio > MAX_COMPRESSION_RATIO:
                            raise SourceValidationError(
                                f"High compression ratio ({ratio:.1f}:1) detected on "
                                f"{clean_name}, exceeding safety limit."
                            )

                    if member.isfile():
                        dest_file = destination_dir / clean_name
                        dest_file.parent.mkdir(parents=True, exist_ok=True)

                        resolved = dest_file.resolve()
                        if not str(resolved).startswith(str(dest_resolved)):
                            raise SourceValidationError(
                                f"Member extraction escapes target: {clean_name}"
                            )

                        source_stream = tf.extractfile(member)
                        if source_stream is not None:
                            with source_stream, open(dest_file, "wb") as target_file:
                                shutil.copyfileobj(source_stream, target_file)
                    elif member.isdir():
                        dest_dir = destination_dir / clean_name
                        dest_dir.mkdir(parents=True, exist_ok=True)

        except tarfile.TarError as exc:
            raise SourceValidationError(f"Corrupt tar archive: {exc}") from exc
