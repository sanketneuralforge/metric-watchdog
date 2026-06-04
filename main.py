# main.py

import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import run_pipeline
from core.schema import (
    SchemaContext,
    parse_ddl,
    load_from_file,
    discover_from_postgres,
)
from config.settings import settings


def main():
    parser = argparse.ArgumentParser(
        description="Metric Watchdog — Autonomous dashboard intelligence"
    )

    # Input 1 — Dashboard
    parser.add_argument(
        "--dashboard",
        required=True,
        help="Path to dashboard screenshot (PNG/JPG) or HTML export",
    )

    # Input 2 — Schema (optional — auto-discovers if not provided)
    parser.add_argument(
        "--schema",
        required=False,
        help="Path to .sql schema file, or 'auto' to discover from DB",
        default="auto",
    )

    # Input 3 — Database (uses POSTGRES_URL from .env by default)
    parser.add_argument(
        "--db",
        required=False,
        help="Postgres connection string (overrides POSTGRES_URL in .env)",
    )

    args = parser.parse_args()

    # Override DB URL if provided
    if args.db:
        import os
        os.environ["POSTGRES_URL"] = args.db
        # Reload settings
        settings.postgres_url = args.db

    # Load schema
    schema = None
    if args.schema == "auto":
        print("  Schema: auto-discovering from Postgres")
        # orchestrator handles this
    elif Path(args.schema).exists():
        print(f"  Schema: loading from {args.schema}")
        schema = load_from_file(args.schema)
        print(f"  Schema: found {len(schema.tables)} tables")
    else:
        print(f"  Schema: treating as DDL string")
        schema = parse_ddl(args.schema)

    run_pipeline(args.dashboard, schema=schema)


if __name__ == "__main__":
    main()