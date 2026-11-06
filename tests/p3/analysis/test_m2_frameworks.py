"""Batch 4 framework enrichment tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.platform.analysis.frameworks import FrameworkEnrichmentService
from backend.platform.analysis.inspection.model import FrameworkDetection
from backend.platform.analysis.syntax.base import ParserRequest
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.model import FrameworkFact
from backend.platform.analysis.syntax.python import PythonAstAdapter


@pytest.mark.parametrize(
    ("framework", "language", "path", "source", "expected_type"),
    (
        (
            "django",
            "python",
            "app/models.py",
            b"from django.db import models\nclass User(models.Model):\n    pass\n",
            "model",
        ),
        (
            "flask",
            "python",
            "app/views.py",
            b"from flask import Flask\n@app.route('/hidden')\ndef home():\n    pass\n",
            "route",
        ),
        (
            "fastapi",
            "python",
            "app/api.py",
            (
                b"from fastapi import FastAPI\n"
                b"@app.get('/hidden')\n"
                b"def home():\n    pass\n"
            ),
            "route",
        ),
        (
            "express",
            "typescript",
            "src/server.ts",
            b'import express from "express";\napp.get("/hidden", handler);\n',
            "route",
        ),
        (
            "nestjs",
            "typescript",
            "src/users.ts",
            (
                b'import { Controller, Get } from "@nestjs/common";\n'
                b'@Controller("users")\n'
                b"class Users { @Get() list() {} }\n"
            ),
            "controller",
        ),
        (
            "nextjs",
            "tsx",
            "app/page.tsx",
            b"export const Page = () => <main />;\n",
            "page",
        ),
    ),
)
def test_framework_enrichment_uses_generic_facts_once(
    framework: str,
    language: str,
    path: str,
    source: bytes,
    expected_type: str,
) -> None:
    adapter = PythonAstAdapter() if language == "python" else TreeSitterJsTsAdapter()
    parsed = adapter.parse(ParserRequest(uuid4(), path, source, language))
    assert parsed.success and parsed.document is not None
    generic_count = len(parsed.document.facts)

    documents = FrameworkEnrichmentService().enrich(
        (parsed.document,),
        (FrameworkDetection(framework, "confirmed"),),
        uuid4(),
    )

    facts = [fact for fact in documents[0].facts if isinstance(fact, FrameworkFact)]
    assert any(fact.fact_type == expected_type for fact in facts)
    assert len(documents[0].facts) > generic_count
    assert all(fact.supporting_fact_keys for fact in facts)
    assert "/hidden" not in str(facts)


def test_supported_or_unrelated_framework_does_not_fabricate_facts() -> None:
    parsed = PythonAstAdapter().parse(
        ParserRequest(uuid4(), "app.py", b"def route():\n    pass\n", "python")
    )
    assert parsed.document is not None

    documents = FrameworkEnrichmentService().enrich(
        (parsed.document,),
        (
            FrameworkDetection("flask", "supported"),
            FrameworkDetection("fastapi", "confirmed"),
        ),
        uuid4(),
    )

    assert not any(isinstance(fact, FrameworkFact) for fact in documents[0].facts)
