import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "database" / "jalflow.db"

db = sqlite3.connect(DATABASE)

try:
    db.execute("BEGIN")

    db.execute("""
        CREATE TRIGGER IF NOT EXISTS validate_user_status_insert
        BEFORE INSERT ON users
        WHEN NEW.is_active NOT IN (0, 1)
        BEGIN
            SELECT RAISE(ABORT, 'is_active must be 0 or 1');
        END
    """)

    db.execute("""
        CREATE TRIGGER IF NOT EXISTS validate_user_status_update
        BEFORE UPDATE OF is_active ON users
        WHEN NEW.is_active NOT IN (0, 1)
        BEGIN
            SELECT RAISE(ABORT, 'is_active must be 0 or 1');
        END
    """)

    db.commit()
    print("Account status validation migration completed!")

except sqlite3.Error as error:
    db.rollback()
    print("Migration failed:", error)

finally:
    db.close()
