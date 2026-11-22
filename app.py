# AI Assistance Acknowledgement:
# ChatGPT (OpenAI) was used during development for programming explanations,
# debugging assistance, and suggestions involving Flask, SQLite, validation,
# and application functionality. Suggestions were reviewed and adapted
# during development.

import os
import re
import sqlite3
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

# Create Flask application
app = Flask(__name__)

# Session security
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)

# Database location
BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database" / "jalflow.db"


# Connect to database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


# Close database connection
@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)

    if db is not None:
        db.close()

# Block deactivated employees from continuing existing sessions.
@app.before_request
def enforce_active_employee_accounts():

    user_id = session.get("user_id")

    if user_id is None:
        return

    user = get_db().execute(
        """
        SELECT role, is_active
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if user is None:
        session.clear()
        return redirect("/login")

    if user["role"] in ("operator", "maintenance") and user["is_active"] == 0:
        session.clear()
        flash("Your employee account is inactive. Please contact the Manager.")
        return redirect("/login")


# Record important actions in JalFlow's audit history.
def log_activity(action, entity_type, entity_id=None, details=None):

    db = get_db()

    actor_user_id = session.get("user_id")

    db.execute(
        """
        INSERT INTO activity_logs (
            actor_user_id,
            action,
            entity_type,
            entity_id,
            details
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            actor_user_id,
            action,
            entity_type,
            entity_id,
            details
        )
    )


# Home page
@app.route("/")
def index():
    return render_template("index.html")


# Registration page
@app.route("/register", methods=["GET", "POST"])
def register():

    db = get_db()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")
        # Public registration is restricted to Residents
        role = "resident"

        # Validate required fields
        if not name or not email or not password:
            flash("Please complete all required fields.")
            return redirect("/register")

        # Check password confirmation
        if password != confirmation:
            flash("Passwords do not match.")
            return redirect("/register")

        # Check password length
        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect("/register")

        # Check whether email already exists
        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            flash("An account with this email already exists.")
            return redirect("/register")

        # Resident-specific information
        zone_id = None
        address = None

        if role == "resident":

            zone_id = request.form.get("zone_id", "").strip()
            address = request.form.get("address", "").strip()

            if not zone_id or not address:
                flash("Please select your zone and enter your address.")
                return redirect("/register")

            try:
                zone_id = int(zone_id)
            except ValueError:
                flash("Invalid zone selection.")
                return redirect("/register")

            zone = db.execute(
                "SELECT id FROM zones WHERE id = ?",
                (zone_id,)
            ).fetchone()

            if zone is None:
                flash("Please select a valid water distribution zone.")
                return redirect("/register")

        # Create password hash
        password_hash = generate_password_hash(password)

        try:
            # Create user account
            cursor = db.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, password_hash, role)
            )

            # Create resident profile if the user is a resident
            if role == "resident":

                user_id = cursor.lastrowid

                db.execute(
                    """
                    INSERT INTO resident_profiles
                    (user_id, zone_id, address)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, zone_id, address)
                )

            db.commit()

        except sqlite3.IntegrityError:
            db.rollback()
            flash("Registration could not be completed.")
            return redirect("/register")

        flash("Registration successful! Please log in.")
        return redirect("/login")

    # Load zones for the registration dropdown
    zones = db.execute(
        "SELECT id, name FROM zones ORDER BY name"
    ).fetchall()

    return render_template("register.html", zones=zones)

# Login page
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        session.clear()

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user is None or not check_password_hash(
            user["password_hash"], password
        ):
            flash("Invalid email or password.")
            return redirect("/login")

        if user["is_active"] == 0:
            flash("Your account is inactive. Please contact the Manager.")
            return redirect("/login")

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        flash("Welcome back, " + user["name"] + "!")

        return redirect("/dashboard")

    return render_template("login.html")


# Dashboard
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    db = get_db()

    active_user = db.execute(
        "SELECT is_active FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if active_user is None or active_user["is_active"] != 1:
        session.clear()
        flash("Your account is inactive or unavailable. Please log in again.")
        return redirect("/login")

    resident_profile = None
    resident_schedules = []
    resident_zones = []
    selected_zone_id = None
    selected_zone_name = None

    if session.get("role") == "resident":

        resident_profile = db.execute(
            """
            SELECT
                resident_profiles.zone_id,
                resident_profiles.address,
                resident_profiles.verification_status,
                zones.name AS zone_name
            FROM resident_profiles
            JOIN zones
                ON resident_profiles.zone_id = zones.id
            WHERE resident_profiles.user_id = ?
            """,
            (session["user_id"],)
        ).fetchone()

        resident_zones = db.execute(
            "SELECT id, name FROM zones ORDER BY name"
        ).fetchall()

        if resident_profile:
            selected_zone_id = resident_profile["zone_id"]

            requested_zone = request.args.get("zone_id", "").strip()

            if requested_zone:
                try:
                    requested_zone_id = int(requested_zone)
                except ValueError:
                    requested_zone_id = None

                if requested_zone_id is not None:
                    selected_zone = db.execute(
                        "SELECT id, name FROM zones WHERE id = ?",
                        (requested_zone_id,)
                    ).fetchone()

                    if selected_zone:
                        selected_zone_id = selected_zone["id"]

            selected_zone_name = db.execute(
                "SELECT name FROM zones WHERE id = ?",
                (selected_zone_id,)
            ).fetchone()["name"]

            resident_schedules = db.execute(
                """
                SELECT
                    id,
                    scheduled_date,
                    start_time,
                    end_time,
                    status,
                    notes
                FROM schedules
                WHERE zone_id = ?
                ORDER BY scheduled_date, start_time
                """,
                (selected_zone_id,)
            ).fetchall()

    return render_template(
        "dashboard.html",
        resident_profile=resident_profile,
        resident_schedules=resident_schedules,
        resident_zones=resident_zones,
        selected_zone_id=selected_zone_id,
        selected_zone_name=selected_zone_name
    )

# Zone management
@app.route("/zones", methods=["GET", "POST"])
def zones():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can manage zones.")
        return redirect("/dashboard")

    db = get_db()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Zone name is required.")
            return redirect("/zones")

        if len(name) > 100:
            flash("Zone name cannot exceed 100 characters.")
            return redirect("/zones")

        if len(description) > 1000:
            flash("Zone description cannot exceed 1000 characters.")
            return redirect("/zones")

        duplicate = db.execute(
            """
            SELECT id FROM zones
            WHERE LOWER(name) = LOWER(?)
            """,
            (name,)
        ).fetchone()

        if duplicate:
            flash("A zone with this name already exists.")
            return redirect("/zones")

        db.execute(
            """
            INSERT INTO zones (name, description, created_by)
            VALUES (?, ?, ?)
            """,
            (name, description, session["user_id"])
        )

        db.commit()

        flash("New water distribution zone added successfully!")
        return redirect("/zones")

    all_zones = db.execute(
        """
        SELECT zones.*, users.name AS manager_name
        FROM zones
        JOIN users ON zones.created_by = users.id
        ORDER BY zones.created_at DESC
        """
    ).fetchall()

    return render_template("zones.html", zones=all_zones)

# Manager: Edit Water Distribution Zone
@app.route("/zones/<int:zone_id>/edit", methods=["GET", "POST"])
def edit_zone(zone_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can edit zones.")
        return redirect("/dashboard")

    db = get_db()

    zone = db.execute(
        "SELECT * FROM zones WHERE id = ?",
        (zone_id,)
    ).fetchone()

    if zone is None:
        flash("Zone not found.")
        return redirect("/zones")

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Zone name is required.")
            return redirect(f"/zones/{zone_id}/edit")

        if len(name) > 100:
            flash("Zone name cannot exceed 100 characters.")
            return redirect(f"/zones/{zone_id}/edit")

        if len(description) > 1000:
            flash("Zone description cannot exceed 1000 characters.")
            return redirect(f"/zones/{zone_id}/edit")

        duplicate = db.execute(
            """
            SELECT id FROM zones
            WHERE LOWER(name) = LOWER(?) AND id != ?
            """,
            (name, zone_id)
        ).fetchone()

        if duplicate:
            flash("A zone with this name already exists.")
            return redirect(f"/zones/{zone_id}/edit")

        db.execute(
            """
            UPDATE zones
            SET name = ?, description = ?
            WHERE id = ?
            """,
            (name, description, zone_id)
        )

        db.commit()

        flash("Zone updated successfully!")
        return redirect("/zones")

    return render_template("zone_edit.html", zone=zone)


# Manager: Valve Management
@app.route("/valves", methods=["GET", "POST"])
def valves():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can manage valves.")
        return redirect("/dashboard")

    db = get_db()

    if request.method == "POST":

        zone_id = request.form.get("zone_id", "").strip()
        valve_code = request.form.get("valve_code", "").strip()
        location = request.form.get("location", "").strip()
        valve_type = request.form.get("valve_type", "").strip()
        notes = request.form.get("notes", "").strip()

        if not zone_id.isdigit():
            flash("Please select a valid zone.")
            return redirect("/valves")

        zone = db.execute(
            "SELECT id FROM zones WHERE id = ?",
            (int(zone_id),)
        ).fetchone()

        if zone is None:
            flash("Selected zone does not exist.")
            return redirect("/valves")

        if not valve_code or len(valve_code) > 50:
            flash("Valve code is required and must not exceed 50 characters.")
            return redirect("/valves")

        if len(location) > 150 or len(valve_type) > 50 or len(notes) > 500:
            flash("Location, valve type, or notes exceed the allowed length.")
            return redirect("/valves")

        duplicate = db.execute(
            """
            SELECT id FROM valves
            WHERE zone_id = ? AND LOWER(valve_code) = LOWER(?)
            """,
            (int(zone_id), valve_code)
        ).fetchone()

        if duplicate:
            flash("This valve code already exists in the selected zone.")
            return redirect("/valves")

        try:
            cursor = db.execute(
                """
                INSERT INTO valves (
                    zone_id, valve_code, location, valve_type, notes
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(zone_id),
                    valve_code,
                    location,
                    valve_type,
                    notes
                )
            )

            log_activity(
                "valve_created",
                "valve",
                cursor.lastrowid,
                f"Created valve {valve_code} in zone ID {zone_id}."
            )

            db.commit()

            flash("Valve added successfully!")

        except sqlite3.IntegrityError:
            db.rollback()
            flash("Unable to add valve. Check the valve code and selected zone.")

        return redirect("/valves")

    all_zones = db.execute(
        "SELECT id, name FROM zones ORDER BY name"
    ).fetchall()

    all_valves = db.execute(
        """
        SELECT valves.*, zones.name AS zone_name
        FROM valves
        JOIN zones ON valves.zone_id = zones.id
        ORDER BY zones.name, valves.valve_code
        """
    ).fetchall()

    return render_template(
        "valves.html",
        zones=all_zones,
        valves=all_valves
    )


# Manager: Edit Valve Details
@app.route("/valves/<int:valve_id>/edit", methods=["GET", "POST"])
def edit_valve(valve_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can edit valves.")
        return redirect("/dashboard")

    db = get_db()

    valve = db.execute(
        "SELECT * FROM valves WHERE id = ?",
        (valve_id,)
    ).fetchone()

    if valve is None:
        flash("Valve not found.")
        return redirect("/valves")

    if request.method == "POST":

        zone_id = request.form.get("zone_id", "").strip()
        valve_code = request.form.get("valve_code", "").strip()
        location = request.form.get("location", "").strip()
        valve_type = request.form.get("valve_type", "").strip()
        status = request.form.get("status", "").strip()
        notes = request.form.get("notes", "").strip()

        allowed_statuses = ("active", "inactive", "maintenance")

        if not zone_id.isdigit():
            flash("Please select a valid zone.")
            return redirect(f"/valves/{valve_id}/edit")

        zone = db.execute(
            "SELECT id FROM zones WHERE id = ?",
            (int(zone_id),)
        ).fetchone()

        if zone is None:
            flash("Selected zone does not exist.")
            return redirect(f"/valves/{valve_id}/edit")

        if not valve_code or len(valve_code) > 50:
            flash("Valve code is required and must not exceed 50 characters.")
            return redirect(f"/valves/{valve_id}/edit")

        if status not in allowed_statuses:
            flash("Please select a valid valve status.")
            return redirect(f"/valves/{valve_id}/edit")

        if len(location) > 150 or len(valve_type) > 50 or len(notes) > 500:
            flash("Location, valve type, or notes exceed the allowed length.")
            return redirect(f"/valves/{valve_id}/edit")

        duplicate = db.execute(
            """
            SELECT id FROM valves
            WHERE zone_id = ?
              AND LOWER(valve_code) = LOWER(?)
              AND id != ?
            """,
            (int(zone_id), valve_code, valve_id)
        ).fetchone()

        if duplicate:
            flash("This valve code already exists in the selected zone.")
            return redirect(f"/valves/{valve_id}/edit")

        # Preserve historical records by preventing referenced valves
        # from being moved to another zone.
        if int(zone_id) != valve["zone_id"]:
            has_history = db.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM incidents WHERE valve_id = ?
                    UNION ALL
                    SELECT 1 FROM operation_logs WHERE valve_id = ?
                ) AS has_history
                """,
                (valve_id, valve_id)
            ).fetchone()["has_history"]

            if has_history:
                flash(
                    "This valve cannot be moved because it has "
                    "existing complaint or operation history."
                )
                return redirect(f"/valves/{valve_id}/edit")

        try:
            db.execute(
                """
                UPDATE valves
                SET zone_id = ?,
                    valve_code = ?,
                    location = ?,
                    valve_type = ?,
                    status = ?,
                    notes = ?
                WHERE id = ?
                """,
                (
                    int(zone_id),
                    valve_code,
                    location,
                    valve_type,
                    status,
                    notes,
                    valve_id
                )
            )

            log_activity(
                "valve_updated",
                "valve",
                valve_id,
                f"Updated valve {valve_code}; status: {status}."
            )

            db.commit()

            flash("Valve updated successfully!")

        except sqlite3.IntegrityError:
            db.rollback()
            flash("Unable to update valve. Please check the entered details.")

        return redirect("/valves")

    all_zones = db.execute(
        "SELECT id, name FROM zones ORDER BY name"
    ).fetchall()

    return render_template(
        "valve_edit.html",
        valve=valve,
        zones=all_zones
    )


# Resident and Operator: Report an Incident
@app.route("/complaints/new", methods=["GET", "POST"])
def new_complaint():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    role = session.get("role")

    if role not in ("resident", "operator"):
        flash("Only residents and operators can report incidents.")
        return redirect("/dashboard")

    db = get_db()

    zones = db.execute(
        "SELECT id, name FROM zones ORDER BY name"
    ).fetchall()

    valves = db.execute(
        """
        SELECT id, zone_id, valve_code, location
        FROM valves
        ORDER BY valve_code
        """
    ).fetchall()

    resident = None

    if role == "resident":
        resident = db.execute(
            """
            SELECT zone_id, verification_status
            FROM resident_profiles
            WHERE user_id = ?
            """,
            (session["user_id"],)
        ).fetchone()

        if resident is None:
            flash("Resident profile not found. Please contact support.")
            return redirect("/dashboard")

    selected_zone_id = None

    if role == "resident":
        selected_zone_id = resident["zone_id"]

        zones = db.execute(
            "SELECT id, name FROM zones WHERE id = ?",
            (selected_zone_id,)
        ).fetchall()

    if request.method == "POST":

        incident_type = request.form.get("incident_type", "").strip()
        description = request.form.get("description", "").strip()
        severity = request.form.get("severity", "medium")
        selected_zone = request.form.get("zone_id", "").strip()
        selected_valve = request.form.get("valve_id", "").strip()

        allowed_types = (
            "Water Shortage",
            "Water Leakage",
            "Water Quality",
            "Supply Disruption",
            "Other"
        )

        allowed_severity = ("low", "medium", "high", "critical")

        if incident_type not in allowed_types:
            flash("Please select a valid complaint type.")
            return redirect("/complaints/new")

        if not description:
            flash("Please describe the water-related problem.")
            return redirect("/complaints/new")

        if severity not in allowed_severity:
            flash("Invalid complaint priority.")
            return redirect("/complaints/new")

        try:
            zone_id = int(selected_zone)
        except ValueError:
            flash("Please select a valid water distribution zone.")
            return redirect("/complaints/new")

        zone = db.execute(
            "SELECT id FROM zones WHERE id = ?",
            (zone_id,)
        ).fetchone()

        if zone is None:
            flash("Please select a valid water distribution zone.")
            return redirect("/complaints/new")

        if role == "resident" and zone_id != resident["zone_id"]:
            flash("You can report incidents only for your registered zone.")
            return redirect("/complaints/new")

        valve_id = None

        if selected_valve:
            try:
                valve_id = int(selected_valve)
            except ValueError:
                flash("Please select a valid valve.")
                return redirect("/complaints/new")

            valve = db.execute(
                """
                SELECT id
                FROM valves
                WHERE id = ? AND zone_id = ?
                """,
                (valve_id, zone_id)
            ).fetchone()

            if valve is None:
                flash("The selected valve does not belong to this zone.")
                return redirect("/complaints/new")

        cursor = db.execute(
            """
            INSERT INTO incidents (
                zone_id,
                valve_id,
                reported_by,
                incident_type,
                description,
                severity
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                zone_id,
                valve_id,
                session["user_id"],
                incident_type,
                description,
                severity
            )
        )

        incident_id = cursor.lastrowid

        log_details = f"{role.title()} reported a water-related incident."

        if valve_id is not None:
            log_details += f" Related valve ID: {valve_id}."

        db.execute(
            """
            INSERT INTO activity_logs (
                actor_user_id,
                action,
                entity_type,
                entity_id,
                details
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                "complaint_submitted",
                "incident",
                incident_id,
                log_details
            )
        )

        db.commit()

        flash("Your incident has been reported successfully!")
        return redirect("/dashboard")

    return render_template(
        "complaint.html",
        zones=zones,
        valves=valves,
        role=role,
        selected_zone_id=selected_zone_id
    )

# Resident: View My Complaints
@app.route("/complaints")
def my_complaints():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "resident":
        flash("This page is only for residents.")
        return redirect("/dashboard")

    db = get_db()

    complaints = db.execute(
        """
        SELECT
            incidents.id,
            incidents.incident_type,
            incidents.description,
            incidents.severity,
            incidents.status,
            incidents.created_at,
            zones.name AS zone_name,
            maintenance_tasks.status AS maintenance_status,
            maintenance_tasks.inspection_notes,
            maintenance_tasks.repair_notes,
            maintenance_tasks.completion_notes
        FROM incidents
        JOIN zones
            ON incidents.zone_id = zones.id
        LEFT JOIN maintenance_tasks
            ON incidents.id = maintenance_tasks.incident_id
        WHERE incidents.reported_by = ?
        ORDER BY incidents.created_at DESC
        LIMIT 100
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "my_complaints.html",
        complaints=complaints
    )

# Manager: View All Resident Complaints
@app.route("/manager/complaints")
def manager_complaints():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can access resident complaints.")
        return redirect("/dashboard")

    db = get_db()

    complaints = db.execute(
        """
        SELECT
            incidents.id,
            incidents.incident_type,
            incidents.description,
            incidents.severity,
            incidents.status,
            incidents.created_at,
            zones.name AS zone_name,
            valves.valve_code AS valve_code,
            valves.location AS valve_location,
            valves.valve_type AS valve_type,
            users.name AS resident_name,
            users.email AS resident_email,
            users.role AS reporter_role
        FROM incidents
        JOIN zones
            ON incidents.zone_id = zones.id
        LEFT JOIN valves
            ON incidents.valve_id = valves.id
        JOIN users
            ON incidents.reported_by = users.id
        ORDER BY incidents.created_at DESC
        """
    ).fetchall()
    maintenance_staff = db.execute(
    """
    SELECT id, name
    FROM users
    WHERE role = 'maintenance'
      AND is_active = 1
    ORDER BY name
    """
).fetchall()

    return render_template(
        "manager_complaints.html",
        complaints=complaints,
        maintenance_staff=maintenance_staff
)

# Maintenance: View Assigned Tasks
@app.route("/maintenance/tasks")
def maintenance_tasks():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "maintenance":
        flash("Only maintenance staff can access these tasks.")
        return redirect("/dashboard")

    db = get_db()

    active_user = db.execute(
        """
        SELECT is_active
        FROM users
        WHERE id = ? AND role = 'maintenance'
        """,
        (session["user_id"],)
    ).fetchone()

    if active_user is None or not active_user["is_active"]:
        session.clear()
        flash("Your account is inactive. Please contact the manager.")
        return redirect("/login")

    tasks = db.execute(
        """
        SELECT
            maintenance_tasks.id AS task_id,
            maintenance_tasks.status AS task_status,
            maintenance_tasks.inspection_notes,
            maintenance_tasks.repair_notes,
            maintenance_tasks.completion_notes,
            maintenance_tasks.assigned_at,
            incidents.id AS complaint_id,
            incidents.incident_type,
            incidents.description,
            incidents.severity,
            zones.name AS zone_name,
            valves.valve_code AS valve_code,
            valves.location AS valve_location,
            valves.valve_type AS valve_type,
            users.name AS resident_name
        FROM maintenance_tasks
        JOIN incidents
            ON maintenance_tasks.incident_id = incidents.id
        JOIN zones
            ON incidents.zone_id = zones.id
        LEFT JOIN valves
            ON incidents.valve_id = valves.id
        JOIN users
            ON incidents.reported_by = users.id
        WHERE maintenance_tasks.assigned_to = ?
        ORDER BY maintenance_tasks.assigned_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "maintenance_tasks.html",
        tasks=tasks
    )
# Maintenance: Update Repair Progress
@app.route("/maintenance/tasks/<int:task_id>/update", methods=["POST"])
def update_maintenance_task(task_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "maintenance":
        flash("Only maintenance staff can update tasks.")
        return redirect("/dashboard")

    db = get_db()

    active_user = db.execute(
        """
        SELECT is_active
        FROM users
        WHERE id = ? AND role = 'maintenance'
        """,
        (session["user_id"],)
    ).fetchone()

    if active_user is None or not active_user["is_active"]:
        session.clear()
        flash("Your account is inactive. Please contact the manager.")
        return redirect("/login")

    new_status = request.form.get("status", "").strip()
    notes = request.form.get("notes", "").strip()

    if len(notes) > 1000:
        flash("Notes cannot exceed 1000 characters.")
        return redirect("/maintenance/tasks")

    allowed_transitions = {
        "assigned": "inspecting",
        "inspecting": "repairing",
        "repairing": "completed"
    }

    task = db.execute(
        """
        SELECT id, status
        FROM maintenance_tasks
        WHERE id = ? AND assigned_to = ?
        """,
        (task_id, session["user_id"])
    ).fetchone()

    if task is None:
        flash("Task not found or not assigned to you.")
        return redirect("/maintenance/tasks")

    if allowed_transitions.get(task["status"]) != new_status:
        flash("Invalid task status update.")
        return redirect("/maintenance/tasks")

    if new_status == "inspecting":
        if not notes:
            flash("Please enter inspection notes.")
            return redirect("/maintenance/tasks")

        db.execute(
            """
            UPDATE maintenance_tasks
            SET status = ?, inspection_notes = ?
            WHERE id = ?
            """,
            (new_status, notes, task_id)
        )

    elif new_status == "repairing":
        if not notes:
            flash("Please enter repair notes.")
            return redirect("/maintenance/tasks")

        db.execute(
            """
            UPDATE maintenance_tasks
            SET status = ?, repair_notes = ?
            WHERE id = ?
            """,
            (new_status, notes, task_id)
        )

    elif new_status == "completed":
        if not notes:
            flash("Please enter completion notes.")
            return redirect("/maintenance/tasks")

        db.execute(
            """
            UPDATE maintenance_tasks
            SET status = ?,
                completion_notes = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, notes, task_id)
        )

        db.execute(
            """
            UPDATE incidents
            SET status = 'resolved'
            WHERE id = (
                SELECT incident_id
                FROM maintenance_tasks
                WHERE id = ?
            )
            """,
            (task_id,)
        )

    log_activity(
        "maintenance_task_status_changed",
        "maintenance_task",
        task_id,
        f"Status changed from {task['status']} to {new_status}."
    )

    db.commit()

    flash("Maintenance task updated successfully!")
    return redirect("/maintenance/tasks")

# Manager: Verify a Resident Complaint
@app.route("/manager/complaints/<int:complaint_id>/verify", methods=["POST"])
def verify_complaint(complaint_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can verify complaints.")
        return redirect("/dashboard")

    db = get_db()

    complaint = db.execute(
        """
        SELECT id, status
        FROM incidents
        WHERE id = ?
        """,
        (complaint_id,)
    ).fetchone()

    if complaint is None:
        flash("Complaint not found.")

    elif complaint["status"] != "reported":
        flash("This complaint cannot be verified.")

    else:
        cursor = db.execute(
            """
            UPDATE incidents
            SET status = 'verified'
            WHERE id = ?
              AND status = 'reported'
            """,
            (complaint_id,)
        )

        if cursor.rowcount != 1:
            db.rollback()
            flash("Complaint could not be verified. Please refresh and try again.")
        else:
            log_activity(
                "complaint_verified",
                "incident",
                complaint_id,
                "Manager verified resident complaint."
            )

            db.commit()

            flash("Complaint verified successfully!")

    return redirect("/manager/complaints")

# Manager: Assign a Verified Complaint to Maintenance Staff
@app.route("/manager/complaints/<int:complaint_id>/assign", methods=["POST"])
def assign_complaint(complaint_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can assign maintenance tasks.")
        return redirect("/dashboard")

    db = get_db()

    maintenance_id = request.form.get("maintenance_id", "").strip()

    try:
        maintenance_id = int(maintenance_id)
    except ValueError:
        flash("Please select a valid maintenance team member.")
        return redirect("/manager/complaints")

    maintenance_user = db.execute(
        """
        SELECT id FROM users
        WHERE id = ?
          AND role = 'maintenance'
          AND is_active = 1
        """,
        (maintenance_id,)
    ).fetchone()

    if maintenance_user is None:
        flash("Invalid maintenance team member.")
        return redirect("/manager/complaints")

    complaint = db.execute(
        """
        SELECT id, status
        FROM incidents
        WHERE id = ?
        """,
        (complaint_id,)
    ).fetchone()

    if complaint is None:
        flash("Complaint not found.")

    elif complaint["status"] != "verified":
        flash("Only verified complaints can be assigned.")

    else:
        existing_task = db.execute(
            """
            SELECT id FROM maintenance_tasks
            WHERE incident_id = ?
            """,
            (complaint_id,)
        ).fetchone()

        if existing_task:
            flash("A maintenance task already exists for this complaint.")

        else:
            db.execute(
                """
                INSERT INTO maintenance_tasks
                (incident_id, assigned_to, assigned_by)
                VALUES (?, ?, ?)
                """,
                (complaint_id, maintenance_id, session["user_id"])
            )

            db.execute(
                """
                UPDATE incidents
                SET status = 'assigned'
                WHERE id = ?
                """,
                (complaint_id,)
            )

            log_activity(
                "complaint_assigned",
                "incident",
                complaint_id,
                f"Assigned to maintenance staff user ID {maintenance_id}."
            )

            db.commit()

            flash("Complaint assigned to maintenance staff successfully!")

    return redirect("/manager/complaints")
# Manager: Close a Resolved Complaint
@app.route("/manager/complaints/<int:complaint_id>/close", methods=["POST"])
def close_complaint(complaint_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can close complaints.")
        return redirect("/dashboard")

    db = get_db()

    complaint = db.execute(
        """
        SELECT id, status
        FROM incidents
        WHERE id = ?
        """,
        (complaint_id,)
    ).fetchone()

    if complaint is None:
        flash("Complaint not found.")

    elif complaint["status"] != "resolved":
        flash("Only resolved complaints can be closed.")

    else:
        cursor = db.execute(
            """
            UPDATE incidents
            SET status = 'closed',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'resolved'
            """,
            (complaint_id,)
        )

        if cursor.rowcount != 1:
            db.rollback()
            flash("Complaint could not be closed. Please refresh and try again.")
        else:
            log_activity(
                "complaint_closed",
                "incident",
                complaint_id,
                "Manager closed the resolved complaint."
            )

            db.commit()

            flash("Complaint closed successfully!")

    return redirect("/manager/complaints")


# Manager: View Activity Logs
@app.route("/manager/activity-logs")
def manager_activity_logs():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can view activity logs.")
        return redirect("/dashboard")

    db = get_db()

    selected_employee = request.args.get("employee_id", "").strip()
    selected_action = request.args.get("action", "").strip()
    selected_date = request.args.get("date", "").strip()

    employees = db.execute(
        """
        SELECT id, name, role
        FROM users
        WHERE role IN ('operator', 'maintenance')
        ORDER BY name
        """
    ).fetchall()

    actions = db.execute(
        """
        SELECT DISTINCT action
        FROM activity_logs
        ORDER BY action
        """
    ).fetchall()

    conditions = []
    parameters = []

    if selected_employee:
        try:
            employee_id = int(selected_employee)
        except ValueError:
            employee_id = None

        if employee_id is None or not any(
            employee["id"] == employee_id for employee in employees
        ):
            flash("Please select a valid employee.")
            selected_employee = ""
        else:
            conditions.append("activity_logs.actor_user_id = ?")
            parameters.append(employee_id)

    if selected_action:
        valid_actions = [row["action"] for row in actions]

        if selected_action not in valid_actions:
            flash("Please select a valid activity type.")
            selected_action = ""
        else:
            conditions.append("activity_logs.action = ?")
            parameters.append(selected_action)

    if selected_date:
        try:
            parsed_date = datetime.strptime(selected_date, "%Y-%m-%d")

            if parsed_date.strftime("%Y-%m-%d") != selected_date:
                raise ValueError

        except ValueError:
            flash("Please select a valid date.")
            selected_date = ""
        else:
            conditions.append("date(activity_logs.created_at) = ?")
            parameters.append(selected_date)

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    logs = db.execute(
        f"""
        SELECT
            activity_logs.id,
            activity_logs.action,
            activity_logs.entity_type,
            activity_logs.entity_id,
            activity_logs.details,
            activity_logs.created_at,
            users.name AS actor_name
        FROM activity_logs
        LEFT JOIN users
            ON activity_logs.actor_user_id = users.id
        {where_clause}
        ORDER BY activity_logs.id DESC
        LIMIT 100
        """,
        parameters
    ).fetchall()

    return render_template(
        "activity_logs.html",
        logs=logs,
        employees=employees,
        actions=actions,
        selected_employee=selected_employee,
        selected_action=selected_action,
        selected_date=selected_date
    )


# Manager: Employee Management
@app.route("/manager/employees", methods=["GET", "POST"])
def manager_employees():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can manage employee accounts.")
        return redirect("/dashboard")

    db = get_db()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")

        if not name or not email or not password:
            flash("Please complete all required fields.")
            return redirect(url_for("manager_employees"))

        if len(name) < 2 or len(name) > 100:
            flash("Employee name must be between 2 and 100 characters.")
            return redirect(url_for("manager_employees"))

        if (
            len(email) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        ):
            flash("Please enter a valid email address (maximum 254 characters).")
            return redirect(url_for("manager_employees"))

        if len(password) > 128:
            flash("Password cannot exceed 128 characters.")
            return redirect(url_for("manager_employees"))

        if role not in ("operator", "maintenance"):
            flash("Please select a valid employee role.")
            return redirect(url_for("manager_employees"))

        if password != confirmation:
            flash("Passwords do not match.")
            return redirect(url_for("manager_employees"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for("manager_employees"))

        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            flash("An account with this email already exists.")
            return redirect(url_for("manager_employees"))

        password_hash = generate_password_hash(password)

        try:
            cursor = db.execute(
                """
                INSERT INTO users
                    (name, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (name, email, password_hash, role)
            )

            employee_id = cursor.lastrowid

            log_activity(
                "employee_created",
                "user",
                employee_id,
                f"Created {role} account for {name}"
            )

            db.commit()

        except sqlite3.IntegrityError:
            db.rollback()
            flash("Employee account could not be created.")
            return redirect(url_for("manager_employees"))

        flash("Employee account created successfully!")
        return redirect(url_for("manager_employees"))

    employees = db.execute(
        """
        SELECT id, name, email, role, is_active, created_at
        FROM users
        WHERE role IN ('operator', 'maintenance')
        ORDER BY role, name
        """
    ).fetchall()

    return render_template(
        "manager_employees.html",
        employees=employees
    )


# Manager: Activate or Deactivate Employee Accounts
@app.route("/manager/employees/<int:employee_id>/status", methods=["POST"])
def manager_employee_status(employee_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can change employee account status.")
        return redirect("/dashboard")

    action = request.form.get("action", "").strip()

    if action not in ("activate", "deactivate"):
        flash("Invalid employee status action.")
        return redirect(url_for("manager_employees"))

    db = get_db()

    employee = db.execute(
        """
        SELECT id, name, role, is_active
        FROM users
        WHERE id = ?
          AND role IN ('operator', 'maintenance')
        """,
        (employee_id,)
    ).fetchone()

    if employee is None:
        flash("Employee account not found.")
        return redirect(url_for("manager_employees"))

    new_status = 1 if action == "activate" else 0

    if employee["is_active"] == new_status:
        flash("Employee account already has that status.")
        return redirect(url_for("manager_employees"))

    cursor = db.execute(
        """
        UPDATE users
        SET is_active = ?
        WHERE id = ?
          AND role IN ('operator', 'maintenance')
          AND is_active = ?
        """,
        (new_status, employee_id, employee["is_active"])
    )

    if cursor.rowcount != 1:
        db.rollback()
        flash("Employee status could not be updated. Please refresh and try again.")
        return redirect(url_for("manager_employees"))

    log_activity(
        "employee_" + action + "d" if action == "activate"
        else "employee_deactivated",
        "user",
        employee_id,
        f"{action.title()}d account for {employee['name']}"
    )

    db.commit()

    flash(
        "Employee account activated successfully!"
        if new_status == 1
        else "Employee account deactivated successfully!"
    )

    return redirect(url_for("manager_employees"))


# Manager: Monitor Cancelled Schedules
@app.route("/manager/cancelled-schedules")
def manager_cancelled_schedules():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can access cancelled schedules.")
        return redirect("/dashboard")

    db = get_db()

    cancelled_schedules = db.execute(
        """
        SELECT
            schedules.id,
            zones.name AS zone_name,
            users.name AS operator_name,
            schedules.scheduled_date,
            schedules.start_time,
            schedules.end_time,
            operation_logs.notes AS cancellation_reason,
            operation_logs.recorded_at AS cancelled_at
        FROM schedules
        LEFT JOIN zones
            ON schedules.zone_id = zones.id
        LEFT JOIN users
            ON schedules.assigned_operator_id = users.id
        LEFT JOIN operation_logs
            ON operation_logs.id = (
                SELECT latest_log.id
                FROM operation_logs AS latest_log
                WHERE latest_log.schedule_id = schedules.id
                    AND latest_log.action = 'observation'
                    AND latest_log.notes LIKE 'Unable to complete scheduled supply:%'
                ORDER BY latest_log.recorded_at DESC, latest_log.id DESC
                LIMIT 1
            )
        WHERE schedules.status = 'cancelled'
        ORDER BY operation_logs.recorded_at DESC, schedules.id DESC
        """
    ).fetchall()

    return render_template(
        "cancelled_schedules.html",
        cancelled_schedules=cancelled_schedules
    )


# Manager: Create Water Supply Schedule
@app.route("/schedules", methods=["GET", "POST"])
def manage_schedules():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "manager":
        flash("Only managers can create schedules.")
        return redirect("/dashboard")

    db = get_db()

    if request.method == "POST":

        zone_id = request.form.get("zone_id", "").strip()
        operator_id = request.form.get("operator_id", "").strip()
        scheduled_date = request.form.get("scheduled_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        notes = request.form.get("notes", "").strip()

        if len(notes) > 1000:
            flash("Schedule instructions cannot exceed 1000 characters.")
            return redirect("/schedules")

        if not all([zone_id, operator_id, scheduled_date,
                    start_time, end_time]):
            flash("Please complete all required fields.")
            return redirect("/schedules")

        try:
            zone_id = int(zone_id)
            operator_id = int(operator_id)
        except ValueError:
            flash("Invalid zone or operator selection.")
            return redirect("/schedules")

        zone = db.execute(
            "SELECT id FROM zones WHERE id = ?",
            (zone_id,)
        ).fetchone()

        operator = db.execute(
            """
            SELECT id FROM users
            WHERE id = ?
              AND role = 'operator'
              AND is_active = 1
            """,
            (operator_id,)
        ).fetchone()

        if zone is None or operator is None:
            flash("Please select a valid zone and operator.")
            return redirect("/schedules")

        try:
            schedule_date = date.fromisoformat(scheduled_date)
        except ValueError:
            flash("Please enter a valid schedule date.")
            return redirect("/schedules")

        if schedule_date < date.today():
            flash("You cannot create a schedule for a past date.")
            return redirect("/schedules")

        try:
            parsed_start_time = time.fromisoformat(start_time)
            parsed_end_time = time.fromisoformat(end_time)
        except ValueError:
            flash("Please enter valid start and end times.")
            return redirect("/schedules")

        if (
            len(start_time) != 5
            or len(end_time) != 5
            or parsed_start_time.isoformat(timespec="minutes") != start_time
            or parsed_end_time.isoformat(timespec="minutes") != end_time
        ):
            flash("Please enter times in HH:MM format.")
            return redirect("/schedules")

        if parsed_end_time <= parsed_start_time:
            flash("End time must be later than start time.")
            return redirect("/schedules")

        overlapping_schedule = db.execute(
            """
            SELECT id
            FROM schedules
            WHERE assigned_operator_id = ?
              AND scheduled_date = ?
              AND status IN ('planned', 'in_progress')
              AND start_time < ?
              AND end_time > ?
            LIMIT 1
            """,
            (
                operator_id,
                scheduled_date,
                end_time,
                start_time
            )
        ).fetchone()

        if overlapping_schedule:
            flash(
                "This operator already has a schedule "
                "during the selected time period."
            )
            return redirect("/schedules")

        cursor = db.execute(
            """
            INSERT INTO schedules (
                zone_id,
                assigned_operator_id,
                scheduled_date,
                start_time,
                end_time,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                zone_id,
                operator_id,
                scheduled_date,
                start_time,
                end_time,
                notes
            )
        )

        schedule_id = cursor.lastrowid

        log_activity(
            "schedule_created",
            "schedule",
            schedule_id,
            f"Created schedule for zone {zone_id}, "
            f"assigned to operator {operator_id}. "
            f"Date: {scheduled_date}, "
            f"Time: {start_time} - {end_time}"
        )

        db.commit()

        flash("Water supply schedule created successfully!")
        return redirect("/schedules")

    zones = db.execute(
        "SELECT id, name FROM zones ORDER BY name"
    ).fetchall()

    operators = db.execute(
        """
        SELECT id, name
        FROM users
        WHERE role = 'operator'
          AND is_active = 1
        ORDER BY name
        """
    ).fetchall()

    schedules = db.execute(
        """
        SELECT
            schedules.id,
            schedules.scheduled_date,
            schedules.start_time,
            schedules.end_time,
            schedules.status,
            schedules.notes,
            schedules.actual_start_at,
            schedules.actual_completed_at,
            zones.name AS zone_name,
            users.name AS operator_name
        FROM schedules
        JOIN zones
            ON schedules.zone_id = zones.id
        JOIN users
            ON schedules.assigned_operator_id = users.id
        ORDER BY schedules.scheduled_date DESC,
                 schedules.start_time ASC
        """
    ).fetchall()

    return render_template(
        "schedules.html",
        zones=zones,
        operators=operators,
        schedules=schedules
    )


# Operator: View Assigned Water Supply Schedules
@app.route("/operator/schedules")
def operator_schedules():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "operator":
        flash("Only field operators can access this page.")
        return redirect("/dashboard")

    db = get_db()

    schedules = db.execute(
        """
        SELECT
            schedules.id,
            schedules.scheduled_date,
            schedules.start_time,
            schedules.end_time,
            schedules.status,
            schedules.notes,
            schedules.actual_start_at,
            schedules.actual_completed_at,
            zones.name AS zone_name
        FROM schedules
        JOIN zones
            ON schedules.zone_id = zones.id
        WHERE schedules.assigned_operator_id = ?
        ORDER BY schedules.scheduled_date ASC,
                 schedules.start_time ASC
        """,
        (session["user_id"],)
    ).fetchall()

    timezone = ZoneInfo("Asia/Kolkata")
    now = datetime.now(timezone)

    schedule_items = []

    for schedule in schedules:
        item = dict(schedule)

        scheduled_start = datetime.combine(
            date.fromisoformat(str(schedule["scheduled_date"])),
            time.fromisoformat(str(schedule["start_time"])),
            tzinfo=timezone
        )

        scheduled_end = datetime.combine(
            date.fromisoformat(str(schedule["scheduled_date"])),
            time.fromisoformat(str(schedule["end_time"])),
            tzinfo=timezone
        )

        item["can_start"] = (
            schedule["status"] == "planned"
            and scheduled_start <= now <= scheduled_end
        )

        item["schedule_not_started_yet"] = (
            schedule["status"] == "planned"
            and now < scheduled_start
        )

        item["can_report_failure"] = (
            schedule["status"] in ("planned", "in_progress")
            and now > scheduled_end
        )

        schedule_items.append(item)

    return render_template(
        "operator_schedules.html",
        schedules=schedule_items
    )


# Operator: Update Water Supply Schedule Status
@app.route("/operator/schedules/<int:schedule_id>/update", methods=["POST"])
def update_schedule_status(schedule_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "operator":
        flash("Only field operators can update schedules.")
        return redirect("/dashboard")

    db = get_db()

    schedule = db.execute(
        """
        SELECT id, status, scheduled_date, start_time, end_time
        FROM schedules
        WHERE id = ?
        AND assigned_operator_id = ?
        """,
        (schedule_id, session["user_id"])
    ).fetchone()

    if schedule is None:
        flash("Schedule not found or not assigned to you.")
        return redirect("/operator/schedules")

    new_status = request.form.get("status", "").strip()
    current_status = schedule["status"]

    allowed_transitions = {
        "planned": "in_progress",
        "in_progress": "completed"
    }

    if allowed_transitions.get(current_status) != new_status:
        flash("Invalid schedule status update.")
        return redirect("/operator/schedules")

    if new_status == "in_progress":
        timezone = ZoneInfo("Asia/Kolkata")
        now = datetime.now(timezone)

        scheduled_start = datetime.combine(
            date.fromisoformat(schedule["scheduled_date"]),
            time.fromisoformat(schedule["start_time"]),
            tzinfo=timezone
        )

        scheduled_end = datetime.combine(
            date.fromisoformat(schedule["scheduled_date"]),
            time.fromisoformat(schedule["end_time"]),
            tzinfo=timezone
        )

        if now < scheduled_start:
            flash("You can start this supply only during its scheduled time.")
            return redirect("/operator/schedules")

        if now > scheduled_end:
            flash("The scheduled time has ended. Please submit a reason if the supply could not be completed.")
            return redirect("/operator/schedules")

    event_time = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).isoformat(timespec="seconds")

    if new_status == "in_progress":
        cursor = db.execute(
            """
            UPDATE schedules
            SET status = ?, actual_start_at = ?
            WHERE id = ?
            AND assigned_operator_id = ?
            AND status = ?
            """,
            (
                new_status,
                event_time,
                schedule_id,
                session["user_id"],
                current_status
            )
        )

    else:
        cursor = db.execute(
            """
            UPDATE schedules
            SET status = ?, actual_completed_at = ?
            WHERE id = ?
            AND assigned_operator_id = ?
            AND status = ?
            """,
            (
                new_status,
                event_time,
                schedule_id,
                session["user_id"],
                current_status
            )
        )

    if cursor.rowcount != 1:
        db.rollback()
        flash("Schedule could not be updated. Please refresh and try again.")
        return redirect("/operator/schedules")

    operation_description = (
        "Water supply schedule started."
        if new_status == "in_progress"
        else "Water supply schedule completed."
    )

    db.execute(
        """
        INSERT INTO operation_logs (
            schedule_id,
            operator_id,
            action,
            notes
        )
        VALUES (?, ?, 'observation', ?)
        """,
        (
            schedule_id,
            session["user_id"],
            operation_description
        )
    )

    log_activity(
        "schedule_status_changed",
        "schedule",
        schedule_id,
        f"Status changed from {current_status} to {new_status}"
    )

    db.commit()

    flash("Schedule status updated successfully!")
    return redirect("/operator/schedules")


# Operator: Report Unsuccessful Water Supply
@app.route(
    "/operator/schedules/<int:schedule_id>/report-failure",
    methods=["POST"]
)
def report_schedule_failure(schedule_id):

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "operator":
        flash("Only field operators can report schedule failures.")
        return redirect("/dashboard")

    db = get_db()

    schedule = db.execute(
        """
        SELECT id, status, scheduled_date, start_time, end_time
        FROM schedules
        WHERE id = ?
        AND assigned_operator_id = ?
        """,
        (schedule_id, session["user_id"])
    ).fetchone()

    if schedule is None:
        flash("Schedule not found or not assigned to you.")
        return redirect("/operator/schedules")

    if schedule["status"] not in ("planned", "in_progress"):
        flash("A reason cannot be submitted for this schedule.")
        return redirect("/operator/schedules")

    timezone = ZoneInfo("Asia/Kolkata")
    now = datetime.now(timezone)

    scheduled_end = datetime.combine(
        date.fromisoformat(schedule["scheduled_date"]),
        time.fromisoformat(schedule["end_time"]),
        tzinfo=timezone
    )

    if now <= scheduled_end:
        flash("You can report an unsuccessful supply only after the scheduled end time.")
        return redirect("/operator/schedules")

    reason = request.form.get("reason", "").strip()

    if not reason:
        flash("Please provide a reason.")
        return redirect("/operator/schedules")

    if len(reason) > 1000:
        flash("The reason must be 1000 characters or fewer.")
        return redirect("/operator/schedules")

    cursor = db.execute(
        """
        UPDATE schedules
        SET status = 'cancelled'
        WHERE id = ?
        AND assigned_operator_id = ?
        AND status IN ('planned', 'in_progress')
        """,
        (schedule_id, session["user_id"])
    )

    if cursor.rowcount != 1:
        db.rollback()
        flash("Schedule could not be cancelled. Please refresh and try again.")
        return redirect("/operator/schedules")

    operation_note = f"Unable to complete scheduled supply: {reason}"

    db.execute(
        """
        INSERT INTO operation_logs (
            schedule_id,
            operator_id,
            action,
            notes
        )
        VALUES (?, ?, 'observation', ?)
        """,
        (
            schedule_id,
            session["user_id"],
            operation_note
        )
    )

    log_activity(
        "schedule_cancelled",
        "schedule",
        schedule_id,
        f"Operator reported unsuccessful water supply. Reason: {reason}"
    )

    db.commit()

    flash("Reason submitted. The schedule status is now Cancelled.")
    return redirect("/operator/schedules")


# Operator: View Personal Operation Logs
@app.route("/operator/operation-logs")
def operator_operation_logs():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect("/login")

    if session.get("role") != "operator":
        flash("Only field operators can access operation logs.")
        return redirect("/dashboard")

    db = get_db()
    operator_id = session["user_id"]

    selected_date = request.args.get("date", "").strip()
    selected_zone = request.args.get("zone_id", "").strip()
    selected_action = request.args.get("action", "").strip()

    conditions = ["operation_logs.operator_id = ?"]
    parameters = [operator_id]

    if selected_date:
        try:
            parsed_date = datetime.strptime(selected_date, "%Y-%m-%d")

            if parsed_date.strftime("%Y-%m-%d") != selected_date:
                raise ValueError

            conditions.append("schedules.scheduled_date = ?")
            parameters.append(selected_date)

        except ValueError:
            flash("Invalid date filter. Please use YYYY-MM-DD.")
            selected_date = ""

    zones = db.execute(
        """
        SELECT DISTINCT zones.id, zones.name
        FROM schedules
        JOIN zones ON schedules.zone_id = zones.id
        WHERE schedules.assigned_operator_id = ?
        ORDER BY zones.name
        """,
        (operator_id,)
    ).fetchall()

    valid_zone_ids = {str(zone["id"]) for zone in zones}

    if selected_zone:
        if selected_zone in valid_zone_ids:
            conditions.append("schedules.zone_id = ?")
            parameters.append(int(selected_zone))
        else:
            flash("Invalid zone filter.")
            selected_zone = ""

    if selected_action == "started":
        conditions.append("LOWER(operation_logs.notes) LIKE '%started%'")
    elif selected_action == "completed":
        conditions.append("LOWER(operation_logs.notes) LIKE '%completed%'")
    elif selected_action:
        flash("Invalid action filter.")
        selected_action = ""

    operation_logs = db.execute(
        """
        SELECT
            operation_logs.id,
            operation_logs.schedule_id,
            operation_logs.action,
            operation_logs.recorded_at,
            operation_logs.notes,
            schedules.scheduled_date,
            schedules.start_time,
            schedules.end_time,
            zones.name AS zone_name
        FROM operation_logs
        JOIN schedules
            ON operation_logs.schedule_id = schedules.id
        JOIN zones
            ON schedules.zone_id = zones.id
        WHERE """
        + " AND ".join(conditions)
        + """
        ORDER BY operation_logs.recorded_at DESC
        LIMIT 100
        """,
        parameters
    ).fetchall()

    return render_template(
        "operator_operation_logs.html",
        operation_logs=operation_logs,
        zones=zones,
        selected_date=selected_date,
        selected_zone=selected_zone,
        selected_action=selected_action
    )


# Logout
@app.route("/logout", methods=["POST"])
def logout():

    session.clear()
    flash("You have logged out successfully.")

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)

