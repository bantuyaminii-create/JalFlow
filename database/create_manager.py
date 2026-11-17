import sqlite3
from pathlib import Path
from getpass import getpass
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "database" / "jalflow.db"

name = input("Manager name: ").strip()
email = input("Manager email: ").strip().lower()
password = getpass("Create password: ")
confirmation = getpass("Confirm password: ")

if not name or not email:
    print("Name and email are required.")
    raise SystemExit

if len(password) < 8:
    print("Password must contain at least 8 characters.")
    raise SystemExit

if password != confirmation:
    print("Passwords do not match.")
    raise SystemExit

db = sqlite3.connect(DATABASE)

try:
    manager_exists = db.execute(
        "SELECT id FROM users WHERE role = 'manager'"
    ).fetchone()

    if manager_exists:
        print("A manager account already exists.")
        raise SystemExit

    email_exists = db.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if email_exists:
        print("This email is already registered.")
        raise SystemExit

    db.execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, 'manager')
        """,
        (name, email, generate_password_hash(password))
    )

    db.commit()
    print("Manager account created successfully!")

except sqlite3.Error as error:
    db.rollback()
    print("Database error:", error)

finally:
    db.close()
