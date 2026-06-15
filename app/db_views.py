"""Postgres views backing compute-on-read lineage aggregations.

These are plain (non-materialized) views: stored queries with zero storage,
always correct, no REFRESH, no drift. The SQL lives here as the single source of
truth, used by BOTH the Alembic migration (the real database) and the test
harness (``tests/conftest.py`` builds its schema with ``Base.metadata.create_all``,
not migrations — so it must create the views from this same SQL).

We keep exactly one view: ``latest_result_per_build_case``. It encodes the one
tricky rule — "the current result of a case in a build is its LATEST execution"
— so every consumer (rollup, build detail, diff, case history) agrees even when
a case is executed several times in one build (re-runs, retries, cascade-blocks).
Higher-level aggregations (rollup, diff, history) are parameterized and live in
``app/services/lineage.py``, reading from this view.
"""

LATEST_RESULT_PER_BUILD_CASE = """
CREATE OR REPLACE VIEW latest_result_per_build_case AS
SELECT DISTINCT ON (e.build_id, v.case_id)
       e.build_id   AS build_id,
       v.case_id    AS case_id,
       e.id         AS execution_id,
       e.version_id AS version_id,
       e.status     AS status,
       e.duration   AS duration,
       e.created_at AS created_at
FROM executions e
JOIN test_case_versions v ON v.id = e.version_id
WHERE e.build_id IS NOT NULL
ORDER BY e.build_id, v.case_id, e.created_at DESC, e.id DESC
"""

CREATE_VIEWS_SQL = [LATEST_RESULT_PER_BUILD_CASE]
DROP_VIEWS_SQL = ["DROP VIEW IF EXISTS latest_result_per_build_case"]
