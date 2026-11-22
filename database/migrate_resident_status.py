import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "database" / "jalflow.db"

db = sqlite3.connect(DATABASE)

try:
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("BEGIN")

    # Create the updated resident profiles table
    db.execute("""
        CREATE TABLE resident_profiles_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            zone_id INTEGER NOT NULL,
            address TEXT NOT NULL,

            verification_status TEXT NOT NULL DEFAULT 'active'
                CHECK (
                    verification_status IN (
                        'active',
                        'pending_review',
                        'rejected'
                    )
                ),

            verified_by INTEGER,
            verified_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (zone_id) REFERENCES zones(id),
            FOREIGN KEY (verified_by) REFERENCES users(id)
        )
    """)

    # Preserve existing resident information
    # Old pending and verified accounts become active
    db.execute("""
        INSERT INTO resident_profiles_new (
            id,
            user_id,
            zone_id,
            address,
            verification_status,
            verified_by,
            verified_at,
            created_at
        )
        SELECT
            id,
            user_id,
            zone_id,
            address,
            CASE
                WHEN verification_status = 'rejected'
                    THEN 'rejected'
                ELSE 'active'
            END,
            verified_by,
            verified_at,
            created_at
        FROM resident_profiles
    """)

    # Replace the old table
    db.execute("DROP TABLE resident_profiles")
    db.execute("""
        ALTER TABLE resident_profiles_new
        RENAME TO resident_profiles
    """)

    db.commit()

    print("Resident status migration completed successfully!")

except sqlite3.Error as error:
    db.rollback()
    print("Migration failed:", error)

finally:
    db.execute("PRAGMA foreign_keys = ON")
    db.close()
