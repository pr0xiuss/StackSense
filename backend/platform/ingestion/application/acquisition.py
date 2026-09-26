"""Acquisition contracts for repository ingestion."""

import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AcquisitionResult:
    """Result of an acquisition operation."""

    root_path: Path
    revision_identifier: str
    source_hash: str
    total_source_bytes: int
    cleanup_fn: Callable[[], None] | None = None

    def cleanup(self) -> None:
        """Clean up acquired temporary files if a cleanup function was provided."""
        if self.cleanup_fn is not None:
            self.cleanup_fn()
        elif self.root_path.exists() and self.root_path.is_dir():
            shutil.rmtree(self.root_path, ignore_errors=True)


class AcquisitionHandler(ABC):
    """Abstract contract for repository source acquisition."""

    @abstractmethod
    def can_handle(self, source_type: str) -> bool:
        """Return True if this handler can process the given source type."""
        raise NotImplementedError

    @abstractmethod
    def acquire(
        self,
        source_reference: str,
        revision_identifier: str | None,
        temp_root: Path,
    ) -> AcquisitionResult:
        """Acquire source repository content into a local directory for validation.

        Args:
            source_reference: Location of source (local path, URL, archive path).
            revision_identifier: Optional user-specified revision identifier.
            temp_root: Safe root directory for extraction or staging.

        Returns:
            AcquisitionResult containing the extracted path and metadata.
        """
        raise NotImplementedError
