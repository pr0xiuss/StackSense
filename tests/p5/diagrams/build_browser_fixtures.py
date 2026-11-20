"""Regenerate test-only real-ELK prepared C2 fixtures; no production acceptance.

Run from repository root with the essential-proof runtime environment. Writes
base64(gzip(canonical PreparedDiagram)) to stdout, never an application store.
"""

import base64
import gzip
import hashlib
import os
import sys
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

from backend.platform.delivery.contracts import DiagramTemplate, OutputDigests
from backend.platform.diagrams.builders import BUILDERS
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import (
    DiagramArtifactDescriptor,
    MemberDescriptor,
    PreparedDiagram,
)
from backend.platform.diagrams.export import member_payloads, prepare_layout
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.layout import LockedFile, create_layout_profile
from tests.p5.diagrams.test_builders import monorepo
from tests.p5.diagrams.test_c2_consumers import prepared
from tests.p5.diagrams.test_exports import Control
from tests.p5.integration.test_diagram_pipeline import RealRootlessLayout


def main() -> None:
    argument = sys.argv[1]
    template = (
        DiagramTemplate.DEPENDENCY
        if argument.startswith("stress")
        else DiagramTemplate(argument)
    )
    fixture = prepared(template)
    limits = DiagramLimits()
    if argument.startswith("stress"):
        from tests.p5.diagrams.test_builders import data, entity, relation

        count = int(argument[6:])
        if count == 150:
            limits = DiagramLimits(
                max_nodes=150, max_edges=600, max_groups=64, max_depth=3
            )
        entities = tuple(entity(i + 1) for i in range(count))
        relationships = tuple(
            relation(i + 1, entities[i], entities[i + 1])
            for i in range(count - 1)
            if i % 5 != 4
        )
        built = BUILDERS[template].build(data(entities, relationships), limits)
    else:
        built = BUILDERS[template].build(monorepo(), limits)
    paths = {
        "node": Path(os.environ["M4_B1_NODE"]),
        "bwrap": Path(os.environ["M4_B1_BWRAP"]),
        "elk_helper": Path("backend/platform/diagrams/layout_runtime/elk_layout.mjs"),
        "elk": Path(
            "backend/platform/diagrams/layout_runtime/node_modules/elkjs/lib/elk.bundled.js"
        ),
    }
    lock = SimpleNamespace(
        files=tuple(
            LockedFile(path=k, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for k, p in sorted(paths.items())
        )
    )
    fonts = DiagramFonts()
    try:
        name = (
            "dependency_layered_v1"
            if template == DiagramTemplate.DEPENDENCY
            else (
                "static_flow_v1"
                if template == DiagramTemplate.DATA_FLOW
                else "architecture_compound_v1"
            )
        )
        profile = create_layout_profile(name, lock, fonts.manifest_digest())
        layout = prepare_layout(
            built,
            fonts,
            RealRootlessLayout(),
            profile,
            limits,
            monotonic() + 60,
            Control(),
        )
    finally:
        fonts.close()
    payloads = member_payloads(built, layout, limits, lambda: None)
    members = tuple(
        MemberDescriptor(
            member=k,
            file_name="scene.svg" if k == "svg" else k + ".json",
            media_type="image/svg+xml" if k == "svg" else "application/json",
            schema_version="1.0.0",
            size_bytes=len(v),
            sha256=hashlib.sha256(v).hexdigest(),
        )
        for k, v in sorted(payloads.items())
    )
    manifest = fixture.descriptor.manifest.model_copy(
        update=dict(
            diagram_id=built.spec.diagram_id,
            semantic_digest=built.spec.semantic_digest,
            layout_digest=layout.layout_digest,
            membership_digest=built.spec.membership_digest,
            members=members,
        )
    )
    ref = fixture.descriptor.reference.model_copy(
        update=dict(
            size_bytes=len(manifest.to_bytes()),
            digests=OutputDigests(
                content=hashlib.sha256(manifest.to_bytes()).hexdigest(),
                spec=built.spec.semantic_digest,
                layout=layout.layout_digest,
            ),
        )
    )
    result = PreparedDiagram(
        spec=built.spec,
        layout=layout,
        descriptor=DiagramArtifactDescriptor(manifest=manifest, reference=ref),
    )
    encoded = base64.b64encode(gzip.compress(result.to_bytes(), mtime=0)).decode()
    print(
        encoded[int(sys.argv[2]) : int(sys.argv[3])] if len(sys.argv) > 2 else encoded
    )


if __name__ == "__main__":
    main()
