"""Neo4j driver lifecycle and schema compatibility boundary."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Final, LiteralString, Protocol

from neo4j import Driver, GraphDatabase, Query
from neo4j.exceptions import ConfigurationError, DriverError, Neo4jError

from backend.platform.config import Settings

GRAPH_SCHEMA_VERSION: Final = "1.0.0"


class GraphInfrastructureError(RuntimeError):
    """Base class for safe graph infrastructure failures."""


class GraphConfigurationError(GraphInfrastructureError):
    """Raised when Neo4j configuration cannot create a driver."""


class GraphDependencyUnavailableError(GraphInfrastructureError):
    """Raised when Neo4j cannot complete an infrastructure operation."""


class GraphSchemaCompatibilityError(GraphInfrastructureError):
    """Raised when the installed graph schema is incompatible."""


@dataclass(frozen=True, slots=True)
class ConstraintSpec:
    """Expected Neo4j constraint definition."""

    name: str
    constraint_type: str
    entity_type: str
    label_or_type: str
    property_name: str
    create_query: LiteralString


@dataclass(frozen=True, slots=True)
class IndexSpec:
    """Expected Neo4j composite index definition."""

    name: str
    index_type: str
    entity_type: str
    label_or_type: str
    properties: tuple[str, ...]
    create_query: LiteralString


CONSTRAINTS: Final = (
    ConstraintSpec(
        name="architecture_entity_projection_key_unique",
        constraint_type="UNIQUENESS",
        entity_type="NODE",
        label_or_type="ArchitectureEntity",
        property_name="projection_key",
        create_query=(
            "CREATE CONSTRAINT architecture_entity_projection_key_unique "
            "IF NOT EXISTS FOR (entity:ArchitectureEntity) "
            "REQUIRE entity.projection_key IS UNIQUE"
        ),
    ),
    ConstraintSpec(
        name="projection_manifest_generation_key_unique",
        constraint_type="UNIQUENESS",
        entity_type="NODE",
        label_or_type="ProjectionManifest",
        property_name="generation_key",
        create_query=(
            "CREATE CONSTRAINT projection_manifest_generation_key_unique "
            "IF NOT EXISTS FOR (manifest:ProjectionManifest) "
            "REQUIRE manifest.generation_key IS UNIQUE"
        ),
    ),
    ConstraintSpec(
        name="arch_relationship_projection_key_unique",
        constraint_type="RELATIONSHIP_UNIQUENESS",
        entity_type="RELATIONSHIP",
        label_or_type="ARCH_RELATIONSHIP",
        property_name="projection_key",
        create_query=(
            "CREATE CONSTRAINT arch_relationship_projection_key_unique "
            "IF NOT EXISTS FOR ()-[relationship:ARCH_RELATIONSHIP]-() "
            "REQUIRE relationship.projection_key IS UNIQUE"
        ),
    ),
)

COMPOSITE_INDEXES: Final = (
    IndexSpec(
        name="architecture_entity_scope_idx",
        index_type="RANGE",
        entity_type="NODE",
        label_or_type="ArchitectureEntity",
        properties=("project_id", "architecture_version_id", "generation_id"),
        create_query=(
            "CREATE INDEX architecture_entity_scope_idx IF NOT EXISTS "
            "FOR (entity:ArchitectureEntity) "
            "ON (entity.project_id, entity.architecture_version_id, "
            "entity.generation_id)"
        ),
    ),
    IndexSpec(
        name="projection_manifest_scope_idx",
        index_type="RANGE",
        entity_type="NODE",
        label_or_type="ProjectionManifest",
        properties=("project_id", "architecture_version_id", "generation_id"),
        create_query=(
            "CREATE INDEX projection_manifest_scope_idx IF NOT EXISTS "
            "FOR (manifest:ProjectionManifest) "
            "ON (manifest.project_id, manifest.architecture_version_id, "
            "manifest.generation_id)"
        ),
    ),
    IndexSpec(
        name="arch_relationship_scope_idx",
        index_type="RANGE",
        entity_type="RELATIONSHIP",
        label_or_type="ARCH_RELATIONSHIP",
        properties=("project_id", "architecture_version_id", "generation_id"),
        create_query=(
            "CREATE INDEX arch_relationship_scope_idx IF NOT EXISTS "
            "FOR ()-[relationship:ARCH_RELATIONSHIP]-() "
            "ON (relationship.project_id, relationship.architecture_version_id, "
            "relationship.generation_id)"
        ),
    ),
)

_SHOW_CONSTRAINTS_QUERY: Final[LiteralString] = (
    "SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties "
    "WHERE name IN $names "
    "RETURN name, type, entityType, labelsOrTypes, properties ORDER BY name"
)
_SHOW_INDEXES_QUERY: Final[LiteralString] = (
    "SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties "
    "WHERE name IN $names "
    "RETURN name, type, entityType, labelsOrTypes, properties ORDER BY name"
)
_CONNECTIVITY_QUERY: Final[LiteralString] = "RETURN 1 AS ready"
_LEGACY_MANIFEST_COUNT_QUERY: Final[LiteralString] = (
    "MATCH (manifest:ArchitectureProjectionGeneration) "
    "RETURN count(manifest) AS legacy_count"
)
_DROP_LEGACY_MANIFEST_CONSTRAINT_QUERY: Final[LiteralString] = (
    "DROP CONSTRAINT architecture_projection_generation_key_unique IF EXISTS"
)


@dataclass(frozen=True, slots=True)
class Neo4jCapability:
    """Verified Neo4j server and schema capability summary."""

    server_agent: str
    protocol_version: str
    database: str
    graph_schema_version: str
    constraint_names: tuple[str, ...]
    index_names: tuple[str, ...] = ()


class GraphInfrastructure(Protocol):
    """Minimal lifecycle used by graph health composition."""

    def initialize(self) -> Neo4jCapability:
        """Verify connectivity and idempotently establish the graph schema."""

    def close(self) -> None:
        """Release infrastructure resources."""


DriverFactory = Callable[..., Driver]


class Neo4jInfrastructure:
    """Own the official Neo4j driver's lifecycle and schema bootstrap."""

    def __init__(
        self,
        settings: Settings,
        *,
        driver_factory: DriverFactory = GraphDatabase.driver,
    ) -> None:
        self._settings = settings
        self._closed = False
        try:
            self._driver = driver_factory(
                settings.neo4j_uri,
                auth=(
                    settings.neo4j_user,
                    settings.neo4j_password.get_secret_value(),
                ),
                connection_timeout=settings.neo4j_connection_timeout_seconds,
                connection_acquisition_timeout=(
                    settings.neo4j_connection_acquisition_timeout_seconds
                ),
                max_connection_pool_size=settings.neo4j_max_connection_pool_size,
            )
        except ConfigurationError, TypeError, ValueError:
            raise GraphConfigurationError(
                "Neo4j driver configuration is invalid."
            ) from None

    @property
    def closed(self) -> bool:
        """Return whether the driver has been closed."""
        return self._closed

    @property
    def driver(self) -> Driver:
        """Return the underlying Neo4j driver."""
        if self._closed:
            raise GraphConfigurationError("Neo4j infrastructure is closed.")
        return self._driver

    def initialize(self) -> Neo4jCapability:
        """Verify Neo4j and idempotently establish the required schema."""
        if self._closed:
            raise GraphConfigurationError("Neo4j infrastructure is closed.")

        try:
            self._driver.verify_connectivity()
            server_info = self._driver.get_server_info()
            with self._driver.session(
                database=self._settings.neo4j_database,
            ) as session:
                ready = session.run(
                    Query(
                        _CONNECTIVITY_QUERY,
                        timeout=self._settings.neo4j_health_timeout_seconds,
                    )
                ).single(strict=True)
                if ready is None or ready["ready"] != 1:
                    raise GraphDependencyUnavailableError(
                        "Neo4j connectivity check failed."
                    )

                legacy_count = session.run(
                    Query(
                        _LEGACY_MANIFEST_COUNT_QUERY,
                        timeout=self._settings.neo4j_health_timeout_seconds,
                    )
                ).single(strict=True)
                validate_no_legacy_manifest_data(legacy_count)
                session.run(
                    Query(
                        _DROP_LEGACY_MANIFEST_CONSTRAINT_QUERY,
                        timeout=self._settings.neo4j_health_timeout_seconds,
                    )
                ).consume()

                for constraint in CONSTRAINTS:
                    session.run(
                        Query(
                            constraint.create_query,
                            timeout=self._settings.neo4j_health_timeout_seconds,
                        )
                    ).consume()

                for index in COMPOSITE_INDEXES:
                    session.run(
                        Query(
                            index.create_query,
                            timeout=self._settings.neo4j_health_timeout_seconds,
                        )
                    ).consume()

                rows = session.run(
                    Query(
                        _SHOW_CONSTRAINTS_QUERY,
                        timeout=self._settings.neo4j_health_timeout_seconds,
                    ),
                    names=[constraint.name for constraint in CONSTRAINTS],
                ).data()

                index_rows = session.run(
                    Query(
                        _SHOW_INDEXES_QUERY,
                        timeout=self._settings.neo4j_health_timeout_seconds,
                    ),
                    names=[index.name for index in COMPOSITE_INDEXES],
                ).data()
        except GraphInfrastructureError:
            raise
        except DriverError, Neo4jError:
            raise GraphDependencyUnavailableError(
                "Neo4j infrastructure operation failed."
            ) from None
        except OSError, TimeoutError:
            raise GraphDependencyUnavailableError(
                "Neo4j infrastructure is unavailable."
            ) from None

        constraint_names = validate_constraint_rows(rows)
        index_names = validate_composite_index_rows(index_rows)
        return Neo4jCapability(
            server_agent=server_info.agent,
            protocol_version=str(server_info.protocol_version),
            database=self._settings.neo4j_database,
            graph_schema_version=GRAPH_SCHEMA_VERSION,
            constraint_names=constraint_names,
            index_names=index_names,
        )

    def close(self) -> None:
        """Close the driver exactly once."""
        if self._closed:
            return
        self._driver.close()
        self._closed = True

    def __enter__(self) -> Neo4jInfrastructure:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def validate_constraint_rows(
    rows: Iterable[Mapping[str, object]],
) -> tuple[str, ...]:
    """Fail closed unless every required constraint has its exact shape."""
    by_name = {str(row.get("name")): row for row in rows}
    for expected in CONSTRAINTS:
        actual = by_name.get(expected.name)
        if actual is None:
            raise GraphSchemaCompatibilityError(
                "Required Neo4j schema constraint is missing."
            )

        labels_or_types = actual.get("labelsOrTypes")
        properties = actual.get("properties")
        if (
            actual.get("type") != expected.constraint_type
            or actual.get("entityType") != expected.entity_type
            or not isinstance(labels_or_types, list)
            or labels_or_types != [expected.label_or_type]
            or not isinstance(properties, list)
            or properties != [expected.property_name]
        ):
            raise GraphSchemaCompatibilityError(
                "Neo4j schema constraint is incompatible."
            )

    return tuple(sorted(by_name))


def validate_composite_index_rows(
    rows: Iterable[Mapping[str, object]],
) -> tuple[str, ...]:
    """Fail closed unless every required composite scope index has its exact shape."""
    by_name = {str(row.get("name")): row for row in rows}
    for expected in COMPOSITE_INDEXES:
        actual = by_name.get(expected.name)
        if actual is None:
            raise GraphSchemaCompatibilityError(
                "Required Neo4j composite scope index is missing."
            )

        labels_or_types = actual.get("labelsOrTypes")
        properties = actual.get("properties")
        if (
            actual.get("type") != expected.index_type
            or actual.get("entityType") != expected.entity_type
            or not isinstance(labels_or_types, list)
            or labels_or_types != [expected.label_or_type]
            or not isinstance(properties, list)
            or tuple(properties) != expected.properties
        ):
            raise GraphSchemaCompatibilityError(
                "Neo4j composite scope index is incompatible."
            )

    return tuple(sorted(by_name))


def validate_no_legacy_manifest_data(row: Mapping[str, object] | None) -> None:
    """Fail closed instead of dropping a constraint protecting legacy data."""
    if row is None:
        raise GraphSchemaCompatibilityError(
            "Legacy Neo4j manifest compatibility check returned no result."
        )
    count = row.get("legacy_count")
    if type(count) is not int or count < 0:
        raise GraphSchemaCompatibilityError(
            "Legacy Neo4j manifest compatibility result is invalid."
        )
    if count:
        raise GraphSchemaCompatibilityError(
            "Legacy Neo4j manifest data requires an explicit migration."
        )
