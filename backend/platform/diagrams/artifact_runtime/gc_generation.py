"""Operator-only exact reserved-orphan deletion; no worker entry permission."""

import sys
from uuid import UUID

from backend.platform.diagrams.artifact_runtime.seal_generation import (
    DatabaseSealerMetadata,
)
from backend.platform.diagrams.artifacts import PrincipalSealer
from backend.platform.diagrams.configuration import DiagramLimits


def main() -> None:
    if len(sys.argv) != 2 or str(UUID(sys.argv[1])) != sys.argv[1]:
        raise ValueError("diagram_input_invalid")
    metadata = DatabaseSealerMetadata(cleanup=True)
    try:
        PrincipalSealer(metadata, DiagramLimits()).delete_reserved(UUID(sys.argv[1]))
    finally:
        metadata.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("diagram_gc_rejected\n")
        raise SystemExit(78) from None
