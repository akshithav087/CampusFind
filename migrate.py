from pathlib import Path

from db import get_db_connection


schema_file = Path(__file__).resolve().parent.parent / "database" / "schema.sql"

with get_db_connection() as connection:
    with connection.cursor() as cursor:
        cursor.execute(schema_file.read_text(encoding="utf-8"))
