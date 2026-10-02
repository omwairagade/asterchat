"""Apply checked-in Aster SQL migrations once, recording each successful version."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aster.db import connect  # noqa: E402

MIGRATIONS = ROOT / "migrations"


def apply_migrations() -> list[str]:
    connection = connect()
    applied: list[str] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS aster_schema_migrations ("
                "version VARCHAR(32) NOT NULL PRIMARY KEY, "
                "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        connection.commit()
        for path in sorted(MIGRATIONS.glob("*.sql")):
            version = path.name.split("_", 1)[0]
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT version FROM aster_schema_migrations WHERE version = %s",
                    (version,),
                )
                if cursor.fetchone():
                    continue
                statements = [part.strip() for part in path.read_text(encoding="utf-8").split(";")]
                for statement in statements:
                    if statement:
                        cursor.execute(statement)
                cursor.execute(
                    "INSERT INTO aster_schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            connection.commit()
            applied.append(version)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return applied


if __name__ == "__main__":
    done = apply_migrations()
    if done:
        print("Applied Aster migration(s): " + ", ".join(done))
    else:
        print("Aster database schema is already current.")
