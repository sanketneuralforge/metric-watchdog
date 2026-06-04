# core/db.py

import psycopg2
import psycopg2.extras
from config.settings import settings

# Dynamic whitelist — populated from SchemaContext at runtime
_allowed_tables: set[str] = set()


def set_allowed_tables(table_names: list[str]):
    """Called once schema is loaded — sets which tables can be queried."""
    global _allowed_tables
    _allowed_tables = {t.lower() for t in table_names}


def get_conn():
    return psycopg2.connect(
        settings.postgres_url,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def execute_query(sql: str, params: tuple = None) -> list[dict]:
    _validate_query(sql)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def execute_query_safe(sql: str, params: tuple = None) -> tuple[list[dict], str | None]:
    try:
        return execute_query(sql, params), None
    except Exception as e:
        return [], str(e)


def _validate_query(sql: str):
    import re
    sql_upper = sql.upper().strip()

    # Block write operations
    for keyword in ["INSERT", "UPDATE", "DELETE", "DROP",
                    "CREATE", "ALTER", "TRUNCATE"]:
        if re.search(rf'\b{keyword}\b', sql_upper):
            raise ValueError(f"Write operation not allowed: {keyword}")

    # Check tables against dynamic whitelist if populated
    if _allowed_tables:
        tables = re.findall(
            r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            sql_upper
        )
        for table in tables:
            if table.lower() not in _allowed_tables:
                raise ValueError(f"Table not in schema: {table}")