-- Administrator-reviewed ISOLATED B1 database only. psql variables schema,
-- database supplied explicitly. Never run against application/production DB.
-- Role creation/password authentication is a separate administrator decision;
-- this file grants no role membership, writes, DDL or grant options.
\set ON_ERROR_STOP on
SELECT current_database() LIKE 'stacksense_p5_b2_%'
  AND current_database() = :'database' AS isolated \gset
\if :isolated
\else
\quit 78
\endif
SELECT :'schema' ~ '^p5_diagram_[0-9a-f]{32}$' AS safe_schema \gset
\if :safe_schema
\else
\quit 78
\endif
BEGIN;
GRANT CONNECT ON DATABASE :"database" TO stacksense_diagram_seal, stacksense_diagram_gc;
GRANT USAGE ON SCHEMA :"schema" TO stacksense_diagram_seal, stacksense_diagram_gc;
GRANT SELECT ON :"schema".diagram_resource, :"schema".diagram_generation,
  :"schema".diagram_read_pin TO stacksense_diagram_seal, stacksense_diagram_gc;
GRANT SELECT ON :"schema".delivery_bundles, :"schema".delivery_work,
  :"schema".delivery_attempts, :"schema".delivery_outputs TO stacksense_diagram_gc;
ALTER ROLE stacksense_diagram_seal IN DATABASE :"database" SET default_transaction_read_only = on;
ALTER ROLE stacksense_diagram_gc IN DATABASE :"database" SET default_transaction_read_only = on;
COMMIT;
