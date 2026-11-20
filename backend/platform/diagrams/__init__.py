"""Version-bound diagram contracts; importing this package starts no work."""

from backend.platform.diagrams.contracts import (
    DiagramArtifactDescriptor,
    DiagramMemberReadPort,
    DiagramReadPort,
    DiagramSpec,
    LayoutSpec,
    PreparedDiagram,
)

__all__ = [
    "DiagramArtifactDescriptor",
    "DiagramMemberReadPort",
    "DiagramReadPort",
    "DiagramSpec",
    "LayoutSpec",
    "PreparedDiagram",
]
