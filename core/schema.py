# core/schema.py

"""
Schema context — describes the database to the SQL writer.
Decoupled from the agent so any schema can be plugged in.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TableSchema:
    name: str
    columns: list[str]          # "column_name TYPE" format
    description: str = ""       # optional business description


@dataclass
class SchemaContext:
    tables: list[TableSchema]
    raw_ddl: str = ""           # original CREATE TABLE statements if provided
    source: str = "manual"      # "manual" | "auto_discovered" | "file"

    def to_prompt_block(self) -> str:
        """
        Format schema for injection into SQL writer prompt.
        This is what the LLM reads when writing SQL.
        """
        lines = ["Available tables and columns:"]
        for table in self.tables:
            lines.append(f"\nTable: {table.name}")
            if table.description:
                lines.append(f"  Description: {table.description}")
            lines.append("  Columns:")
            for col in table.columns:
                lines.append(f"    - {col}")
        return "\n".join(lines)

    def table_names(self) -> list[str]:
        return [t.name for t in self.tables]


def parse_ddl(ddl: str) -> SchemaContext:
    """
    Parse CREATE TABLE statements into SchemaContext.
    Handles standard SQL DDL format.
    """
    tables = []
    # Match CREATE TABLE blocks
    pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(([^;]+)\)',
        re.IGNORECASE | re.DOTALL
    )
    for match in pattern.finditer(ddl):
        table_name = match.group(1)
        body = match.group(2)

        columns = []
        for line in body.split('\n'):
            line = line.strip().rstrip(',')
            if not line:
                continue
            # Skip constraints
            if any(line.upper().startswith(k) for k in
                   ['PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'INDEX',
                    'CONSTRAINT', 'KEY']):
                continue
            # Extract column name and type
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0]
                col_type = parts[1].rstrip(',')
                columns.append(f"{col_name} {col_type}")

        if columns:
            tables.append(TableSchema(name=table_name, columns=columns))

    return SchemaContext(tables=tables, raw_ddl=ddl, source="manual")


def discover_from_postgres(postgres_url: str) -> SchemaContext:
    """
    Auto-discover schema from a live Postgres connection.
    Reads information_schema to get all tables and columns.
    """
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(
        postgres_url,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    tables = []
    try:
        with conn.cursor() as cur:
            # Get all user tables
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            table_names = [row['table_name'] for row in cur.fetchall()]

            for table_name in table_names:
                # Get columns for each table
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                columns = [
                    f"{row['column_name']} {row['data_type']}"
                    for row in cur.fetchall()
                ]
                tables.append(TableSchema(
                    name=table_name,
                    columns=columns,
                ))
    finally:
        conn.close()

    return SchemaContext(tables=tables, source="auto_discovered")


def load_from_file(path: str) -> SchemaContext:
    """Load schema from a .sql file containing DDL statements."""
    ddl = Path(path).read_text()
    ctx = parse_ddl(ddl)
    ctx.source = "file"
    return ctx