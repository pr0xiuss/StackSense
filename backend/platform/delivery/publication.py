"""Publication ports and B2's guarded, physical PostgreSQL unit of work.

M1 owns Connection.begin/commit/rollback. Producer Sessions must be guarded,
enlisted with rollback_only on that Connection, single-threaded and borrowed.
They must reject commit/rollback/close *before* lifecycle execution and poison
the UoW even if the producer catches the error. No Session callback publishes,
activates external storage or dispatches downstream work. Only confirmed outer
commit permits M1 notifications. Producer storage sealing remains an owner port
requirement; SQL atomicity does not provide distributed artifact durability.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import get_ident
from time import monotonic
from typing import Any, Protocol, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime
from sqlalchemy import event, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Delete, Insert, Update
from sqlalchemy.sql.selectable import Select

from backend.platform.delivery.contracts import (
    AcceptedOutput,
    ArtifactReference,
    AttemptIdentity,
    FrozenContract,
    PreparedOutput,
    PublicationReceipt,
)
from backend.platform.delivery.persistence import (
    DeliveryAttemptModel,
    DeliveryOutputModel,
    DeliveryWorkModel,
)
from backend.platform.delivery.repository import (
    DeliveryOwnershipLost,
    ExecutionLease,
    SqlAlchemyDeliveryRepository,
)


class PublicationContractViolation(RuntimeError):
    """Publication must roll back; no candidate data in this exception."""


class PublicationGuard:
    """M1-owned sticky poison shared by Session, result and Connection guards."""

    def __init__(self) -> None:
        self._poisoned = False

    def reject_producer_lifecycle(self) -> None:
        self._poisoned = True
        raise PublicationContractViolation("producer transaction lifecycle forbidden")

    def poison(self) -> None:
        self._poisoned = True

    def require_healthy(self) -> None:
        if self._poisoned:
            raise PublicationContractViolation("publication transaction poisoned")


class PublicationContext(FrozenContract):
    transaction_id: UUID
    attempt: AttemptIdentity
    deadline: AwareDatetime

    def require_prepared(self, prepared: PreparedOutput) -> None:
        validated = PublicationContext.model_validate(self)
        prepared.require_binding(validated.attempt)

    def require_reference(self, reference: ArtifactReference) -> None:
        validated = PublicationContext.model_validate(self)
        reference = ArtifactReference.model_validate(reference)
        work = validated.attempt.work
        if (
            reference.scope != work.scope
            or reference.binding != work.binding
            or reference.input_fingerprint != work.input_fingerprint
            or reference.candidate_id != validated.attempt.candidate_id
        ):
            raise PublicationContractViolation("readiness context/reference mismatch")


class ReadyValidation(FrozenContract):
    reference: ArtifactReference
    # Returned only after producer validates actual storage/readiness. The type
    # itself cannot establish database commit, sealing or physical durability.


class OutputReadinessReader(Protocol):
    def validate_ready(
        self, reference: ArtifactReference, context: PublicationContext
    ) -> ReadyValidation:
        """Validate exact producer metadata locally on the enlisted transaction.

        During publication this may observe its own staged READY. During later
        prerequisite checks context identifies the original (terminal) attempt;
        no live lease/current-generation requirement applies to historical refs.
        No external I/O, alias fallback, commits or callbacks are allowed here.
        """
        ...


class ProducerPublicationPort(OutputReadinessReader, Protocol):
    def publish_prepared(
        self, prepared: PreparedOutput, context: PublicationContext
    ) -> AcceptedOutput: ...


class ProducerPublicationFactory(Protocol):
    def __call__(self, session: GuardedEnlistedSession) -> ProducerPublicationPort:
        """Receive only the guarded UoW-enlisted borrowed Session."""
        ...


class _ProducerOrmSession(Session):
    """Guard ORM identity-map escape paths such as object_session(entity)."""

    def __init__(
        self, guard: PublicationGuard, m1_control: Callable[[], bool], **kwargs: Any
    ) -> None:
        self._publication_guard, self._m1_control = guard, m1_control
        super().__init__(**kwargs)

    def commit(self) -> None:
        self._publication_guard.reject_producer_lifecycle()

    def rollback(self) -> None:
        if not self._m1_control():
            self._publication_guard.reject_producer_lifecycle()
        super().rollback()

    def close(self) -> None:
        if not self._m1_control():
            self._publication_guard.reject_producer_lifecycle()
        super().close()

    def begin(self, nested: bool = False) -> Any:
        self._publication_guard.reject_producer_lifecycle()

    def begin_nested(self) -> Any:
        self._publication_guard.reject_producer_lifecycle()


class _GuardedResult:
    """No public cursor/context/connection exposure; iteration stays budgeted."""

    def __init__(
        self, result: Any, call: Callable[..., Any], guard: PublicationGuard
    ) -> None:
        self._result, self._call, self._guard = result, call, guard

    def scalar(self) -> Any:
        return self._call(self._result.scalar)

    def scalar_one(self) -> Any:
        return self._call(self._result.scalar_one)

    def scalar_one_or_none(self) -> Any:
        return self._call(self._result.scalar_one_or_none)

    def one(self) -> Any:
        return self._call(self._result.one)

    def one_or_none(self) -> Any:
        return self._call(self._result.one_or_none)

    def first(self) -> Any:
        return self._call(self._result.first)

    def all(self) -> Any:
        return self._call(self._result.all)

    def fetchone(self) -> Any:
        return self._call(self._result.fetchone)

    def fetchall(self) -> Any:
        return self._call(self._result.fetchall)

    def fetchmany(self, size: int) -> Any:
        return self._call(self._result.fetchmany, size)

    def scalars(self) -> _GuardedResult:
        return _GuardedResult(self._call(self._result.scalars), self._call, self._guard)

    def mappings(self) -> _GuardedResult:
        return _GuardedResult(
            self._call(self._result.mappings), self._call, self._guard
        )

    def keys(self) -> Any:
        return self._call(self._result.keys)

    def close(self) -> None:
        self._call(self._result.close)

    def __iter__(self) -> Any:
        iterator = iter(self._result)
        end = object()
        while True:
            value = self._call(next, iterator, end)
            if value is end:
                return
            yield value

    @property
    def rowcount(self) -> int:
        return int(self._call(lambda: self._result.rowcount))

    def __getattr__(self, name: str) -> Any:
        self._guard.reject_producer_lifecycle()


class GuardedEnlistedSession:
    """Borrowed explicit SQL operations, not a general SQLAlchemy Session.

    No dispatcher, Query.session, engine, connection or transaction handles.
    This is trusted-code composition, not a sandbox against Python introspection.
    """

    def __init__(
        self, session: Session, guard: PublicationGuard, check: Callable[[], None]
    ) -> None:
        self._session, self._guard, self._check = session, guard, check

    def _call(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._check()
        try:
            result = function(*args, **kwargs)
            self._check()
            return result
        except BaseException:
            self._guard.poison()
            raise

    def execute(self, statement: Any, params: Any = None) -> Any:
        if not isinstance(statement, (Select, Insert, Update, Delete)):
            self._guard.reject_producer_lifecycle()
        return _GuardedResult(
            self._call(self._session.execute, statement, params),
            self._call,
            self._guard,
        )

    def scalars(self, statement: Any) -> Any:
        return self.execute(statement).scalars()

    def scalar(self, statement: Any) -> Any:
        return self.execute(statement).scalar()

    def get(self, entity: Any, key: Any) -> Any:
        return self._call(self._session.get, entity, key)

    def add(self, instance: object) -> None:
        self._call(self._session.add, instance)

    def add_all(self, instances: Any) -> None:
        self._call(self._session.add_all, instances)

    def delete(self, instance: object) -> None:
        self._call(self._session.delete, instance)

    def flush(self) -> None:
        self._call(self._session.flush)

    def commit(self) -> None:
        self._guard.reject_producer_lifecycle()

    def rollback(self) -> None:
        self._guard.reject_producer_lifecycle()

    def close(self) -> None:
        self._guard.reject_producer_lifecycle()

    def __getattr__(self, name: str) -> Any:
        # Includes event dispatch/listener registration and raw connection APIs.
        self._guard.reject_producer_lifecycle()


class PublicationUnitOfWork:
    """One fresh physical transaction; only M1 can authorize and commit it."""

    def __init__(
        self, engine: Engine, *, timeout_seconds: float, lock_timeout_ms: int
    ) -> None:
        if (
            engine.dialect.name != "postgresql"
            or timeout_seconds <= 0
            or lock_timeout_ms <= 0
        ):
            raise ValueError(
                "publication requires PostgreSQL and explicit positive budgets"
            )
        self._engine, self._timeout, self._lock_ms = (
            engine,
            timeout_seconds,
            lock_timeout_ms,
        )
        self._guard = PublicationGuard()
        self._participants: list[Session] = []
        self._active = self._authorized = self._committed = False
        self._m1_transaction_control = False

    def __enter__(self) -> Self:
        self._transaction_id = uuid4()
        self._owner_thread, self._until = get_ident(), monotonic() + self._timeout
        self._connection = self._engine.connect()
        self._transaction = self._connection.begin()

        def physical_control(connection: Any) -> None:
            if not self._m1_transaction_control:
                # SQLAlchemy may deactivate its RootTransaction even when a
                # before-commit listener raises. Abort the *physical* transaction
                # first, so it cannot leak through a reused pooled connection.
                try:
                    connection.connection.dbapi_connection.rollback()
                except BaseException:
                    connection.invalidate()
                self._guard.reject_producer_lifecycle()

        event.listen(self._connection, "commit", physical_control)
        event.listen(self._connection, "rollback", physical_control)

        def statement_control(
            connection: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            compiled = getattr(context, "compiled", None)
            if compiled is None or not isinstance(
                compiled.statement, (Select, Insert, Update, Delete)
            ):
                self._guard.reject_producer_lifecycle()
            if statement.lstrip().split(None, 1)[0].upper().rstrip(";") in {
                "COMMIT",
                "ROLLBACK",
                "ABORT",
                "BEGIN",
                "START",
                "END",
                "SAVEPOINT",
                "RELEASE",
                "PREPARE",
            }:
                self._guard.reject_producer_lifecycle()

        event.listen(self._connection, "before_cursor_execute", statement_control)
        self._active = True
        self._session = self._new_session()
        try:
            self._connection.execute(
                select(func.set_config("lock_timeout", str(self._lock_ms), True))
            )
            self._connection.execute(
                select(
                    func.set_config(
                        "statement_timeout",
                        str(max(1, int(self._timeout * 1000))),
                        True,
                    )
                )
            )
        except BaseException:
            self.__exit__()
            raise
        return self

    def _new_session(self, *, producer: bool = False) -> Session:
        session: Session
        if producer:
            session = _ProducerOrmSession(
                self._guard,
                lambda: self._m1_transaction_control,
                bind=self._connection,
                autoflush=False,
                expire_on_commit=False,
                join_transaction_mode="rollback_only",
            )
        else:
            session = Session(
                bind=self._connection,
                autoflush=False,
                expire_on_commit=False,
                join_transaction_mode="rollback_only",
            )
        self._participants.append(session)
        return session

    def require_healthy(self) -> None:
        self._guard.require_healthy()
        if (
            not self._active
            or self._authorized
            or get_ident() != self._owner_thread
            or not self._transaction.is_active
            or monotonic() >= self._until
        ):
            self._guard.poison()
            raise PublicationContractViolation(
                "publication inactive, expired or wrong-thread"
            )
        # Every next SQL statement receives only the remaining operation budget.
        remaining_ms = max(1, int((self._until - monotonic()) * 1000))
        self._connection.execute(
            select(func.set_config("statement_timeout", str(remaining_ms), True))
        )

    def enlist(self, factory: ProducerPublicationFactory) -> ProducerPublicationPort:
        self.require_healthy()
        borrowed = GuardedEnlistedSession(
            self._new_session(producer=True), self._guard, self.require_healthy
        )
        try:
            port = factory(borrowed)
            if not callable(getattr(port, "publish_prepared", None)) or not callable(
                getattr(port, "validate_ready", None)
            ):
                raise PublicationContractViolation("invalid publication/readiness port")
            self.require_healthy()
            return port
        except BaseException:
            self._guard.poison()
            raise

    def context(
        self, attempt: AttemptIdentity, *, deadline: datetime | None = None
    ) -> PublicationContext:
        """Same identity for every port enlisted on this physical transaction.

        Historical readiness uses the current publication budget, not the old
        producer execution deadline. Live completion additionally caps by its
        original execution deadline.
        """
        self.require_healthy()
        remaining = datetime.now(UTC) + timedelta(
            seconds=max(0, self._until - monotonic())
        )
        return PublicationContext(
            transaction_id=self._transaction_id,
            attempt=attempt,
            deadline=min(remaining, deadline) if deadline is not None else remaining,
        )

    def complete(
        self,
        lease: ExecutionLease,
        prepared: PreparedOutput,
        factory: ProducerPublicationFactory,
        *,
        stage_dependencies: Callable[[Session, PublicationReceipt], None] | None = None,
    ) -> PublicationReceipt:
        """Heartbeat must be joined by the worker before entering this UoW."""
        try:
            prepared.require_binding(lease.identity)
            self.require_healthy()
            repository = SqlAlchemyDeliveryRepository(self._session)
            repository.live(
                lease, lock=True, all_current=True
            )  # bundle -> sorted work -> attempt -> producer
            context = self.context(lease.identity, deadline=lease.deadline)
            port = self.enlist(factory)
            accepted = AcceptedOutput.model_validate(
                port.publish_prepared(prepared, context)
            )
            self.require_healthy()
            accepted.require_candidate(prepared)
            context.require_reference(accepted.reference)
            ready = ReadyValidation.model_validate(
                port.validate_ready(accepted.reference, context)
            )
            if ready.reference != accepted.reference:
                raise PublicationContractViolation(
                    "producer readiness reference mismatch"
                )
            receipt = PublicationReceipt(
                receipt_id=uuid4(), prepared=prepared, accepted=accepted
            )
            self._session.add(
                DeliveryOutputModel(
                    id=receipt.receipt_id,
                    bundle_id=lease.identity.work.bundle_id,
                    work_id=lease.identity.work.work_id,
                    attempt_id=lease.identity.attempt_id,
                    fence=lease.identity.fence,
                    receipt=receipt.model_dump(mode="json"),
                    committed_at=repository.now(),
                )
            )
            if stage_dependencies is not None:
                stage_dependencies(self._session, receipt)
            for participant in self._participants:
                self.require_healthy()
                participant.flush()
            self.require_healthy()
            # Final live-fence CAS is the authorization linearization point.
            authorized = update(DeliveryAttemptModel).where(
                DeliveryAttemptModel.id == lease.identity.attempt_id,
                DeliveryAttemptModel.work_id == lease.identity.work.work_id,
                DeliveryAttemptModel.state == "RUNNING",
                DeliveryAttemptModel.fence == lease.identity.fence,
                DeliveryAttemptModel.lease_digest == lease.digest,
                DeliveryAttemptModel.worker_id == lease.worker_id,
                DeliveryAttemptModel.expires_at > func.clock_timestamp(),
            )
            ended = (
                authorized.values(
                    state="COMPLETED",
                    lease_digest=None,
                    expires_at=None,
                    ended_at=func.clock_timestamp(),
                )
                .returning(DeliveryAttemptModel.work_id)
                .cte("authorized_delivery_completion")
            )
            completed = self._connection.execute(
                update(DeliveryWorkModel)
                .where(
                    DeliveryWorkModel.id.in_(select(ended.c.work_id)),
                    DeliveryWorkModel.id == lease.identity.work.work_id,
                    DeliveryWorkModel.fence == lease.identity.fence,
                    DeliveryWorkModel.dispatch_epoch == lease.identity.dispatch_epoch,
                    DeliveryWorkModel.state == "RUNNING",
                    DeliveryWorkModel.is_current.is_(True),
                )
                .values(state="COMPLETED", safe_reason=None)
                .returning(DeliveryWorkModel.id)
            ).scalar_one_or_none()
            if completed is None:
                raise DeliveryOwnershipLost(
                    "final delivery publication authorization lost"
                )
            self._authorized = True
            return receipt
        except BaseException:
            self._guard.poison()
            raise

    def coordinate(self, operation: Callable[[Session], None]) -> None:
        """M1-only dependency transaction, never exposed to producer ports.

        The callback locks the bundle and sorted current works before validating
        producer readiness. Commit remains exclusively owned by this UoW.
        """
        self.require_healthy()
        if self._authorized:
            raise PublicationContractViolation("publication already authorized")
        try:
            operation(self._session)
            for participant in self._participants:
                self.require_healthy()
                participant.flush()
            self.require_healthy()
            self._authorized = True
        except BaseException:
            self._guard.poison()
            raise

    def commit(self) -> None:
        # No query or ORM flush after final CAS. Check local guard/transaction
        # only: the lease need not remain live at the physical WAL commit instant.
        self._guard.require_healthy()
        if (
            not self._active
            or not self._authorized
            or get_ident() != self._owner_thread
            or not self._transaction.is_active
            or monotonic() >= self._until
        ):
            raise PublicationContractViolation("publication not authorized for commit")
        self._m1_transaction_control = True
        try:
            self._transaction.commit()
        finally:
            self._m1_transaction_control = False
        self._committed, self._active = True, False

    def __exit__(self, *exc: object) -> None:
        self._active = False
        self._m1_transaction_control = True
        try:
            if self._transaction.is_active:
                self._transaction.rollback()
        finally:
            if not self._committed and not self._connection.invalidated:
                try:
                    dbapi = self._connection.connection.dbapi_connection
                    if dbapi is None:
                        self._connection.invalidate()
                    else:
                        dbapi.rollback()
                except BaseException:
                    self._connection.invalidate()
            for session in reversed(self._participants):
                session.close()
            self._connection.close()
