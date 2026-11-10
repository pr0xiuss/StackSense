"""Deterministic framework enrichment over parser-neutral F2 facts."""

from backend.platform.analysis.frameworks.base import FrameworkEnrichmentService
from backend.platform.analysis.frameworks.javascript import JavaScriptFrameworkEnricher
from backend.platform.analysis.frameworks.python import PythonFrameworkEnricher

__all__ = [
    "FrameworkEnrichmentService",
    "JavaScriptFrameworkEnricher",
    "PythonFrameworkEnricher",
]
