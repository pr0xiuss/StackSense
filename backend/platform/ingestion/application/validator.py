"""Source repository validation and discovery pipeline."""

from dataclasses import dataclass
from pathlib import Path

from backend.platform.errors import SourceValidationError
from backend.platform.ingestion.domain.constants import (
    MAX_DIRECTORY_DEPTH,
    MAX_EXTRACTED_SIZE_BYTES,
    MAX_PATH_LENGTH,
    MAX_REPOSITORY_FILE_COUNT,
)


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """Represents a discovered file within the repository source."""

    relative_path: str
    absolute_path: Path
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ValidatedSource:
    """Represents the validated inventory of repository files."""

    files: list[DiscoveredFile]
    total_files: int
    total_bytes: int


class SourceValidator:
    """Validates repository file structure, path lengths, depth, and resource bounds."""

    def validate(self, root_path: Path) -> ValidatedSource:
        resolved_root = root_path.resolve()
        if not resolved_root.is_dir():
            raise SourceValidationError(
                f"Validation target is not a directory: {resolved_root}"
            )

        discovered: list[DiscoveredFile] = []
        total_bytes = 0

        # Deterministically scan filesystem
        for item in sorted(resolved_root.rglob("*")):
            if not item.is_file():
                continue

            # Prevent symlink escapes
            try:
                resolved_item = item.resolve()
                resolved_item.relative_to(resolved_root)
            except (ValueError, RuntimeError) as exc:
                raise SourceValidationError(
                    f"Symlink or path escapes repository root: {item}"
                ) from exc

            rel_path = item.relative_to(resolved_root).as_posix()

            if len(rel_path) > MAX_PATH_LENGTH:
                raise SourceValidationError(
                    f"Path length ({len(rel_path)}) exceeds limit of "
                    f"{MAX_PATH_LENGTH}: {rel_path}"
                )

            parts = rel_path.split("/")
            depth = len(parts) - 1
            if depth > MAX_DIRECTORY_DEPTH:
                raise SourceValidationError(
                    f"Directory depth ({depth}) exceeds limit of "
                    f"{MAX_DIRECTORY_DEPTH}: {rel_path}"
                )

            file_size = item.stat().st_size
            total_bytes += file_size

            discovered.append(
                DiscoveredFile(
                    relative_path=rel_path,
                    absolute_path=item,
                    size_bytes=file_size,
                )
            )

            if len(discovered) > MAX_REPOSITORY_FILE_COUNT:
                raise SourceValidationError(
                    f"File count exceeds maximum repository file limit of "
                    f"{MAX_REPOSITORY_FILE_COUNT}."
                )

            if total_bytes > MAX_EXTRACTED_SIZE_BYTES:
                raise SourceValidationError(
                    f"Total extracted size ({total_bytes} bytes) exceeds maximum "
                    f"repository size of {MAX_EXTRACTED_SIZE_BYTES} bytes."
                )

        return ValidatedSource(
            files=discovered,
            total_files=len(discovered),
            total_bytes=total_bytes,
        )
