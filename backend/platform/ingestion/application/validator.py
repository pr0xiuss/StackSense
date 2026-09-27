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

    def __init__(
        self,
        *,
        max_path_length: int = MAX_PATH_LENGTH,
        max_directory_depth: int = MAX_DIRECTORY_DEPTH,
        max_file_count: int = MAX_REPOSITORY_FILE_COUNT,
        max_extracted_size_bytes: int = MAX_EXTRACTED_SIZE_BYTES,
    ) -> None:
        self._max_path_length = max_path_length
        self._max_directory_depth = max_directory_depth
        self._max_file_count = max_file_count
        self._max_extracted_size_bytes = max_extracted_size_bytes

    def validate(self, root_path: Path) -> ValidatedSource:
        try:
            resolved_root = root_path.resolve()
        except OSError as exc:
            raise SourceValidationError(
                f"Failed to resolve repository path {root_path}: {exc}"
            ) from exc

        if not resolved_root.is_dir():
            raise SourceValidationError(
                f"Validation target is not a directory: {resolved_root}"
            )

        discovered: list[DiscoveredFile] = []
        total_bytes = 0

        # Deterministically scan filesystem
        try:
            items = sorted(resolved_root.rglob("*"))
        except OSError as exc:
            raise SourceValidationError(
                f"Failed to scan repository files: {exc}"
            ) from exc

        for item in items:
            try:
                if not item.is_file():
                    continue

                # Prevent symlink escapes
                resolved_item = item.resolve()
                resolved_item.relative_to(resolved_root)
                rel_path = item.relative_to(resolved_root).as_posix()
            except (ValueError, RuntimeError) as exc:
                raise SourceValidationError(
                    f"Symlink or path escapes repository root: {item}"
                ) from exc
            except OSError as exc:
                raise SourceValidationError(
                    f"Filesystem access error validating path {item}: {exc}"
                ) from exc

            if len(rel_path) > self._max_path_length:
                raise SourceValidationError(
                    f"Path length ({len(rel_path)}) exceeds limit of "
                    f"{self._max_path_length}: {rel_path}"
                )

            parts = rel_path.split("/")
            depth = len(parts) - 1
            if depth > self._max_directory_depth:
                raise SourceValidationError(
                    f"Directory depth ({depth}) exceeds limit of "
                    f"{self._max_directory_depth}: {rel_path}"
                )

            try:
                file_size = item.stat().st_size
            except OSError as exc:
                raise SourceValidationError(
                    f"Filesystem access error validating path {item}: {exc}"
                ) from exc

            total_bytes += file_size

            discovered.append(
                DiscoveredFile(
                    relative_path=rel_path,
                    absolute_path=item,
                    size_bytes=file_size,
                )
            )

            if len(discovered) > self._max_file_count:
                raise SourceValidationError(
                    f"File count exceeds maximum repository file limit of "
                    f"{self._max_file_count}."
                )

            if total_bytes > self._max_extracted_size_bytes:
                raise SourceValidationError(
                    f"Total extracted size ({total_bytes} bytes) exceeds maximum "
                    f"repository size of {self._max_extracted_size_bytes} bytes."
                )

        return ValidatedSource(
            files=discovered,
            total_files=len(discovered),
            total_bytes=total_bytes,
        )
