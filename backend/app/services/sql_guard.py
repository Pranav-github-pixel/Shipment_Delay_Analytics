"""Single analytical SELECT against the processed shipments view."""
import sqlglot
from sqlglot import exp

FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX", "ROUND", "ABS", "COALESCE", "CAST",
             "TRY_CAST", "YEAR", "MONTH", "DAY", "DATE_TRUNC", "TIME_TO_STR", "IF", "CASE",
             "LOWER", "UPPER", "NULLIF", "STDDEV", "STDDEV_SAMP", "VARIANCE", "MEDIAN"}


def validate_query(query):
    try:
        statements = sqlglot.parse(query, read="spark")
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"Invalid SQL: {exc}") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Only one SELECT query is permitted")
    tree = statements[0]
    if tree.args.get("with") or tree.args.get("with_") or tree.find(exp.Join) or tree.find(exp.Subquery):
        raise ValueError("Use a single SELECT from shipments; joins, CTEs and subqueries are not supported")
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name.lower() != "shipments" or tables[0].db or tables[0].catalog:
        raise ValueError("Queries may read only the shipments view")
    for node in tree.walk():
        if isinstance(node, (exp.Command, exp.Into)):
            raise ValueError("Only read-only analytics are permitted")
        if isinstance(node, exp.Func):
            name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()
            if name not in FUNCTIONS:
                raise ValueError(f"Function {name} is not available in the analytical console")
    return tree.sql(dialect="spark")
