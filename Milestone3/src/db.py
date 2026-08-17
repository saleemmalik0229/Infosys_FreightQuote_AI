import sqlite3
import bcrypt
import jwt
import re
import time
import datetime
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Tuple, Dict, Optional

DB_FILE = "freightquote.db"
JWT_SECRET = "freightquote_jwt_secret_key_12345"

def init_db(db_path: str = DB_FILE):
    """Initializes the SQLite database with the necessary tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        security_question TEXT NOT NULL,
        security_answer TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'User',
        is_locked INTEGER NOT NULL DEFAULT 0,
        lock_until INTEGER NOT NULL DEFAULT 0,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)
    
    # Create OTP table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS otps (
        email TEXT PRIMARY KEY,
        otp_code TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        cooldown_level INTEGER NOT NULL DEFAULT 0,
        last_requested_at INTEGER NOT NULL DEFAULT 0
    )
    """)
    
    # Create default Admin if not exists
    cursor.execute("SELECT * FROM users WHERE email = 'admin@freightquote.ai'")
    if not cursor.fetchone():
        hashed = bcrypt.hashpw("Admin@1234".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("""
        INSERT INTO users (email, password_hash, security_question, security_answer, role, created_at)
        VALUES ('admin@freightquote.ai', ?, 'What is your favorite color?', 'Blue', 'Admin', ?)
        """, (hashed, datetime.datetime.now().isoformat()))
        
    conn.commit()
    conn.close()

# Password & Email Validations
def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))

def validate_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def check_password_strength(password: str) -> str:
    score = 0
    if len(password) >= 8:
        score += 1
    if re.search(r"[a-z]", password) and re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[0-9]", password):
        score += 1
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 1
        
    if score <= 2:
        return "Weak"
    elif score == 3:
        return "Average"
    else:
        return "Good"

# JWT Tokens
def create_jwt_token(email: str, role: str) -> str:
    payload = {
        "email": email,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_jwt_token(token: str) -> Optional[Dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# Lockout Management
def check_user_lockout(email: str, db_path: str = DB_FILE) -> Tuple[bool, str]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT is_locked, lock_until, failed_attempts FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return False, "User not found"
        
    is_locked, lock_until, failed_attempts = row
    current_time = int(time.time())
    
    if is_locked:
        if lock_until == 9999999999:
            return True, "Account is permanently locked. Contact an admin to unlock."
        elif current_time < lock_until:
            remaining = lock_until - current_time
            minutes = remaining // 60
            seconds = remaining % 60
            return True, f"Account locked. Try again in {minutes}m {seconds}s."
        else:
            # Lock expired, reset
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_locked = 0, lock_until = 0 WHERE email = ?", (email,))
            conn.commit()
            conn.close()
            
    return False, ""

def handle_failed_login(email: str, db_path: str = DB_FILE) -> str:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT failed_attempts FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "User not found"
        
    attempts = row[0] + 1
    current_time = int(time.time())
    lock_until = 0
    is_locked = 0
    msg = ""
    
    if attempts == 3:
        lock_until = current_time + 300  # 5 min
        is_locked = 1
        msg = "Account locked for 5 minutes due to 3 failed attempts."
    elif attempts == 4:
        lock_until = current_time + 900  # 15 min
        is_locked = 1
        msg = "Account locked for 15 minutes due to 4 failed attempts."
    elif attempts >= 5:
        lock_until = 9999999999  # Permanent
        is_locked = 1
        msg = "Account permanently locked due to 5+ failed attempts. Contact an admin."
    else:
        msg = f"Failed attempt. {3 - attempts} attempts remaining before lockout."
        
    cursor.execute("""
    UPDATE users 
    SET failed_attempts = ?, is_locked = ?, lock_until = ? 
    WHERE email = ?
    """, (attempts, is_locked, lock_until, email))
    conn.commit()
    conn.close()
    return msg

def reset_failed_login(email: str, db_path: str = DB_FILE):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET failed_attempts = 0, is_locked = 0, lock_until = 0 WHERE email = ?", (email,))
    conn.commit()
    conn.close()

# OTP Management
def request_otp(email: str, db_path: str = DB_FILE) -> Tuple[bool, str, str]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT cooldown_level, last_requested_at FROM otps WHERE email = ?", (email,))
    row = cursor.fetchone()
    
    current_time = int(time.time())
    cooldowns = [60, 180, 300, 3600] # levels 0, 1, 2, 3+
    
    if row:
        cooldown_level, last_requested_at = row
        level = min(cooldown_level, 3)
        cooldown_duration = cooldowns[level]
        elapsed = current_time - last_requested_at
        
        if elapsed < cooldown_duration:
            conn.close()
            remaining = cooldown_duration - elapsed
            return False, f"Please wait {remaining} seconds before requesting a new OTP.", ""
            
        next_level = min(cooldown_level + 1, 3)
    else:
        next_level = 0
        
    # Generate 6-digit OTP
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = current_time + 300 # 5 min expiry
    
    cursor.execute("""
    INSERT OR REPLACE INTO otps (email, otp_code, expires_at, cooldown_level, last_requested_at)
    VALUES (?, ?, ?, ?, ?)
    """, (email, otp_code, expires_at, next_level, current_time))
    
    conn.commit()
    conn.close()
    
    return True, f"OTP generated successfully.", otp_code

def send_otp_email(email: str, otp_code: str) -> bool:
    try:
        from google.colab import userdata
        sender_email = userdata.get('GMAIL_OTP_EMAIL')
        sender_password = userdata.get('GMAIL_OTP_PASSWORD')
    except Exception:
        sender_email = None
        sender_password = None
        
    # Always log to local file for validation convenience
    with open("mock_otp.txt", "w") as f:
        f.write(f"{email}:{otp_code}")
        
    if not sender_email or not sender_password:
        print(f"[OTP LOG - LOCAL FALLBACK] OTP code for {email} is: {otp_code}")
        return True
        
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = "FreightQuote AI - OTP Verification"
        body = f"Your verification code is: {otp_code}. This code is valid for 5 minutes."
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[OTP ERROR] SMTP failed: {e}. Logged to mock_otp.txt instead.")
        return True

def verify_otp(email: str, code: str, db_path: str = DB_FILE) -> Tuple[bool, str]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT otp_code, expires_at FROM otps WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return False, "No OTP requested for this email."
        
    otp_code, expires_at = row
    current_time = int(time.time())
    
    if current_time > expires_at:
        return False, "OTP has expired. Please request a new one."
        
    if otp_code != code:
        return False, "Invalid OTP code."
        
    return True, "OTP verified successfully."
