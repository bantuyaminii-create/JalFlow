import sqlite3
from pathlib import Path

# Find the project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Define database and schema paths
DATABASE_PATH = BASE_DIR / "database" / "jalflow.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

# Connect to SQLite
connection = sqlite3.connect(DATABASE_PATH)

# Enable foreign key support
connection.execute("PRAGMA foreign_keys = ON")

# Read the SQL schema
with open(SCHEMA_PATH, "r") as schema_file:
    schema = schema_file.read()

# Create all database tables
connection.executescript(schema)

# Save changes
connection.commit()

# Display created tables
tables = connection.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

print("JalFlow database created successfully!")
print("\nTables created:")

for table in tables:
    print("-", table[0])

connection.close()
