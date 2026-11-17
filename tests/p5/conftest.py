"""Explicit isolated PostgreSQL only; never fall back to application .env."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.platform.delivery.persistence import DELIVERY_TABLES


@pytest.fixture
def delivery_engine():
    value = os.environ.get("P5_TEST_DATABASE_URL")
    if not value:
        pytest.skip("P5_TEST_DATABASE_URL required for real PostgreSQL proofs")
    url = make_url(value)
    if (
        not url.database
        or not url.database.startswith("stacksense_p5_b2_")
        or url.get_backend_name() != "postgresql"
    ):
        pytest.fail(
            "P5 integration requires its explicitly named isolated PostgreSQL database"
        )
    root = create_engine(
        url.set(drivername="postgresql+psycopg"), connect_args={"connect_timeout": 5}
    )
    schema = "p5_test_" + uuid4().hex
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = root.execution_options(schema_translate_map={None: schema})
    try:
        for table in DELIVERY_TABLES:
            table.create(engine)
        yield engine
    finally:
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
