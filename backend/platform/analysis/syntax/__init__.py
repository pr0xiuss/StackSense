"""Public exports for syntax parsing, facts, source coordinates, and execution."""

from backend.platform.analysis.syntax.base import (
    ParserAdapter,
    ParserRequest,
    ParserResult,
    SourceEncodingError,
    create_parsing_diagnostic,
    normalize_source_encoding,
)
from backend.platform.analysis.syntax.executor import ParserExecutor
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.limits import (
    DEFAULT_MAX_FACTS_PER_ANALYSIS,
    DEFAULT_MAX_FACTS_PER_ARTIFACT,
    DEFAULT_MAX_SERIALIZED_F2_BYTES,
    FactLimitExceededError,
)
from backend.platform.analysis.syntax.model import (
    DeclarationFact,
    DeclarationKind,
    ExportFact,
    ExportKind,
    FrameworkFact,
    ImportFact,
    ImportKind,
    ManifestFact,
    ParseStatus,
    ReferenceFact,
    ReferenceKind,
    SourceEncodingMetadata,
    SourceRange,
    SyntaxDocument,
    SyntaxFact,
    build_fact_key,
    sort_facts,
)
from backend.platform.analysis.syntax.python import PythonAstAdapter

__all__ = [
    "DeclarationFact",
    "DeclarationKind",
    "DEFAULT_MAX_FACTS_PER_ANALYSIS",
    "DEFAULT_MAX_FACTS_PER_ARTIFACT",
    "DEFAULT_MAX_SERIALIZED_F2_BYTES",
    "ExportFact",
    "ExportKind",
    "FrameworkFact",
    "FactLimitExceededError",
    "ImportFact",
    "ImportKind",
    "ManifestFact",
    "ParseStatus",
    "ParserAdapter",
    "ParserExecutor",
    "ParserRequest",
    "ParserResult",
    "PythonAstAdapter",
    "ReferenceFact",
    "ReferenceKind",
    "SourceEncodingError",
    "SourceEncodingMetadata",
    "SourceRange",
    "SyntaxDocument",
    "SyntaxFact",
    "TreeSitterJsTsAdapter",
    "build_fact_key",
    "create_parsing_diagnostic",
    "normalize_source_encoding",
    "sort_facts",
]
