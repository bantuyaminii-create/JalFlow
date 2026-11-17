# JalFlow – Water Distribution Management System

JalFlow is a web-based water distribution management system developed using Python, Flask, and SQLite.

It provides a platform for managing water distribution zones, valves, supply schedules, resident complaints, maintenance activities, and employee accounts.

## Features

### Resident
- Registration and login.
- Browse water distribution zones.
- Submit complaints with optional valve selection.
- Track complaint and maintenance progress.

### Manager
- Manage zones and valves.
- Review, verify, assign, and close complaints.
- Manage water supply schedules.
- Monitor cancelled schedules.
- Create and manage employee accounts.
- Activate and deactivate employees.
- View activity logs.

### Operator
- View assigned schedules.
- Update schedule progress.
- Record actual start and completion times.
- Report unsuccessful water supply.
- View operation logs.

### Maintenance
- View assigned maintenance tasks.
- Update task progress.
- Record inspection and repair notes.

## Technology Stack

- Python
- Flask
- SQLite
- HTML5
- CSS3
- Bootstrap 5

## Installation

1. Install Python 3.9 or later.
2. Clone this repository.
3. Open the project folder in a terminal.
4. Create a virtual environment using `python -m venv .venv`.
5. Activate the virtual environment.
6. Install dependencies using `python -m pip install -r requirements.txt`.
7. Configure the Flask `SECRET_KEY` environment variable.
8. Initialize the database using `python database/init_db.py`.
9. Create the first Manager account using `python database/create_manager.py`.
10. Start the application using `python -m flask --app app run`.

Open `http://127.0.0.1:5000` in your browser.

## Database

JalFlow uses SQLite. The database is created locally at `database/jalflow.db` using `schema.sql`.

Database files and backups are excluded from Git tracking.

## Security

- Passwords are stored as hashes.
- SQL queries use parameterized statements where applicable.
- Flask sessions use a configurable secret key.
- Role-based access controls protect management operations.
- Deactivated employees cannot log in.

Never publish passwords or secret keys.

## Project Status

JalFlow is an academic software project under development. Further improvements and testing are planned.
