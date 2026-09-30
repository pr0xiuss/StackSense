"""Safe extraction utility for repository archives (.zip, .tar, .tar.gz, .tgz)."""

import hashlib
import re
import shutil
import stat
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

_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

_WINDOWS_DRIVE_PATTERN = re.compile(r"^[a-zA-Z]:")


def _sanitize_and_validate_member_path(
    raw_path: str,
    *,
    is_dir: bool,
    destination_dir: Path,
    dest_resolved: Path,
) -> Path | None:
    """Validate archive member path against traversal, escaping, and device injection.

    Returns:
        The target Path under destination_dir if valid, or None if the entry
        represents the archive root itself and should be skipped.

    Raises:
        SourceValidationError: if any path traversal, drive prefix, UNC prefix,
        reserved device, or escape condition is detected.
    """
    if "\x00" in raw_path:
        raise SourceValidationError(
            f"Path traversal detected in archive member (null byte): {raw_path!r}"
        )

    # Check for absolute paths before any stripping
    if raw_path.startswith("/") or raw_path.startswith("\\"):
        raise SourceValidationError(
            f"Path traversal detected in archive member: {raw_path}"
        )

    # Check for UNC network share paths
    if raw_path.startswith("//") or raw_path.startswith("\\\\"):
        raise SourceValidationError(
            f"Path traversal detected in archive member: {raw_path}"
        )

    # Check for Windows drive-letter paths (e.g. C:, C:\, C:/, d:foo)
    if _WINDOWS_DRIVE_PATTERN.match(raw_path):
        raise SourceValidationError(
            f"Path traversal detected in archive member: {raw_path}"
        )

    # Normalize backslashes to forward slashes
    normalized = raw_path.replace("\\", "/")

    # Strip leading/trailing slashes for segment parsing
    clean_name = normalized.strip("/")
    if not clean_name:
        return None  # Root directory entry (e.g. "" or "./")

    # If the path starts with './', strip that prefix for consistent traversal analysis
    if clean_name.startswith("./"):
        clean_name = clean_name[2:].lstrip("/")
        if not clean_name:
            return None

    if len(clean_name) > MAX_PATH_LENGTH:
        raise SourceValidationError(
            f"Archive member path exceeds {MAX_PATH_LENGTH} "
            f"characters: {clean_name}"
        )

    parts = clean_name.split("/")
    if ".." in parts:
        raise SourceValidationError(
            f"Path traversal detected in archive member: {raw_path}"
        )

    if "" in parts:
        raise SourceValidationError(
            f"Path traversal detected in archive member: {raw_path}"
        )

    if any(":" in part for part in parts):
        raise SourceValidationError(
            f"Path traversal detected in archive member: {raw_path}"
        )

    for part in parts:
        stem = part.split(".")[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise SourceValidationError(
                f"Prohibited Windows reserved device name in archive member: {raw_path}"
            )

    depth = len(parts) - (1 if is_dir else 0)
    if depth > MAX_DIRECTORY_DEPTH:
        raise SourceValidationError(
            f"Directory depth ({depth}) exceeds limit of "
            f"{MAX_DIRECTORY_DEPTH}: {clean_name}"
        )

    dest_path = destination_dir / clean_name
    try:
        resolved = dest_path.resolve()
    except (ValueError, RuntimeError) as exc:
        raise SourceValidationError(
            f"Invalid archive member path '{clean_name}': {exc}"
        ) from exc

    if not resolved.is_relative_to(dest_resolved):
        raise SourceValidationError(f"Member extraction escapes target: {clean_name}")

    return dest_path


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
                    # Reject symlinks encoded in external attributes
                    mode = member.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise SourceValidationError(
                            f"Archive member '{member.filename}' is a link. "
                            "Symbolic and hard links are not permitted."
                        )

                    dest_file = _sanitize_and_validate_member_path(
                        member.filename,
                        is_dir=member.is_dir(),
                        destination_dir=destination_dir,
                        dest_resolved=dest_resolved,
                    )
                    if dest_file is None:
                        continue

                    parts = dest_file.relative_to(destination_dir).as_posix().split("/")
                    file_ext = dest_file.suffix.lower()
                    if file_ext in ARCHIVE_EXTENSIONS:
                        archive_nesting = sum(
                            1
                            for part in parts
                            if Path(part).suffix.lower() in ARCHIVE_EXTENSIONS
                        )
                        if archive_nesting > MAX_ARCHIVE_NESTING_DEPTH:
                            raise SourceValidationError(
                                f"Archive nesting depth exceeds limit of "
                                f"{MAX_ARCHIVE_NESTING_DEPTH}: {dest_file.name}"
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
                                f"{dest_file.name}, exceeding safety limit."
                            )

                    if not member.is_dir():
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
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
                    # Reject symbolic and hard links
                    if member.issym() or member.islnk():
                        raise SourceValidationError(
                            f"Archive member '{member.name}' is a link. "
                            "Symbolic and hard links are not permitted."
                        )

                    # Reject special devices, FIFOs, and sockets
                    # (strictly whitelist regular files and directories)
                    if (
                        member.ischr()
                        or member.isblk()
                        or member.isfifo()
                        or member.isdev()
                        or not (member.isfile() or member.isdir())
                    ):
                        raise SourceValidationError(
                            "Prohibited special device, FIFO, or socket entry: "
                            f"{member.name}"
                        )

                    dest_entry = _sanitize_and_validate_member_path(
                        member.name,
                        is_dir=member.isdir(),
                        destination_dir=destination_dir,
                        dest_resolved=dest_resolved,
                    )
                    if dest_entry is None:
                        continue

                    rel_entry = dest_entry.relative_to(destination_dir)
                    parts = rel_entry.as_posix().split("/")
                    file_ext = dest_entry.suffix.lower()
                    if file_ext in ARCHIVE_EXTENSIONS:
                        archive_nesting = sum(
                            1
                            for part in parts
                            if Path(part).suffix.lower() in ARCHIVE_EXTENSIONS
                        )
                        if archive_nesting > MAX_ARCHIVE_NESTING_DEPTH:
                            raise SourceValidationError(
                                f"Archive nesting depth exceeds limit of "
                                f"{MAX_ARCHIVE_NESTING_DEPTH}: {dest_entry.name}"
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
                                f"{dest_entry.name}, exceeding safety limit."
                            )

                    if member.isfile():
                        dest_entry.parent.mkdir(parents=True, exist_ok=True)
                        source_stream = tf.extractfile(member)
                        if source_stream is not None:
                            with source_stream, open(dest_entry, "wb") as target_file:
                                shutil.copyfileobj(source_stream, target_file)
                    elif member.isdir():
                        dest_entry.mkdir(parents=True, exist_ok=True)

        except tarfile.TarError as exc:
            raise SourceValidationError(f"Corrupt tar archive: {exc}") from exc
