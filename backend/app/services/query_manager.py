import os

QUERY_FILE = "queries.md"

def get_all_queries():
    """Reads queries.md and returns a list of dictionaries with name and query."""
    if not os.path.exists(QUERY_FILE):
        return []
    
    queries = []
    with open(QUERY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if " - " in line:
                name, sql = line.strip().split(" - ", 1)
                queries.append({"name": name.strip(), "query": sql.strip()})
    return queries

def save_query(name: str, sql: str):
    """Saves a new query to queries.md or updates an existing one."""
    queries = get_all_queries()
    
    # Check if exists to update
    found = False
    for q in queries:
        if q["name"] == name:
            q["query"] = sql
            found = True
            break
            
    if not found:
        queries.append({"name": name, "query": sql})
        
    _write_queries(queries)

def delete_query(name: str):
    """Deletes a query by name from queries.md."""
    queries = get_all_queries()
    queries = [q for q in queries if q["name"] != name]
    _write_queries(queries)

def _write_queries(queries):
    """Helper to write the list back to queries.md."""
    with open(QUERY_FILE, "w", encoding="utf-8") as f:
        for q in queries:
            f.write(f"{q['name']} - {q['query']}\n")
