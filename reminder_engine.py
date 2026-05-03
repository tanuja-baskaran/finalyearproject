"""
reminder_engine.py — Smart Medicine Reminder Backend
Handles SQLite storage, Gmail SMTP email, Twilio SMS, and background monitoring.
"""

import sqlite3
import smtplib
import threading
import logging
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(override=True)
except ImportError:
    pass

try:
    from twilio.rest import Client as TwilioClient  # type: ignore
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

logger = logging.getLogger("ReminderEngine")

# ── Database path ────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "reminders.db"

# ── Sent-alert guard: track last sent time per reminder to avoid duplicates ──
_sent_guard: dict = {}   # {reminder_id: datetime}
_guard_lock = threading.Lock()

# ── Per-thread connections + Python-level write lock ─────────────────────────
# Each thread (Streamlit main thread, monitor thread, notify sub-threads)
# gets its own sqlite3.Connection via threading.local().  WAL journal mode
# allows one writer + unlimited readers simultaneously; the 30-second timeout
# makes writers queue instead of immediately raising "database is locked".
# _db_lock is kept as an extra Python-level serializer for write operations.
_db_lock = threading.RLock()
_thread_local = threading.local()


def _conn() -> sqlite3.Connection:
    """Return a per-thread SQLite connection, creating it on first call."""
    conn = getattr(_thread_local, "connection", None)
    if conn is None:
        conn = sqlite3.connect(
            str(DB_PATH),
            check_same_thread=False,   # we manage safety via _db_lock
            timeout=30,                # wait up to 30 s before giving up
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        _thread_local.connection = conn
    return conn

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    """Create tables if they don't exist, migrate missing columns, enable WAL."""
    with _db_lock:
        conn = _conn()
        c = conn.cursor()

        # ── reminders table ───────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_name    TEXT    NOT NULL,
                dosage           TEXT    DEFAULT '',
                time             TEXT    NOT NULL,
                frequency        TEXT    DEFAULT 'Daily',
                food_instruction TEXT    DEFAULT 'After Food',
                phone            TEXT    DEFAULT '',
                email            TEXT    DEFAULT '',
                status           TEXT    DEFAULT 'Pending',
                last_taken       TEXT    DEFAULT '',
                days             TEXT    DEFAULT 'Everyday',
                snooze_until     TEXT    DEFAULT ''
            )
        """)

        # ── reminder_logs table ───────────────────────────────────────────────
        # 'status' column included to match any existing schema that has it NOT NULL
        c.execute("""
            CREATE TABLE IF NOT EXISTS reminder_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id INTEGER,
                date        TEXT,
                action      TEXT,
                status      TEXT    DEFAULT 'logged',
                timestamp   TEXT
            )
        """)

        # ── Migration: add any missing columns ────────────────────────────────
        existing_rem = {row[1] for row in c.execute("PRAGMA table_info(reminders)")}
        for col, defn in [
            ("dosage",           "TEXT DEFAULT ''"),
            ("food_instruction", "TEXT DEFAULT 'After Food'"),
            ("phone",            "TEXT DEFAULT ''"),
            ("email",            "TEXT DEFAULT ''"),
            ("snooze_until",     "TEXT DEFAULT ''"),
            ("last_taken",       "TEXT DEFAULT ''"),
            ("frequency",        "TEXT DEFAULT 'Daily'"),
        ]:
            if col not in existing_rem:
                c.execute(f"ALTER TABLE reminders ADD COLUMN {col} {defn}")
                logger.info("Migration: added '%s' to reminders", col)

        existing_log = {row[1] for row in c.execute("PRAGMA table_info(reminder_logs)")}
        for col, defn in [
            ("reminder_id", "INTEGER"),
            ("date",        "TEXT"),
            ("action",      "TEXT"),
            ("status",      "TEXT DEFAULT 'logged'"),
            ("timestamp",   "TEXT"),
        ]:
            if col not in existing_log:
                c.execute(f"ALTER TABLE reminder_logs ADD COLUMN {col} {defn}")
                logger.info("Migration: added '%s' to reminder_logs", col)

        conn.commit()
        # Note: do NOT close _shared_conn here — it's reused for the lifetime of the process


def get_all_reminders() -> list[dict]:
    with _db_lock:
        conn = _conn()
        rows = conn.execute("SELECT * FROM reminders ORDER BY time").fetchall()
        return [dict(r) for r in rows]


def get_reminder(rem_id: int) -> dict | None:
    with _db_lock:
        conn = _conn()
        row = conn.execute("SELECT * FROM reminders WHERE id=?", (rem_id,)).fetchone()
        return dict(row) if row else None


def add_reminder(data: dict) -> int:
    with _db_lock:
        conn = _conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO reminders
                (medicine_name, dosage, time, frequency, food_instruction, phone, email, days)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            data.get("medicine_name", ""),
            data.get("dosage", ""),
            data.get("time", "08:00"),
            data.get("frequency", "Daily"),
            data.get("food_instruction", "After Food"),
            data.get("phone", ""),
            data.get("email", ""),
            data.get("days", "Everyday"),
        ))
        new_id = c.lastrowid
        conn.commit()
        return new_id  # type: ignore


def update_reminder(rem_id: int, data: dict):
    with _db_lock:
        conn = _conn()
        conn.execute("""
            UPDATE reminders SET
                medicine_name=?, dosage=?, time=?, frequency=?,
                food_instruction=?, phone=?, email=?, days=?
            WHERE id=?
        """, (
            data.get("medicine_name", ""),
            data.get("dosage", ""),
            data.get("time", "08:00"),
            data.get("frequency", "Daily"),
            data.get("food_instruction", "After Food"),
            data.get("phone", ""),
            data.get("email", ""),
            data.get("days", "Everyday"),
            rem_id,
        ))
        conn.commit()


def delete_reminder(rem_id: int):
    with _db_lock:
        conn = _conn()
        conn.execute("DELETE FROM reminders WHERE id=?", (rem_id,))
        conn.execute("DELETE FROM reminder_logs WHERE reminder_id=?", (rem_id,))
        conn.commit()


def mark_taken(rem_id: int):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        conn = _conn()
        conn.execute("UPDATE reminders SET status='Taken', last_taken=?, snooze_until='' WHERE id=?",
                     (now_str, rem_id))
        conn.execute(
            "INSERT OR REPLACE INTO reminder_logs (reminder_id, date, action, status, timestamp) VALUES (?,?,?,?,?)",
            (rem_id, datetime.now().strftime("%Y-%m-%d"), "Taken", "logged", now_str),
        )
        conn.commit()


def mark_missed(rem_id: int):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        conn = _conn()
        conn.execute("UPDATE reminders SET status='Missed' WHERE id=?", (rem_id,))
        conn.execute(
            "INSERT OR REPLACE INTO reminder_logs (reminder_id, date, action, status, timestamp) VALUES (?,?,?,?,?)",
            (rem_id, datetime.now().strftime("%Y-%m-%d"), "Missed", "logged", now_str),
        )
        conn.commit()


def snooze_reminder(rem_id: int, minutes: int = 5):
    snooze_until = (datetime.now() + timedelta(minutes=minutes)).strftime("%H:%M")
    with _db_lock:
        conn = _conn()
        conn.execute("UPDATE reminders SET snooze_until=? WHERE id=?", (snooze_until, rem_id))
        conn.commit()


def reset_daily_statuses():
    """Reset all reminders to Pending at midnight."""
    with _db_lock:
        conn = _conn()
        conn.execute("UPDATE reminders SET status='Pending', snooze_until=''")
        conn.commit()


def get_adherence_stats() -> dict:
    with _db_lock:
        conn = _conn()
        today = datetime.now().strftime("%Y-%m-%d")
        taken_today = conn.execute(
            "SELECT COUNT(*) FROM reminder_logs WHERE date=? AND action='Taken'", (today,)
        ).fetchone()[0]
        missed_today = conn.execute(
            "SELECT COUNT(*) FROM reminder_logs WHERE date=? AND action='Missed'", (today,)
        ).fetchone()[0]
        total_logs = conn.execute("SELECT COUNT(*) FROM reminder_logs WHERE action='Taken'").fetchone()[0]
        total_possible = conn.execute("SELECT COUNT(*) FROM reminder_logs").fetchone()[0]
        adherence_pct = round((total_logs / total_possible * 100) if total_possible > 0 else 0, 1)
        total_reminders = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
        return {
            "taken_today": taken_today,
            "missed_today": missed_today,
            "adherence_pct": adherence_pct,
            "total_reminders": total_reminders,
        }


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL (Gmail SMTP)
# ─────────────────────────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """Send an email via Gmail SMTP. Returns (success, message)."""
    gmail_addr = os.getenv("GMAIL_ADDRESS", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")

    if not gmail_addr or not gmail_pass:
        return False, "Gmail credentials not configured in .env"
    if not to_email:
        return False, "No recipient email address provided"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"DiabetesGuard Pro <{gmail_addr}>"
        msg["To"]      = to_email

        # Plain text fallback
        plain = MIMEText(body, "plain")

        # HTML version
        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:0;margin:0;">
        <div style="max-width:560px;margin:30px auto;background:#fff;border-radius:16px;
                    box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;">
            <div style="background:linear-gradient(135deg,#2563EB,#1D4ED8);padding:28px 32px;">
                <h1 style="color:#fff;margin:0;font-size:1.4rem;">💊 DiabetesGuard Pro</h1>
                <p style="color:#BFDBFE;margin:6px 0 0;font-size:0.9rem;">Smart Medicine Reminder</p>
            </div>
            <div style="padding:28px 32px;">
                <pre style="font-family:Arial,sans-serif;white-space:pre-wrap;
                            color:#1E293B;font-size:0.95rem;line-height:1.7;">{body}</pre>
            </div>
            <div style="background:#F8FAFC;padding:16px 32px;text-align:center;
                        border-top:1px solid #E2E8F0;">
                <p style="color:#94A3B8;font-size:0.78rem;margin:0;">
                    This is an automated reminder from DiabetesGuard Pro.<br>
                    Please consult your doctor for medical advice.
                </p>
            </div>
        </div>
        </body></html>
        """
        html = MIMEText(html_body, "html")

        msg.attach(plain)
        msg.attach(html)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(gmail_addr, gmail_pass)
            server.sendmail(gmail_addr, to_email, msg.as_string())

        logger.info("Email sent to %s — Subject: %s", to_email, subject)
        return True, f"✅ Email sent to {to_email}"

    except smtplib.SMTPAuthenticationError:
        msg_err = "Gmail authentication failed. Check GMAIL_APP_PASSWORD in .env"
        logger.error(msg_err)
        return False, msg_err
    except Exception as e:
        logger.error("Email error: %s", e)
        return False, f"Email error: {e}"


def send_test_email(to_email: str) -> tuple[bool, str]:
    subject = "✅ DiabetesGuard Pro — Email Test Successful"
    body = (
        "Hello!\n\n"
        "This is a test email from DiabetesGuard Pro.\n"
        "Your email notification system is configured correctly.\n\n"
        "You will receive medicine reminders at this address.\n\n"
        "— DiabetesGuard Pro 💊"
    )
    return send_email(to_email, subject, body)


def send_reminder_email(rem: dict, alert_type: str = "due") -> tuple[bool, str]:
    """Send a reminder alert email for a scheduled medicine."""
    to_email = rem.get("email", "")
    if not to_email:
        return False, "No email set for this reminder"

    name   = rem.get("medicine_name", "Medicine")
    dosage = rem.get("dosage", "")
    time_  = rem.get("time", "")
    food   = rem.get("food_instruction", "")

    if alert_type == "early":
        subject = f"⏰ Upcoming Dose Reminder — {name}"
        body = (
            f"Hi,\n\n"
            f"Your medicine is due in 10 minutes:\n\n"
            f"  💊 Medicine : {name} {dosage}\n"
            f"  ⏰ Scheduled: {_fmt_time(time_)}\n"
            f"  🍽️  Take     : {food}\n\n"
            f"Please prepare your dose.\n\n— DiabetesGuard Pro"
        )
    elif alert_type == "missed":
        subject = f"⚠️ Missed Dose Alert — {name}"
        body = (
            f"Hi,\n\n"
            f"You missed your scheduled dose of {name} {dosage}.\n\n"
            f"  ⏰ Was scheduled at: {_fmt_time(time_)}\n"
            f"  🍽️  Instruction    : {food}\n\n"
            f"Please consult your doctor if you're unsure whether to take a late dose.\n\n"
            f"— DiabetesGuard Pro"
        )
    else:  # due now
        subject = f"💊 Time to Take {name}!"
        body = (
            f"Hi,\n\n"
            f"It's time for your medicine:\n\n"
            f"  💊 Medicine : {name} {dosage}\n"
            f"  ⏰ Time     : {_fmt_time(time_)}\n"
            f"  🍽️  Take     : {food}\n\n"
            f"Open the DiabetesGuard Pro app to mark it as taken.\n\n— DiabetesGuard Pro"
        )

    return send_email(to_email, subject, body)


# ─────────────────────────────────────────────────────────────────────────────
# SMS (Twilio)
# ─────────────────────────────────────────────────────────────────────────────

def send_sms(to_phone: str, body: str) -> tuple[bool, str]:
    """Send SMS via Twilio. Returns (success, message)."""
    if not TWILIO_AVAILABLE:
        return False, "Twilio package not installed (pip install twilio)"

    sid   = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_ = os.getenv("TWILIO_FROM_NUMBER", "")

    if not sid or sid.startswith("AC" + "x"):
        return False, "Twilio credentials not configured in .env"
    if not to_phone:
        return False, "No phone number provided"

    try:
        client = TwilioClient(sid, token)
        msg = client.messages.create(body=body, from_=from_, to=to_phone)
        logger.info("SMS sent to %s, SID=%s", to_phone, msg.sid)
        return True, f"✅ SMS sent to {to_phone}"
    except Exception as e:
        logger.error("SMS error: %s", e)
        return False, f"SMS error: {e}"


def send_test_sms(to_phone: str) -> tuple[bool, str]:
    body = (
        "💊 DiabetesGuard Pro Test\n"
        "Your SMS notifications are working correctly!\n"
        "You will receive medicine reminders here."
    )
    return send_sms(to_phone, body)


def send_reminder_sms(rem: dict, alert_type: str = "due") -> tuple[bool, str]:
    to_phone = rem.get("phone", "")
    if not to_phone:
        return False, "No phone set for this reminder"

    name   = rem.get("medicine_name", "Medicine")
    dosage = rem.get("dosage", "")
    time_  = rem.get("time", "")
    food   = rem.get("food_instruction", "")

    if alert_type == "early":
        body = (
            f"⏰ DiabetesGuard Pro\n"
            f"Upcoming: {name} {dosage} in 10 min ({_fmt_time(time_)})\n"
            f"Take: {food}"
        )
    elif alert_type == "missed":
        body = (
            f"⚠️ DiabetesGuard Pro\n"
            f"Missed dose: {name} {dosage} (was {_fmt_time(time_)})\n"
            f"Please consult your doctor."
        )
    else:
        body = (
            f"💊 DiabetesGuard Pro\n"
            f"Time to take: {name} {dosage}\n"
            f"Scheduled: {_fmt_time(time_)} | {food}"
        )

    return send_sms(to_phone, body)


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL NOTIFY NOW
# ─────────────────────────────────────────────────────────────────────────────

def notify_now(rem_id: int) -> list[str]:
    """Immediately send email + SMS for a reminder. Returns list of result messages."""
    rem = get_reminder(rem_id)
    if not rem:
        return ["Reminder not found"]
    results = []
    ok_e, msg_e = send_reminder_email(rem, "due")
    results.append(msg_e)
    ok_s, msg_s = send_reminder_sms(rem, "due")
    results.append(msg_s)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND MONITORING THREAD
# ─────────────────────────────────────────────────────────────────────────────

_monitor_thread: threading.Thread | None = None
_stop_event = threading.Event()
_last_reset_date: str = ""


def _should_fire(rem_id: int, window_minutes: int = 5) -> bool:
    """Return True if we haven't sent an alert for this reminder in the last `window_minutes`."""
    with _guard_lock:
        last = _sent_guard.get(rem_id)
        if last is None:
            return True
        return (datetime.now() - last).total_seconds() > window_minutes * 60


def _record_fire(rem_id: int):
    with _guard_lock:
        _sent_guard[rem_id] = datetime.now()


def _is_today(days_value) -> bool:
    """Check if today is in the reminder's day schedule."""
    day_abbr = datetime.now().strftime("%a")[:3]  # Mon, Tue, …
    if days_value == "Everyday" or days_value == ["Everyday"]:
        return True
    if isinstance(days_value, list):
        return day_abbr in days_value
    if isinstance(days_value, str):
        return day_abbr in days_value
    return True


def _fmt_time(t: str) -> str:
    """Convert HH:MM → 12-hour AM/PM format."""
    try:
        return datetime.strptime(t, "%H:%M").strftime("%I:%M %p")
    except Exception:
        return t


def _monitor_loop():
    global _last_reset_date
    logger.info("Reminder monitor started.")
    while not _stop_event.is_set():
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # Midnight reset
            if _last_reset_date != today_str:
                reset_daily_statuses()
                _last_reset_date = today_str
                logger.info("Daily status reset done.")

            reminders = get_all_reminders()
            for rem in reminders:
                if not _is_today(rem.get("days", "Everyday")):
                    continue

                status = rem.get("status", "Pending")
                if status == "Taken":
                    continue

                time_str = rem.get("time", "")
                if not time_str:
                    continue

                try:
                    rem_dt = datetime.strptime(time_str, "%H:%M").replace(
                        year=now.year, month=now.month, day=now.day
                    )
                except ValueError:
                    continue

                diff_min = (now - rem_dt).total_seconds() / 60  # +ve = overdue
                rem_id = rem["id"]

                # Snooze check
                snooze_str = rem.get("snooze_until", "")
                if snooze_str:
                    try:
                        snooze_dt = datetime.strptime(snooze_str, "%H:%M").replace(
                            year=now.year, month=now.month, day=now.day
                        )
                        if now < snooze_dt:
                            continue  # Still snoozed
                    except Exception:
                        pass

                # Early reminder: 10 min before
                if -12 <= diff_min <= -8 and _should_fire(rem_id):
                    logger.info("Early alert for: %s", rem["medicine_name"])
                    _thread_notify(rem, "early")
                    _record_fire(rem_id)

                # Due now: within 0–4 min window
                elif 0 <= diff_min <= 4 and _should_fire(rem_id):
                    logger.info("Due now alert for: %s", rem["medicine_name"])
                    _thread_notify(rem, "due")
                    _record_fire(rem_id)

                    with _db_lock:
                        conn = _conn()
                        conn.execute("UPDATE reminders SET status='Due Now' WHERE id=?", (rem_id,))
                        conn.commit()

                # Missed: >60 min overdue
                elif diff_min > 60 and status not in ("Missed", "Taken") and _should_fire(rem_id, 120):
                    logger.info("Missed dose detected for: %s", rem["medicine_name"])
                    mark_missed(rem_id)
                    _thread_notify(rem, "missed")
                    _record_fire(rem_id)

        except Exception as exc:
            logger.error("Monitor error: %s", exc)

        _stop_event.wait(60)  # Check every 60 seconds

    logger.info("Reminder monitor stopped.")


def _thread_notify(rem: dict, alert_type: str):
    """Fire notifications in a separate daemon thread so monitor isn't blocked."""
    def _run():
        send_reminder_email(rem, alert_type)
        send_reminder_sms(rem, alert_type)
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def start_monitor():
    """Start the background reminder monitor (call once at app startup)."""
    global _monitor_thread
    if _monitor_thread is not None and _monitor_thread.is_alive():
        return  # Already running
    _stop_event.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True, name="ReminderMonitor")
    _monitor_thread.start()
    logger.info("Reminder monitor thread launched.")


def stop_monitor():
    _stop_event.set()


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-INIT
# ─────────────────────────────────────────────────────────────────────────────
try:
    init_db()
    start_monitor()
except Exception as _init_err:
    logger.warning("reminder_engine auto-init error: %s", _init_err)
