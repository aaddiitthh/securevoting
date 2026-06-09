DROP TABLE IF EXISTS main_admins;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS candidates;
DROP TABLE IF EXISTS tokens;
DROP TABLE IF EXISTS votes;
DROP TABLE IF EXISTS election_status;

CREATE TABLE main_admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_code TEXT UNIQUE NOT NULL,
    dept_name TEXT NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments (id)
);

CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    gender TEXT CHECK(gender IN ('Boy', 'Girl')) NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments (id)
);

CREATE TABLE tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    token_value TEXT UNIQUE NOT NULL,
    is_used BOOLEAN DEFAULT 0,
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (department_id) REFERENCES departments (id)
);

CREATE TABLE votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    boy_candidate_id INTEGER NOT NULL,
    girl_candidate_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments (id),
    FOREIGN KEY (boy_candidate_id) REFERENCES candidates (id),
    FOREIGN KEY (girl_candidate_id) REFERENCES candidates (id)
);

CREATE TABLE election_status (
    id INTEGER PRIMARY KEY CHECK (id = 1), -- Ensure only one row
    is_active BOOLEAN DEFAULT 0
);

