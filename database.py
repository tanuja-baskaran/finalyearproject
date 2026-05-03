"""
database.py — Health Records Database
Stores assessment results in health_records.db (separate from reminders.db).
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("HealthDB")

DB_PATH = Path(__file__).parent / "health_records.db"


def init_db():
    """Create the health_records table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS health_records (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp         TEXT    NOT NULL,
            age               INTEGER,
            gender            TEXT,
            bmi               REAL,
            blood_glucose     REAL,
            hba1c             REAL,
            hypertension      INTEGER DEFAULT 0,
            heart_disease     INTEGER DEFAULT 0,
            smoking           TEXT    DEFAULT 'Never',
            prediction_result TEXT,
            risk_score        REAL,
            model_used        TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Health records DB initialised at %s", DB_PATH)


def save_health_record(data: dict):
    """Insert a new health assessment record."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO health_records
            (timestamp, age, gender, bmi, blood_glucose, hba1c,
             hypertension, heart_disease, smoking,
             prediction_result, risk_score, model_used)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data.get("age"),
        data.get("gender"),
        data.get("bmi"),
        data.get("blood_glucose"),
        data.get("hba1c"),
        int(data.get("hypertension", 0)),
        int(data.get("heart_disease", 0)),
        data.get("smoking", "Never"),
        data.get("prediction_result"),
        data.get("risk_score"),
        data.get("model_used"),
    ))
    conn.commit()
    conn.close()


def get_health_records(limit: int = 50) -> list[dict]:
    """Fetch the most recent health records."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM health_records ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_health_record(record_id: int):
    """Delete a health record by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM health_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
