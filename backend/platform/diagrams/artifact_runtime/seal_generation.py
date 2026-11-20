"""Fixed separate-principal stdin entry; no delete verb or caller paths."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.platform.delivery.contracts import AttemptIdentity
from backend.platform.delivery.ownership import SqlAlchemyAttemptRetirementReader
from backend.platform.diagrams.artifact_contracts import SealRequest
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.contracts import ClosedRecord, DiagramArtifactManifest, H
from backend.platform.diagrams.persistence import DiagramGenerationModel as Generation
from backend.platform.diagrams.persistence import DiagramReadPinModel as Pin
from backend.platform.diagrams.persistence import DiagramResourceModel as Resource

CONFIG_ROOT = Path("/opt/stacksense/diagram-artifacts/deployment")


class SealProfile(ClosedRecord):
    fingerprint: H
    limits: DiagramLimits


class MetadataConfig(ClosedRecord):
    version: Literal["1.0.0"]
    database_url: str
    schema_name: str = Field(alias="schema")
    profiles: tuple[SealProfile, ...]


class DatabaseSealerMetadata:
    def __init__(self, *, cleanup: bool = False) -> None:
        path = CONFIG_ROOT / ("db-cleanup.json" if cleanup else "db-readonly.json")
        info = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o400
        ):
            raise ValueError("diagram_store_unavailable")
        config = MetadataConfig.from_bytes(path.read_bytes(), max_bytes=8192)
        self.initialize(config, cleanup=cleanup)

    def initialize(self, config: MetadataConfig, *, cleanup: bool = False) -> None:
        if config.schema_name != "public" and not (
            config.schema_name.startswith("p5_diagram_")
            and len(config.schema_name) == 43
            and all(c in "0123456789abcdef" for c in config.schema_name[11:])
        ):
            raise ValueError("diagram_store_unavailable")
        self.engine = create_engine(
            config.database_url,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": 1,
                "options": (
                    "-c default_transaction_read_only=on "
                    "-c statement_timeout=1000 -c lock_timeout=1000"
                ),
            },
        ).execution_options(schema_translate_map={None: config.schema_name})
        if self.engine.dialect.name != "postgresql":
            self.engine.dispose()
            raise ValueError("diagram_store_unavailable")
        self.cleanup = cleanup
        self.profiles = {p.fingerprint: p.limits for p in config.profiles}
        if len(self.profiles) != len(config.profiles):
            self.engine.dispose()
            raise ValueError("diagram_store_unavailable")

    def limits_for(self, request: SealRequest) -> DiagramLimits:
        try:
            return self.profiles[
                request.attempt.work.binding.profile.configuration_fingerprint
            ]
        except KeyError:
            raise ValueError("diagram_store_unavailable") from None

    def close(self) -> None:
        self.engine.dispose()

    def require_staging(self, request: SealRequest) -> None:
        with Session(self.engine) as session:
            row = session.get(Generation, request.generation_id)
            if (
                row is None
                or row.state != "STAGING"
                or row.accepted_reference is not None
            ):
                raise ValueError("diagram_integrity_error")
            attempt = AttemptIdentity.model_validate_json(
                json.dumps(row.attempt_snapshot)
            )
            manifest = DiagramArtifactManifest.model_validate_json(
                json.dumps(row.manifest)
            )
            manifest_bytes = manifest.to_bytes()
            resource = session.get(Resource, row.resource_id)
            if (
                attempt != request.attempt
                or resource is None
                or row.artifact_id != request.artifact_id
                or row.candidate_id != attempt.candidate_id
                or row.attempt_id != attempt.attempt_id
                or row.fence != attempt.fence
                or row.attempt_ordinal != attempt.ordinal
                or row.dispatch_epoch != attempt.dispatch_epoch
                or row.work_id != attempt.work.work_id
                or row.manifest_sha256 != request.manifest_sha256
                or row.manifest_size != request.manifest_size
                or len(manifest_bytes) != request.manifest_size
                or hashlib.sha256(manifest_bytes).hexdigest() != request.manifest_sha256
                or manifest.members != request.members
                or manifest.generation_id != request.generation_id
                or manifest.artifact_id != request.artifact_id
                or manifest.scope != attempt.work.scope
                or manifest.binding != attempt.work.binding
                or manifest.input_fingerprint != attempt.work.input_fingerprint
                or resource.scope != attempt.work.scope.model_dump(mode="json")
                or resource.binding != attempt.work.binding.model_dump(mode="json")
                or resource.accepted_generation_id == request.generation_id
            ):
                raise ValueError("diagram_integrity_error")

    def require_deleting(self, generation_id: UUID) -> None:
        if not self.cleanup:
            raise ValueError("diagram_forbidden")
        with Session(self.engine) as session:
            row = session.get(Generation, generation_id)
            if (
                row is None
                or row.state != "DELETING"
                or row.deletion_nonce is None
                or row.deletion_actor is None
                or row.retirement_snapshot is None
                or row.accepted_reference is not None
                or row.acceptance_context is not None
                or row.accepted_at is not None
            ):
                raise ValueError("diagram_integrity_error")
            if (
                session.scalar(
                    select(Pin.id).where(Pin.generation_id == generation_id).limit(1)
                )
                is not None
            ):
                raise ValueError("diagram_integrity_error")
            if (
                session.scalar(
                    select(Resource.id)
                    .where(Resource.accepted_generation_id == generation_id)
                    .limit(1)
                )
                is not None
            ):
                raise ValueError("diagram_integrity_error")
            attempt = AttemptIdentity.model_validate_json(
                json.dumps(row.attempt_snapshot)
            )
            recorded = row.retirement_snapshot
        # Public M1 retirement read only. No private upstream model/table access.
        observation = SqlAlchemyAttemptRetirementReader(
            self.engine, timeout_seconds=1, lock_timeout_ms=1000
        ).read_retirement(attempt)
        if (
            observation is None
            or observation.publication is not None
            or observation.attempt != attempt
            or observation.model_dump(mode="json") != recorded
        ):
            raise ValueError("diagram_integrity_error")


def main() -> None:
    from backend.platform.diagrams.artifacts import PrincipalSealer

    if len(sys.argv) != 1:
        raise ValueError("diagram_input_invalid")
    data = sys.stdin.buffer.read(262145)
    request = SealRequest.from_bytes(data, max_bytes=262144)
    metadata = DatabaseSealerMetadata()
    try:
        proof = PrincipalSealer(metadata, metadata.limits_for(request)).seal(request)
        sys.stdout.buffer.write(proof.to_bytes())
    finally:
        metadata.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("diagram_sealing_rejected\n")
        raise SystemExit(78) from None
