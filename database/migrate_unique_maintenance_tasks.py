import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "database" / "jalflow.db"

db = sqlite3.connect(DATABASE)

try:
    db.execute("BEGIN")

    duplicates = db.execute("""
        SELECT incident_id, COUNT(*)
        FROM maintenance_tasks
        GROUP BY incident_id
        HAVING COUNT(*) > 1
    """).fetchall()

    if duplicates:
        raise ValueError(
            f"Duplicate maintenance tasks found: {duplicates}"
        )

    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_maintenance_tasks_incident_id
        ON maintenance_tasks(incident_id)
    """)

    db.commit()
    print("Unique maintenance-task index migration completed!")

except (sqlite3.Error, ValueError) as error:
    db.rollback()
    print("Migration failed:", error)

finally:
    db.close()
