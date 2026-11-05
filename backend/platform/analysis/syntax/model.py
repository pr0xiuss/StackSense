"""Canonical F2 syntax models, source range coordinates, and syntax facts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class ParseStatus(StrEnum):
    """Status of parsing an individual source artifact."""

    PARSED = "parsed"
    PARSED_WITH_ERRORS = "parsed_with_errors"
    FAILED = "failed"


class DeclarationKind(StrEnum):
    """Kinds of declaration facts."""

    MODULE = "module"
    PACKAGE = "package"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    VARIABLE = "variable"
    REACT_COMPONENT = "react_component"


class ImportKind(StrEnum):
    """Kinds of import facts."""

    MODULE = "module"
    NAMED = "named"
    DEFAULT = "default"
    ALL = "all"
    SIDE_EFFECT = "side_effect"


class ExportKind(StrEnum):
    """Kinds of export facts."""

    NAMED = "named"
    DEFAULT = "default"
    ALL = "all"
    RE_EXPORT = "re_export"


class ReferenceKind(StrEnum):
    """Kinds of reference facts."""

    CALL = "call"
    NAME = "name"
    ATTRIBUTE = "attribute"
    INHERITANCE = "inheritance"
    DECORATOR = "decorator"
    REACT_COMPOSITION = "react_composition"


@dataclass(frozen=True)
class SourceRange:
    """Canonical UTF-8 source range coordinates.

    Coordinates represent positions in the canonical decoded/UTF-8 re-encoded source:
    - start_byte, end_byte: 0-based absolute byte offsets, end-exclusive.
    - start_line, end_line: 1-based line numbers.
    - start_column, end_column: 0-based UTF-8 byte column offsets within line.
    """

    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    start_column: int
    end_column: int

    def __post_init__(self) -> None:
        if self.start_byte < 0 or self.end_byte < self.start_byte:
            msg = (
                f"Invalid byte range: start_byte={self.start_byte}, "
                f"end_byte={self.end_byte}"
            )
            raise ValueError(msg)
        if self.start_line < 1 or self.end_line < self.start_line:
            msg = (
                f"Invalid line range: start_line={self.start_line}, "
                f"end_line={self.end_line}"
            )
            raise ValueError(msg)
        if self.start_column < 0 or self.end_column < 0:
            msg = (
                f"Invalid column range: start_column={self.start_column}, "
                f"end_column={self.end_column}"
            )
            raise ValueError(msg)
        if self.start_line == self.end_line and self.end_column < self.start_column:
            msg = (
                f"Invalid column ordering on same line: "
                f"start_col={self.start_column}, end_col={self.end_column}"
            )
            raise ValueError(msg)

    def contains(self, other: SourceRange) -> bool:
        """Check if this source range strictly encloses another range."""
        return self.start_byte <= other.start_byte and self.end_byte >= other.end_byte


@dataclass(frozen=True)
class SourceEncodingMetadata:
    """Metadata describing the original and normalized encoding of the source."""

    detected_encoding: str
    has_bom: bool
    line_count: int
    byte_count: int
    is_utf8_clean: bool


@dataclass(frozen=True)
class DeclarationFact:
    """Fact recording a declared symbol or syntactic entity."""

    fact_key: str
    kind: DeclarationKind
    name: str
    qualified_name: str | None
    container_key: str | None
    modifiers: tuple[str, ...]
    decorators: tuple[str, ...]
    signature_text: str | None
    declaration_range: SourceRange
    name_range: SourceRange


@dataclass(frozen=True)
class ImportFact:
    """Fact recording an import statement or dependency binding."""

    fact_key: str
    kind: ImportKind
    source_module: str
    relative_level: int
    imported_name: str | None
    local_alias: str | None
    is_type_only: bool
    is_commonjs: bool
    range: SourceRange


@dataclass(frozen=True)
class ExportFact:
    """Fact recording an exported symbol or interface."""

    fact_key: str
    kind: ExportKind
    local_name: str | None
    exported_name: str
    source_module: str | None
    is_type_only: bool
    is_commonjs: bool
    range: SourceRange


@dataclass(frozen=True)
class ReferenceFact:
    """Fact recording an identifier reference, call, inheritance, or composition."""

    fact_key: str
    kind: ReferenceKind
    source_declaration_key: str | None
    target_name: str
    range: SourceRange


@dataclass(frozen=True)
class FrameworkFact:
    """Fact recording framework evidence (e.g. route, controller, middleware)."""

    fact_key: str
    framework_name: str
    artifact_id: UUID
    fact_type: str
    name: str
    details: dict[str, Any]
    supporting_fact_keys: tuple[str, ...]
    range: SourceRange | None


@dataclass(frozen=True)
class ManifestFact:
    """Fact recording declared dependency or configuration in a manifest."""

    fact_key: str
    manifest_type: str
    name: str
    version: str | None
    scope: str | None
    is_dev: bool
    raw_key: str
    range: SourceRange | None


SyntaxFact = (
    DeclarationFact
    | ImportFact
    | ExportFact
    | ReferenceFact
    | FrameworkFact
    | ManifestFact
)


def build_fact_key(
    artifact_path: str,
    kind: str,
    discriminator: str,
    source_range: SourceRange | None,
) -> str:
    """Derive a deterministic document-local fact key."""
    norm_path = artifact_path.replace("\\", "/").strip("/")
    norm_disc = discriminator.strip().replace(" ", "_")
    if source_range is not None:
        range_part = f"{source_range.start_byte}_{source_range.end_byte}"
    else:
        range_part = "none"
    return f"{norm_path}::{kind}::{norm_disc}::{range_part}"


def fact_sort_key(fact: SyntaxFact) -> tuple[int, int, str, str]:
    """Sort key for fact ordering: (start_byte, end_byte, kind, fact_key)."""
    if isinstance(fact, DeclarationFact):
        return (
            fact.declaration_range.start_byte,
            fact.declaration_range.end_byte,
            f"decl_{fact.kind.value}",
            fact.fact_key,
        )
    if isinstance(fact, (ImportFact, ExportFact, ReferenceFact)):
        return (
            fact.range.start_byte,
            fact.range.end_byte,
            f"ref_{fact.kind.value}",
            fact.fact_key,
        )
    if isinstance(fact, (FrameworkFact, ManifestFact)):
        if fact.range is not None:
            return (
                fact.range.start_byte,
                fact.range.end_byte,
                f"spec_{fact.__class__.__name__}",
                fact.fact_key,
            )
        return (-1, -1, f"spec_{fact.__class__.__name__}", fact.fact_key)
    return (0, 0, fact.__class__.__name__, fact.fact_key)


def sort_facts(facts: Iterable[SyntaxFact]) -> tuple[SyntaxFact, ...]:
    """Deterministically sort syntax facts."""
    return tuple(sorted(facts, key=fact_sort_key))


@dataclass(frozen=True)
class SyntaxDocument:
    """Immutable parsed syntax document for a single source artifact."""

    artifact_id: UUID
    path: str
    content_hash: str
    language: str
    language_version: str | None
    parser_adapter_id: str
    parser_adapter_version: str
    grammar_abi_version: int | None
    parse_status: ParseStatus
    encoding_metadata: SourceEncodingMetadata
    facts: tuple[SyntaxFact, ...]
    diagnostic_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        norm_path = self.path.replace("\\", "/")
        if norm_path.startswith("/") or norm_path.startswith("./"):
            raise ValueError(
                f"Artifact path must be normalized relative POSIX path: {self.path}"
            )
        # Verify facts are sorted deterministically
        sorted_facts = sort_facts(self.facts)
        if self.facts != sorted_facts:
            object.__setattr__(self, "facts", sorted_facts)
