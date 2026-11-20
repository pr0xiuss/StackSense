"""Actual filesystem + PostgreSQL + M1 experiment, NOT OS-principal proof.

The test-only sealer bypasses only deployment identity/filesystem certification.
Real copy/rehash/no-replace/locking, durable staging, guarded M1 publication,
committed exact reads and concurrent accepted-history GC exclusion still run.
No developer sealer or producer is registered in application composition.
"""

from sqlalchemy.orm import Session

from backend.platform.delivery.persistence import DELIVERY_TABLES
from backend.platform.diagrams import artifacts
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.persistence import DiagramGenerationModel as Generation
from tests.p5.diagrams import test_linux_sealing as physical
from tests.p5.diagrams.test_database import diagram_db  # noqa: F401


def test_application_seal_actual_m1_commit_and_history_gc(
    diagram_db, tmp_path, monkeypatch  # noqa: F811
):
    engine, _, _ = diagram_db
    with engine.begin() as connection:
        for table in DELIVERY_TABLES:
            table.create(connection)
    for name in ("staging", "sealed", "locks"):
        (tmp_path / name).mkdir(mode=0o700)
    monkeypatch.setattr(artifacts, "STORE_ROOT", tmp_path)
    monkeypatch.setattr(physical, "STORE_ROOT", tmp_path)
    original = physical.staged

    def stage(engine, lease=None):
        return original(engine, lease, application_only=True)

    class Metadata:
        def require_staging(self, request):
            with Session(engine) as session:
                row = session.get(Generation, request.generation_id)
                if (
                    row is None
                    or row.state != "STAGING"
                    or row.attempt_snapshot != request.attempt.model_dump(mode="json")
                    or row.artifact_id != request.artifact_id
                    or row.manifest_sha256 != request.manifest_sha256
                    or row.manifest_size != request.manifest_size
                ):
                    raise PermissionError("diagram_integrity_error")

        def require_deleting(self, generation_id):
            raise PermissionError("not a cleanup authority")

    class ApplicationOnlySealer(artifacts.PrincipalSealer):
        def __init__(self):
            self.metadata = Metadata()
            self.limits = DiagramLimits()

    sealer = ApplicationOnlySealer()

    def invoke(request):
        try:
            return sealer.seal(request)
        except PermissionError:
            return None

    monkeypatch.setattr(physical, "staged", stage)
    monkeypatch.setattr(physical, "invoke", invoke)
    physical.test_physical_seal_m1_commit_rollback_read_and_gc_exclusion(engine)
    # The same ordinary copy path cannot overwrite an existing exact generation.
    folders = list((tmp_path / "sealed").iterdir())
    assert len(folders) == 1 and not folders[0].name.startswith(".candidate-")
    for member in folders[0].iterdir():
        assert member.stat().st_mode & 0o222 == 0
        source = tmp_path / "staging" / folders[0].name / member.name
        assert member.stat().st_ino != source.stat().st_ino
    # Same-UID chmod is possible: this is application immutability, not proof
    # against a compromised worker identity. Production certification is deferred.
    assert artifacts.PrincipalSealer.__init__ is not ApplicationOnlySealer.__init__
