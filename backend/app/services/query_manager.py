import json
import os
from threading import RLock
from app import config
from app.services.sql_guard import validate_query

lock = RLock()
DEFAULTS = [
    {"name": "Delay by shipping mode", "query": "SELECT shipping_mode, COUNT(*) AS orders, AVG(delayed) AS delay_rate FROM shipments GROUP BY shipping_mode ORDER BY delay_rate DESC"},
    {"name": "Regional performance", "query": "SELECT region, COUNT(*) AS orders, AVG(delayed) AS delay_rate FROM shipments GROUP BY region ORDER BY delay_rate DESC"},
    {"name": "Monthly trend", "query": "SELECT order_month, COUNT(*) AS orders, AVG(delayed) AS delay_rate FROM shipments GROUP BY order_month ORDER BY order_month"},
    {"name": "Customer segments", "query": "SELECT customer_segment, COUNT(*) AS orders, AVG(delayed) AS delay_rate FROM shipments GROUP BY customer_segment"},
]


def get_all_queries():
    with lock:
        path = config.ARTIFACT_DIR / "queries.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else list(DEFAULTS)


def save_query(name, sql):
    validate_query(sql)
    with lock:
        queries = [q for q in get_all_queries() if q["name"] != name]
        queries.append({"name": name, "query": sql})
        _write(queries)


def delete_query(name):
    with lock:
        queries = get_all_queries()
        if not any(q["name"] == name for q in queries):
            raise KeyError("Saved query not found")
        _write([q for q in queries if q["name"] != name])


def _write(queries):
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.ARTIFACT_DIR / "queries.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(queries, indent=2), encoding="utf-8")
    os.replace(temporary, path)
