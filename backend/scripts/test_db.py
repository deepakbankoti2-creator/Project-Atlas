"""
Project Atlas — Database Connection Verification Script
Location: backend/scripts/test_db.py

Purpose:
Connect to the project_atlas MySQL database, display database info,
inspect existing tables/records, and verify connectivity safely without exposing secrets.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import inspect, text
from backend.app.core.config import settings
from backend.app.core.database import engine


def test_connection():
    print("=" * 60)
    print(" PROJECT ATLAS - DATABASE CONNECTION TEST")
    print("=" * 60)
    print(f"Target Host     : {settings.DB_HOST}")
    print(f"Target Port     : {settings.DB_PORT}")
    print(f"Target Database : {settings.DB_NAME}")
    print(f"Target User     : {settings.DB_USER}")
    print(f"Connection URL  : {settings.safe_database_url}")
    print("-" * 60)

    try:
        with engine.connect() as connection:
            # 1. Verify active database name
            result = connection.execute(text("SELECT DATABASE();"))
            active_db = result.scalar()
            print(f"[SUCCESS] Connected to active database: '{active_db}'")

            # 2. Inspect available tables
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            print(f"[SUCCESS] Discovered {len(table_names)} table(s) in '{active_db}':")
            for table in table_names:
                print(f"  - Table: {table}")

            # 3. Inspect columns and row counts for each table
            print("-" * 60)
            print(" TABLE DETAILS & SAMPLE RECORD COUNTS:")
            print("-" * 60)
            for table in table_names:
                columns = inspector.get_columns(table)
                col_names = [col["name"] for col in columns]
                count_res = connection.execute(text(f"SELECT COUNT(*) FROM `{table}`;"))
                count = count_res.scalar()
                print(f"  • {table} ({count} rows):")
                print(f"    Columns: {', '.join(col_names)}")

            print("=" * 60)
            print("[STATUS] MySQL database connection test SUCCEEDED!")
            print("=" * 60)
            return True

    except Exception as e:
        print("=" * 60)
        print("[STATUS] MySQL database connection test FAILED!")
        print("-" * 60)
        # Sanitize exception message to ensure no password is printed
        err_msg = str(e)
        if settings.DB_PASSWORD and settings.DB_PASSWORD in err_msg:
            err_msg = err_msg.replace(settings.DB_PASSWORD, "********")
        print(f"Error Details: {err_msg}")
        print("\nTroubleshooting Suggestions:")
        print("1. Verify that your MySQL server service ('MySQL80') is running.")
        print("2. Check the DB_USER and DB_PASSWORD entries in your .env file.")
        print("3. Ensure user has permissions for the 'project_atlas' database.")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
