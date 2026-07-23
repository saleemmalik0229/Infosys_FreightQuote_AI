import os
import sqlite3
import datetime
from pathlib import Path

# Database path setup
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = os.path.join(BASE_DIR, "infosys_portal.db")

def get_db():
    """
    Establishes and returns a SQLite database connection.
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database schema and performs non-destructive migrations
    to extend the users table for Milestone 2 features.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Base Users Table creation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT,
                security_question TEXT,
                security_answer_hash TEXT,
                created_at TEXT
            )
        """)
        
        # 2. Login Attempts Table for Rate Limiting & Recovery
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                last_attempt REAL DEFAULT 0,
                resend_count INTEGER DEFAULT 0,
                last_resend_time REAL DEFAULT 0
            )
        """)
        
        # 3. Dynamic Non-Destructive Schema Extension for Milestone 2
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "failed_attempts" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0")
            
        if "lock_until" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN lock_until REAL DEFAULT 0")
            
        if "account_status" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN account_status TEXT DEFAULT 'active'")
            
        conn.commit()

def seed_initial_users(hash_func, check_func, admin_email, admin_password):
    """
    Seeds initial administrator and springboard mentor user accounts while preserving
    existing account password hashes and user data.
    """
    init_db()
    users_to_seed = [
        ("Administrator", admin_email, admin_password, "What is your pet name?", "admin"),
        ("Springboard Mentor 018", "springboardmentor018@gmail.com", "Welcome@123", "What is your pet name?", "mentor"),
        ("Springboard Mentor 038", "springboardmentor038@gmail.com", "Welcome@123", "What is your pet name?", "mentor")
    ]
    
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    with get_db() as conn:
        cursor = conn.cursor()
        for name, email, pwd, sq, sa in users_to_seed:
            cursor.execute("SELECT password_hash FROM users WHERE email=?", (email,))
            row = cursor.fetchone()
            
            pwd_hash = hash_func(pwd)
            sa_hash = hash_func(sa.lower().strip())
            
            if not row:
                cursor.execute("""
                    INSERT INTO users 
                    (username, email, password_hash, security_question, security_answer_hash, created_at, failed_attempts, lock_until, account_status) 
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'active')
                """, (name, email, pwd_hash, sq, sa_hash, now_str))
            else:
                # Sync configured admin credentials on startup if updated in config
                if email == admin_email and not check_func(pwd, row["password_hash"]):
                    cursor.execute("UPDATE users SET password_hash=? WHERE email=?", (pwd_hash, email))
        conn.commit()

def unlock_user_account(email: str):
    """
    Admin function to unlock a locked account, resetting failed attempts and lock timers.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET failed_attempts = 0, lock_until = 0, account_status = 'active'
            WHERE email = ?
        """, (email,))
        cursor.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        conn.commit()
        return cursor.rowcount > 0

def get_user_by_email(email: str):
    """
    Fetches user record by email address.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_users():
    """
    Fetches all registered user records for Admin Directory.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, failed_attempts, lock_until, account_status, created_at FROM users")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def delete_user_by_email(email: str):
    """
    Deletes a user account and associated login attempt logs.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email=?", (email,))
        cursor.execute("DELETE FROM login_attempts WHERE email=?", (email,))
        conn.commit()
        return cursor.rowcount > 0
