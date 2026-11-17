-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- 1. Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (
        role IN ('manager', 'operator', 'maintenance', 'resident')
    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- 2. Zones table
CREATE TABLE zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 3. Valves table
CREATE TABLE valves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    valve_code TEXT NOT NULL,
    location TEXT,
    valve_type TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (zone_id) REFERENCES zones(id),
    UNIQUE (zone_id, valve_code)
);

-- 4. Supply schedules table
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    assigned_operator_id INTEGER NOT NULL,
    scheduled_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'completed', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actual_start_at TEXT,
    actual_completed_at TEXT,

    FOREIGN KEY (zone_id) REFERENCES zones(id),
    FOREIGN KEY (assigned_operator_id) REFERENCES users(id),

    CHECK (end_time > start_time)
);

-- 5. Operation logs table
CREATE TABLE operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    valve_id INTEGER,
    operator_id INTEGER NOT NULL,
    action TEXT NOT NULL
        CHECK (action IN ('valve_opened', 'valve_closed', 'inspection', 'observation')),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    FOREIGN KEY (schedule_id) REFERENCES schedules(id),
    FOREIGN KEY (valve_id) REFERENCES valves(id),
    FOREIGN KEY (operator_id) REFERENCES users(id)
);

-- 6. Incidents table
CREATE TABLE incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    valve_id INTEGER,
    reported_by INTEGER NOT NULL,
    incident_type TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL DEFAULT 'reported'
        CHECK (status IN ('reported', 'verified', 'assigned', 'resolved', 'closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,

    FOREIGN KEY (zone_id) REFERENCES zones(id),
    FOREIGN KEY (valve_id) REFERENCES valves(id),
    FOREIGN KEY (reported_by) REFERENCES users(id)
);

-- 7. Maintenance tasks table
CREATE TABLE maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    assigned_to INTEGER NOT NULL,
    assigned_by INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned', 'inspecting', 'repairing', 'completed')),
    inspection_notes TEXT,
    repair_notes TEXT,
    completion_notes TEXT,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (incident_id) REFERENCES incidents(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id),
    FOREIGN KEY (assigned_by) REFERENCES users(id)
);

-- 8. Activity logs table
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

-- 9. Resident profiles table
CREATE TABLE resident_profiles (
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
);
