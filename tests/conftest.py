"""Shared pytest configuration for StackSense tests."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    """Provide a test client for the StackSense API."""
    return TestClient(app)
