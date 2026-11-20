"""C2 byte identity rules, independent of persistence and runtime geometry."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from backend.platform.analysis.architecture.model import (
    ArchitectureEntityKind as Kind,
)
from backend.platform.analysis.architecture.model import (
    ArchitectureRelationshipKind as Rel,
)
from backend.platform.delivery.contracts import DiagramTemplate

VERSION = "1.0.0"
_JSON_ESCAPE = re.compile(r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})')


def _escape_json(match: re.Match[str]) -> str:
    token = match.group()
    controls = {
        "\\b": "\\u0008",
        "\\t": "\\u0009",
        "\\n": "\\u000a",
        "\\f": "\\u000c",
        "\\r": "\\u000d",
    }
    return controls.get(token, token)


DOMAINS = frozenset(
    f"ss.diagram.{name}"
    for name in (
        "id",
        "node",
        "edge",
        "group",
        "semantic",
        "members",
        "layout",
        "view",
        "profile",
        "port",
        "label",
        "glyph",
    )
)


def canonical_bytes(value: object) -> bytes:
    """Integer-only canonical JSON, no normalization or short control escapes.

    Callers explicitly order sets; this encoder preserves meaningful array order.
    Conversion of nested frozen C0 values uses their existing wire representation.
    """

    def wire(item: object) -> Any:
        if isinstance(item, BaseModel):
            return wire(item.model_dump(mode="json"))
        if isinstance(item, Enum):
            return wire(item.value)
        if isinstance(item, UUID):
            return str(item)
        if item is None or type(item) is bool or isinstance(item, str):
            return item
        if type(item) is int:
            if abs(item) > 2**53 - 1:
                raise ValueError("integer outside C2 exact range")
            return item
        if isinstance(item, Mapping):
            if any(not isinstance(k, str) for k in item):
                raise ValueError("C2 object keys must be text")
            return {k: wire(v) for k, v in item.items()}
        if isinstance(item, (tuple, list)):
            return [wire(v) for v in item]
        raise ValueError("unsupported C2 JSON value")

    # For Unicode scalars, code-point and UTF-8 byte key ordering agree. Repair
    # complete escape tokens only, so a literal backslash+n is never rewritten.
    encoded = json.dumps(
        wire(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return _JSON_ESCAPE.sub(_escape_json, encoded).encode("utf-8", "strict")


def load_json(data: bytes, *, max_bytes: int) -> object:
    """Bounded wire ingress rejecting duplicate keys, BOM, floats and constants."""
    if len(data) > max_bytes:
        raise ValueError("C2 input capacity exceeded")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate C2 object key")
            result[key] = value
        return result

    def reject(value: str) -> object:
        raise ValueError("noninteger C2 JSON number")

    def integer(value: str) -> int:
        if value == "-0":
            raise ValueError("negative zero is not canonical C2 JSON")
        number = int(value)
        if abs(number) > 2**53 - 1:
            raise ValueError("integer outside C2 exact range")
        return number

    try:
        result: object = json.loads(
            data.decode("utf-8", "strict"),
            object_pairs_hook=pairs,
            parse_int=integer,
            parse_float=reject,
            parse_constant=reject,
        )
        canonical_bytes(result)
        return result
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("invalid C2 JSON") from exc


def digest(domain: str, payload: object) -> str:
    if domain not in DOMAINS:
        raise ValueError("unsupported diagram hash domain")
    if domain in ("ss.diagram.semantic", "ss.diagram.layout"):
        payload = normalize_sets(payload)
    return hashlib.sha256(canonical_bytes((domain, VERSION, payload))).hexdigest()


def normalize_sets(value: Any, *, owner: str = "", shallow: bool = False) -> Any:
    """Canonicalize declared C2 sets only, never path/route/glyph placement order."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {
            key: (
                normalize_sets(item, owner=key, shallow=shallow)
                if not shallow or isinstance(item, (tuple, list))
                else item
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        items = list(value) if shallow else [normalize_sets(item) for item in value]
        sets = {
            "nodes",
            "edges",
            "groups",
            "ports",
            "labels",
            "routes",
            "annotations",
            "provenance",
            "legend",
            "counts",
            "reasons",
            "omitted",
            "root_ids",
            "selected_entity_ids",
            "entity_kinds",
            "statuses",
            "relationship_kinds",
            "boundary_ids",
            "multi_parent",
            "visible_member_ids",
            "subject_ids",
            "evidence",
            "records",
            "parents",
            "layers",
            "limitations",
            "members",
        }
        # Glyph placements retain their text order, including repeated glyphs.
        table = (
            owner == "glyphs"
            and bool(items)
            and isinstance(items[0], dict)
            and "commands" in items[0]
        )

        def key(item: Any) -> bytes:
            if isinstance(item, Mapping):
                for field in ("id", "edge_id", "group_id", "key"):
                    if field in item:
                        return str(item[field]).encode("utf-8")
                for field in ("record", "relationship", "child"):
                    if isinstance(item.get(field), Mapping):
                        return str(item[field]["id"]).encode("utf-8")
                if "member" in item:
                    return str(item["member"]).encode("utf-8")
            if isinstance(item, str):
                return item.encode("utf-8")
            return canonical_bytes(item)

        if owner in sets or table:
            items.sort(key=key)
        return tuple(items) if isinstance(value, tuple) else items
    return value


def visual_id(kind: str, payload: object) -> str:
    prefix = {
        "id": "diagram://",
        "node": "dn:",
        "edge": "de:",
        "group": "dg:",
        "port": "dp:",
        "label": "dl:",
        "glyph": "gl:",
    }.get(kind)
    if prefix is None:
        raise ValueError("unsupported diagram identity kind")
    return prefix + digest(f"ss.diagram.{kind}", payload)


@dataclass(frozen=True, slots=True)
class TemplateRules:
    """Versioned eligibility, not builders or inferred canonical facts.

    Conditional boundary eligibility is deliberately separate from unconditional
    defaults. Builders must prove it from actual relationships/containment.
    """

    template: DiagramTemplate
    default_kinds: tuple[Kind, ...]
    conditional_kinds: tuple[Kind, ...]
    default_relationships: tuple[Rel, ...]
    optional_relationships: tuple[Rel, ...]
    contains_is_dependency: Literal[False] = False

    def fingerprint(self, selection_policy: Mapping[str, int]) -> str:
        return digest(
            "ss.diagram.profile",
            {
                "template": self.template,
                "template_version": VERSION,
                "builder_version": VERSION,
                "selection_version": VERSION,
                "identity_version": VERSION,
                "default_kinds": sorted(self.default_kinds),
                "conditional_kinds": sorted(self.conditional_kinds),
                "default_relationships": sorted(self.default_relationships),
                "optional_relationships": sorted(self.optional_relationships),
                "contains_is_dependency": self.contains_is_dependency,
                "selection_policy": selection_policy,
            },
        )


ARCHITECTURAL_RELATIONSHIPS = (
    Rel.DEPENDS_ON,
    Rel.CALLS,
    Rel.EXPOSES,
    Rel.ROUTES_TO,
    Rel.PRODUCES,
    Rel.CONSUMES,
    Rel.CONNECTS_TO,
    Rel.PERSISTS_TO,
    Rel.USES,
)
DEPENDENCY_RELATIONSHIPS = tuple(r for r in Rel if r != Rel.CONTAINS)


def template_rules(template: DiagramTemplate) -> TemplateRules:
    """Fixed four-template registry; never dynamically loaded user rules."""
    if template == DiagramTemplate.OVERVIEW:
        return TemplateRules(
            template,
            (
                Kind.APPLICATION,
                Kind.FRONTEND_APPLICATION,
                Kind.SERVICE,
                Kind.WORKER,
                Kind.DATABASE,
                Kind.MESSAGE_BROKER,
                Kind.QUEUE,
                Kind.TOPIC,
                Kind.EXTERNAL_SERVICE,
                Kind.EXTERNAL_API,
            ),
            (
                Kind.ENDPOINT,
                Kind.DATA_REPOSITORY,
                Kind.CONTROLLER,
                Kind.COMPONENT,
                Kind.MODULE,
            ),
            ARCHITECTURAL_RELATIONSHIPS,
            (),
        )
    if template == DiagramTemplate.COMPONENT:
        return TemplateRules(
            template,
            (
                Kind.APPLICATION,
                Kind.FRONTEND_APPLICATION,
                Kind.MODULE,
                Kind.COMPONENT,
                Kind.CONTROLLER,
                Kind.SERVICE,
                Kind.WORKER,
                Kind.DATA_REPOSITORY,
                Kind.ENDPOINT,
            ),
            (
                Kind.DATABASE,
                Kind.MESSAGE_BROKER,
                Kind.QUEUE,
                Kind.TOPIC,
                Kind.EXTERNAL_SERVICE,
                Kind.EXTERNAL_API,
                Kind.LIBRARY,
            ),
            ARCHITECTURAL_RELATIONSHIPS,
            (Rel.IMPORTS, Rel.EXTENDS, Rel.IMPLEMENTS),
        )
    if template == DiagramTemplate.DEPENDENCY:
        return TemplateRules(
            template,
            tuple(k for k in Kind if k != Kind.UNKNOWN),
            (Kind.UNKNOWN,),
            DEPENDENCY_RELATIONSHIPS,
            (),
        )
    if template == DiagramTemplate.DATA_FLOW:
        return TemplateRules(
            template,
            (
                Kind.APPLICATION,
                Kind.FRONTEND_APPLICATION,
                Kind.SERVICE,
                Kind.WORKER,
                Kind.CONTROLLER,
                Kind.COMPONENT,
                Kind.ENDPOINT,
                Kind.DATA_REPOSITORY,
                Kind.DATABASE,
                Kind.MESSAGE_BROKER,
                Kind.QUEUE,
                Kind.TOPIC,
                Kind.EXTERNAL_SERVICE,
                Kind.EXTERNAL_API,
            ),
            (),
            (Rel.PERSISTS_TO, Rel.PRODUCES, Rel.CONSUMES, Rel.CALLS, Rel.ROUTES_TO),
            (Rel.CONNECTS_TO,),
        )
    raise ValueError("unsupported diagram template")
