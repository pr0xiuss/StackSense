"""Explicit fresh ISOLATED B1 schema setup. Not a release migration/grant tool.

Usage: P5_TEST_DATABASE_URL=<private test URL> python -m ...provision_database SCHEMA
Never changes an existing schema, creates roles or selects application .env.
"""

import os
import re
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.platform.delivery.persistence import DELIVERY_TABLES
from backend.platform.diagrams.persistence import install_prototype


def main() -> None:
    if (
        len(sys.argv) != 2
        or re.fullmatch(r"p5_diagram_[0-9a-f]{32}", sys.argv[1]) is None
    ):
        raise ValueError("explicit new B1 schema required")
    url = make_url(os.environ["P5_TEST_DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith(
        "stacksense_p5_b2_"
    ):
        raise ValueError("isolated P5 PostgreSQL required")
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    schema = sys.argv[1]
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table in DELIVERY_TABLES:
                table.create(
                    connection.execution_options(schema_translate_map={None: schema})
                )
            install_prototype(connection, schema)
    finally:
        engine.dispose()
    print("B1 isolated schema created: " + schema)


if __name__ == "__main__":
    main()
