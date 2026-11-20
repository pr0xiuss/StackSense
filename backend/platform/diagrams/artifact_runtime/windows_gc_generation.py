"""Fixed operator-invoked Windows orphan GC; normal workers get no entry grant."""

import sys
from uuid import UUID

from backend.platform.diagrams.artifact_runtime.windows_seal_generation import (
    configured_metadata,
)
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.windows_artifacts import WindowsPrincipalSealer


def main() -> None:
    if len(sys.argv) != 2 or str(UUID(sys.argv[1])) != sys.argv[1]:
        raise ValueError("diagram_input_invalid")
    metadata, config = configured_metadata(cleanup=True)
    try:
        WindowsPrincipalSealer(
            metadata,
            DiagramLimits(),
            sealer_sid=config.sealer_sid,
            worker_sid=config.worker_sid,
            reader_sid=config.reader_sid,
        ).delete_reserved(UUID(sys.argv[1]))
    finally:
        metadata.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("diagram_windows_gc_rejected\n")
        raise SystemExit(78) from None
