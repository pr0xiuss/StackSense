"""Approved diagram limits. These do not enable dispatch or prove capability."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, model_validator

from backend.platform.diagrams.contracts import ClosedRecord
from backend.platform.diagrams.model import canonical_bytes

MIB = 1024 * 1024
GIB = 1024 * MIB


class DiagramLimits(ClosedRecord):
    max_source_rows: Annotated[StrictInt, Field(ge=1, le=500000)] = 350000
    max_source_calls: Annotated[StrictInt, Field(ge=1, le=5000)] = 2500
    source_page_size: Annotated[StrictInt, Field(ge=1, le=500)] = 200
    max_input_bytes: Annotated[StrictInt, Field(ge=1, le=256 * MIB)] = 128 * MIB
    max_retained_records: Annotated[StrictInt, Field(ge=1, le=200000)] = 100000
    max_retained_bytes: Annotated[StrictInt, Field(ge=1, le=128 * MIB)] = 64 * MIB
    max_nodes: Annotated[StrictInt, Field(ge=1, le=1000)] = 500
    max_edges: Annotated[StrictInt, Field(ge=1, le=4000)] = 2000
    max_groups: Annotated[StrictInt, Field(ge=1, le=256)] = 128
    max_depth: Annotated[StrictInt, Field(ge=1, le=8)] = 4
    max_relationship_members: Annotated[StrictInt, Field(ge=1, le=50000)] = 25000
    max_group_members: Annotated[StrictInt, Field(ge=1, le=100000)] = 50000
    max_fanout: Annotated[StrictInt, Field(ge=1, le=250)] = 100
    max_logical_id_bytes: Annotated[StrictInt, Field(ge=1, le=8192)] = 8192
    max_name_bytes: Annotated[StrictInt, Field(ge=1, le=4096)] = 4096
    max_namespace_component_bytes: Annotated[StrictInt, Field(ge=1, le=1024)] = 1024
    max_source_fact_key_bytes: Annotated[StrictInt, Field(ge=1, le=8192)] = 8192
    max_helper_input_bytes: Annotated[StrictInt, Field(ge=1, le=16 * MIB)] = 8 * MIB
    max_helper_output_bytes: Annotated[StrictInt, Field(ge=1, le=32 * MIB)] = 16 * MIB
    max_helper_stderr_bytes: Annotated[StrictInt, Field(ge=1, le=262144)] = 65536
    max_scratch_bytes: Annotated[StrictInt, Field(ge=1, le=64 * MIB)] = 32 * MIB
    max_helper_memory_bytes: Annotated[StrictInt, Field(ge=1, le=GIB)] = 768 * MIB
    max_helper_processes: Annotated[StrictInt, Field(ge=1, le=128)] = 64
    max_helper_fds: Annotated[StrictInt, Field(ge=1, le=128)] = 64
    max_helper_cpu_seconds: Annotated[StrictInt, Field(ge=1, le=60)] = 20
    helper_wall_seconds: Annotated[StrictInt, Field(ge=1, le=90)] = 30
    build_seconds: Annotated[StrictInt, Field(ge=1, le=300)] = 180
    view_seconds: Annotated[StrictInt, Field(ge=1, le=90)] = 30
    read_seconds: Annotated[StrictInt, Field(ge=1, le=60)] = 15
    statement_seconds: Annotated[StrictInt, Field(ge=1, le=15)] = 5
    lock_seconds: Annotated[StrictInt, Field(ge=1, le=3)] = 1
    max_route_sections: Annotated[StrictInt, Field(ge=1, le=50000)] = 20000
    max_glyphs: Annotated[StrictInt, Field(ge=1, le=1024)] = 512
    max_glyph_placements: Annotated[StrictInt, Field(ge=1, le=200000)] = 100000
    max_path_commands: Annotated[StrictInt, Field(ge=1, le=600000)] = 300000
    max_spec_bytes: Annotated[StrictInt, Field(ge=1, le=16 * MIB)] = 8 * MIB
    max_layout_bytes: Annotated[StrictInt, Field(ge=1, le=32 * MIB)] = 16 * MIB
    max_members_bytes: Annotated[StrictInt, Field(ge=1, le=48 * MIB)] = 32 * MIB
    max_svg_bytes: Annotated[StrictInt, Field(ge=1, le=48 * MIB)] = 32 * MIB
    max_manifest_bytes: Annotated[StrictInt, Field(ge=1, le=262144)] = 131072
    max_total_member_bytes: Annotated[StrictInt, Field(ge=1, le=128 * MIB)] = 96 * MIB
    max_focus_roots: Annotated[StrictInt, Field(ge=1, le=32)] = 1
    max_selected_ids: Annotated[StrictInt, Field(ge=1, le=200)] = 100
    max_expanded_groups: Annotated[StrictInt, Field(ge=1, le=64)] = 32
    max_api_body_bytes: Annotated[StrictInt, Field(ge=1, le=131072)] = 65536
    page_size: Annotated[StrictInt, Field(ge=1, le=200)] = 50
    max_cursor_bytes: Annotated[StrictInt, Field(ge=1, le=4096)] = 4096
    cursor_ttl_seconds: Annotated[StrictInt, Field(ge=1, le=600)] = 600
    stream_seconds: Annotated[StrictInt, Field(ge=1, le=120)] = 60
    pin_seconds: Annotated[StrictInt, Field(ge=1, le=300)] = 120
    max_pins_per_generation: Annotated[StrictInt, Field(ge=1, le=64)] = 32
    max_local_reads: Annotated[StrictInt, Field(ge=1, le=16)] = 8
    max_local_builds: Annotated[StrictInt, Field(ge=1, le=2)] = 1
    max_project_builds: Annotated[StrictInt, Field(ge=1, le=1)] = 1
    min_free_bytes: Annotated[StrictInt, Field(ge=512 * MIB, le=2**53 - 1)] = 2 * GIB
    max_orphan_bytes: Annotated[StrictInt, Field(ge=1, le=8 * GIB)] = 2 * GIB
    orphan_grace_seconds: Annotated[StrictInt, Field(ge=3600, le=2**53 - 1)] = 86400
    gc_batch_size: Annotated[StrictInt, Field(ge=1, le=100)] = 20

    @model_validator(mode="after")
    def stream_pin_lifetime(self) -> Self:
        if self.pin_seconds <= self.stream_seconds:
            raise ValueError("pin must outlive bounded stream")
        return self

    def semantic_selection_policy(self) -> dict[str, int]:
        """Exclude runtime/font/storage/time from semantic identity."""
        keys = (
            "max_source_rows",
            "max_source_calls",
            "source_page_size",
            "max_input_bytes",
            "max_retained_records",
            "max_retained_bytes",
            "max_nodes",
            "max_edges",
            "max_groups",
            "max_depth",
            "max_relationship_members",
            "max_group_members",
            "max_fanout",
            "max_logical_id_bytes",
            "max_name_bytes",
            "max_namespace_component_bytes",
            "max_source_fact_key_bytes",
        )
        return {key: getattr(self, key) for key in keys}


class DiagramRuntimeConfig(ClosedRecord):
    enabled: bool = False
    selection_profile: Literal["standard500", "compact150"]
    operational_limits: DiagramLimits
    runtime_version: Literal["24.22.3"]
    layout_version: Literal["0.12.1"]
    font_version: Literal["dejavu_paths_2_37_v1"]
    export_version: Literal["svg_paths_v1"]
    schema_version: Literal["1.0.0"]
    cursor_key_id: Annotated[str, Field(min_length=1, max_length=64)]
    cursor_secret: Annotated[str, Field(min_length=32)] = Field(
        repr=False, exclude=True
    )

    @model_validator(mode="after")
    def selected_profile(self) -> Self:
        limits = self.operational_limits
        ceilings = (
            (150, 600, 64, 3)
            if self.selection_profile == "compact150"
            else (1000, 4000, 256, 8)
        )
        if any(
            v > ceiling
            for v, ceiling in zip(
                (
                    limits.max_nodes,
                    limits.max_edges,
                    limits.max_groups,
                    limits.max_depth,
                ),
                ceilings,
                strict=True,
            )
        ):
            raise ValueError("selection exceeds pinned profile")
        return self

    def fingerprint(self, verified_asset_hashes: MappingHashes) -> str:
        """Hash only explicit nonsecret config and actual verified runtime hashes."""
        return hashlib.sha256(
            canonical_bytes((self.model_dump(mode="json"), verified_asset_hashes))
        ).hexdigest()


# Asset acquisition/independent verification owns these values. This alias is
# deliberately not a built-in production lock with guessed hashes.
MappingHashes = dict[str, str]
