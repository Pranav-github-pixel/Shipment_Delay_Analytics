import pytest
from app.services.sql_guard import validate_query
from app.services import query_manager


@pytest.mark.parametrize('sql', [
    'DROP VIEW shipments', 'SELECT * FROM shipments; DELETE FROM shipments',
    "SELECT * FROM csv.`C:/private.csv`", "SELECT reflect('java.lang.System','getenv','PATH') FROM shipments",
    'SELECT * FROM shipments a CROSS JOIN shipments b', 'SELECT * FROM other_table',
    'WITH x AS (SELECT * FROM shipments) SELECT * FROM x', 'SELECT * FROM (SELECT * FROM shipments)',
    "SELECT java_method('java.lang.System','getenv','PATH') FROM shipments", 'SELECT * INTO result FROM shipments',
])
def test_unsafe_queries(sql):
    with pytest.raises(ValueError):
        validate_query(sql)


def test_saved_queries(tmp_path, monkeypatch):
    monkeypatch.setattr(query_manager.config, 'ARTIFACT_DIR', tmp_path)
    for q in query_manager.DEFAULTS:
        validate_query(q['query'])
    query_manager.save_query('Test', 'SELECT COUNT(*) FROM shipments')
    assert any(q['name'] == 'Test' for q in query_manager.get_all_queries())
    query_manager.delete_query('Test')
    with pytest.raises(KeyError):
        query_manager.delete_query('Test')
