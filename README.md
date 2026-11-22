# JalFlow – Water Distribution Management System

#### Video Demo: https://youtu.be/1N7fBNIiXcE

#### Description:

JalFlow is a web-based Water Distribution Management System developed using Python, Flask, and SQLite. The project aims to improve the organization and monitoring of water distribution activities by providing a centralized platform for residents, managers, operators, and maintenance employees.

Water distribution involves several activities, including managing distribution zones, monitoring valves, planning supply schedules, handling resident complaints, and maintaining infrastructure. Managing these activities separately can make it difficult to track their progress. JalFlow brings these operations together in one application and provides different functionality according to each user's role.

## Features

### 1. Resident

Residents can register and log in to the application. They can browse available water distribution zones, submit complaints about water supply problems, and optionally associate a complaint with a particular valve. Residents can also view their submitted complaints and follow the progress of complaint verification, assignment, and maintenance.

### 2. Manager

The Manager has access to the main administrative functions. Managers can create, edit, and manage distribution zones and valves. They can review resident complaints, verify complaints, assign them to employees, and close them after resolution.

Managers can also create and manage water supply schedules, monitor cancelled schedules, and manage employee accounts. Employee management includes creating accounts and activating or deactivating employees. The Manager can also view activity logs to monitor important actions performed within the application.

### 3. Operator

Operators can view their assigned water supply schedules and update the progress of those schedules. The application records actual start and completion times. If a scheduled water supply operation cannot be completed successfully, operators can report the failure. Operators can also view operation logs.

### 4. Maintenance Employee

Maintenance employees can view their assigned maintenance tasks and update task progress. They can record inspection information and repair notes so that the progress of maintenance work can be tracked.

## Technologies Used

- Python – Application logic and backend development.
- Flask – Web application framework and routing.
- SQLite – Relational database for storing application information.
- HTML5 – Structure of web pages.
- CSS3 – Styling and layout.
- Bootstrap 5 – Responsive user interface components.
- Werkzeug – Password hashing and password verification.

## Project Files

- `app.py` contains the main Flask application. It defines application routes, database connections, session handling, authentication, role-based access, complaint management, schedules, employee management, maintenance tasks, and activity logging.

- `schema.sql` defines the SQLite database structure. It creates tables for users, zones, valves, schedules, operation logs, incidents, maintenance tasks, activity logs, and resident profiles.

- `database/init_db.py` initializes the database by reading and executing the SQL statements in `schema.sql`.

- `database/create_manager.py` creates the initial Manager account. It requests account details, validates the password, hashes it, and stores the account in the database.

- `database/migrate_resident_status.py` updates the resident profile table when upgrading an older database. It is not required for a fresh installation.

- `database/migrate_unique_maintenance_tasks.py` checks for duplicate maintenance tasks and creates a unique index to prevent multiple maintenance tasks from being assigned to the same complaint.

- `database/migrate_account_status_validation.py` adds SQLite triggers to validate account status values when user accounts are inserted or updated.

The migration scripts are intended for upgrading older database versions. They are not required when creating a fresh database using the current `schema.sql` file.

- `requirements.txt` lists the Python dependencies required to run the application.

- `static/css/style.css` contains the application's custom CSS styles.

- `templates/` contains the HTML templates rendered by Flask:
  - `index.html` provides the application landing page.
  - `login.html` and `register.html` provide authentication pages.
  - `dashboard.html` displays the dashboard.
  - `zones.html` and `zone_edit.html` support distribution zone management.
  - `valves.html` and `valve_edit.html` support valve management.
  - `complaint.html` provides the complaint submission page.
  - `my_complaints.html` displays resident complaints.
  - `manager_complaints.html` supports complaint review and management.
  - `manager_employees.html` supports employee account management.
  - `schedules.html` supports schedule management.
  - `cancelled_schedules.html` displays cancelled schedules.
  - `operator_schedules.html` displays operator schedules.
  - `operator_operation_logs.html` displays operator operation records.
  - `maintenance_tasks.html` displays and manages maintenance tasks.
  - `activity_logs.html` displays administrative activity records.

## Database Design

JalFlow uses SQLite to store information in related tables. The database separates information about users, distribution zones, valves, schedules, complaints, maintenance tasks, and operational activities.

Foreign key relationships help maintain consistency between related records. Database queries use parameterized statements where applicable. This helps protect the application against SQL injection.

## Security and Design Decisions

The application uses role-based access control so that users can access functionality appropriate to their roles. Passwords are stored as hashes rather than plain text. Flask sessions are used to maintain authenticated user information, and the application supports a configurable secret key through the `SECRET_KEY` environment variable.

SQLite was selected because it is lightweight and suitable for this academic project. Flask was selected because it provides a straightforward way to organize backend routes and connect them with HTML templates.

The application separates database initialization, database schema, backend logic, styling, and HTML templates to make the project easier to understand and maintain.

## Installation and Execution

1. Install Python 3.9 or later.
2. Install the required dependencies:

   `python -m pip install -r requirements.txt`

3. Configure a Flask secret key using the `SECRET_KEY` environment variable.
4. Initialize the database:

   `python database/init_db.py`

5. Create the initial Manager account:

   `python database/create_manager.py`

6. Start the application:

   `python -m flask --app app run`

7. Open `http://127.0.0.1:5000` in a web browser.

## Project Status

JalFlow is an academic software project developed as part of CS50x. The main application features for residents, managers, operators, and maintenance employees have been implemented.

The application has undergone extensive route-level and integration testing using temporary databases. Testing covers authentication, role-based access, input validation, complaint handling, zone and valve management, schedule operations, maintenance workflows, account status, and activity logging. These tests were performed without modifying the existing application database.

Further improvements and deployment are possible future extensions of the project.

## Acknowledgements

ChatGPT (OpenAI) was used as a programming assistance tool during development for explanations, debugging support, and suggestions related to Flask, SQLite, application functionality, and code organization. The suggestions were reviewed and adapted during development.
