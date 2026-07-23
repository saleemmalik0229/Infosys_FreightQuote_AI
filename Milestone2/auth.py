import re
import time
import secrets
import datetime
import smtplib
from email.utils import formatdate, make_msgid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import sys
from pathlib import Path

# Add root directory to sys.path to resolve root config.py
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import jwt
import bcrypt
import config
from db import get_db

JWT_SECRET = config.JWT_SECRET
EMAIL_ADDRESS = config.EMAIL_ADDRESS
EMAIL_PASSWORD = config.EMAIL_PASSWORD
OTP_EXPIRY_MINUTES = config.OTP_EXPIRY_MINUTES

# --- Cryptography Helpers ---
def hash_txt(txt: str) -> str:
    """Hashes plain text using bcrypt with salted rounds."""
    return bcrypt.hashpw(txt.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def check_txt(txt: str, hashed: str) -> bool:
    """Verifies a plain text string against a bcrypt hash."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(txt.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

# --- Validation Functions ---
def is_valid_email(email: str) -> bool:
    """Validates email format using regex."""
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-.]+)?$", email))

def evaluate_password_strength(password: str):
    """
    Evaluates password complexity and returns a numeric score, rating classification,
    associated hex color code, and helpful feedback message.
    
    Ratings:
      - Weak: Score < 5 (Red)
      - Average: Score 5-9 (Orange/Yellow)
      - Good: Score >= 10 (Green)
    """
    if not password:
        return 0, "Weak", "#EF4444", "Password is required."
        
    score = 0
    feedback = []
    
    # Length checks
    length = len(password)
    if length >= 8:
        score += 2
    else:
        feedback.append("Min 8 characters required")
        
    if length >= 12:
        score += 2
    if length >= 16:
        score += 2
        
    # Character diversity checks
    if re.search(r"[A-Z]", password):
        score += 2
    else:
        feedback.append("Include uppercase letter")
        
    if re.search(r"[a-z]", password):
        score += 1
    else:
        feedback.append("Include lowercase letter")
        
    if re.search(r"\d", password):
        score += 2
    else:
        feedback.append("Include number")
        
    if re.search(r"[@$!%*?&_#^-]", password):
        score += 2
    else:
        feedback.append("Include special character")

    # Classification
    if score < 5:
        rating = "Weak"
        color = "#EF4444"  # Red
    elif 5 <= score < 10:
        rating = "Average"
        color = "#F59E0B"  # Yellow/Orange
    else:
        rating = "Good"
        color = "#10B981"  # Green
        
    msg = " | ".join(feedback) if feedback else "Strong password!"
    return score, rating, color, msg

def is_strong_password(password: str):
    """
    Backward compatible helper returning (is_valid: bool, message: str).
    Validates if password meets minimum strength requirements.
    """
    score, rating, _, msg = evaluate_password_strength(password)
    if rating == "Weak":
        return False, f"Password is too weak: {msg}"
    return True, "Strong password."

# --- Progressive Account Lockout Engine ---
def check_progressive_lockout(email: str):
    """
    Checks if an account is locked due to progressive login failures.
    Returns: (is_locked: bool, time_remaining_seconds: int, status_message: str)
    
    Lockout rules:
      - 3 failed attempts  => 5 min lock (300 s)
      - 4 failed attempts  => 15 min lock (900 s)
      - 5 failed attempts  => Permanently locked (account_status='locked') until Admin unlocks
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT failed_attempts, lock_until, account_status FROM users WHERE email=?", (email,))
        row = cursor.fetchone()
        
    if not row:
        return False, 0, ""
        
    failed_attempts = row["failed_attempts"] or 0
    lock_until = row["lock_until"] or 0
    account_status = row["account_status"] or "active"
    now = time.time()
    
    # 1. Permanent lock check (5 consecutive failed attempts)
    if failed_attempts >= 5 or (account_status == "locked" and lock_until > now + 86400):
        return True, 0, "❌ Account PERMANENTLY LOCKED due to 5 consecutive failed attempts. Contact Administrator to unlock."
        
    # 2. Temporary lock check (3 or 4 failed attempts)
    if account_status == "locked" and now < lock_until:
        remaining = int(lock_until - now)
        minutes = remaining // 60
        seconds = remaining % 60
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        return True, remaining, f"❌ Account locked due to {failed_attempts} failed attempts. Try again in {time_str}."
        
    # 3. If lock duration expired and < 5 attempts, auto-reactivate account
    if account_status == "locked" and now >= lock_until and failed_attempts < 5:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET account_status='active', lock_until=0 WHERE email=?", (email,))
            conn.commit()
            
    return False, 0, ""

def record_failed_login(email: str):
    """
    Records a failed login attempt and applies progressive lockout penalties.
    """
    now = time.time()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT failed_attempts FROM users WHERE email=?", (email,))
        row = cursor.fetchone()
        
        if not row:
            return "❌ Invalid email or password."
            
        current_attempts = (row["failed_attempts"] or 0) + 1
        lock_until = 0
        new_status = "active"
        msg = f"❌ Invalid email or password. Attempt {current_attempts} of 3 before lockout."
        
        if current_attempts == 3:
            lock_until = now + 300  # 5 minutes
            new_status = "locked"
            msg = "❌ 3 failed attempts! Account locked for 5 minutes."
        elif current_attempts == 4:
            lock_until = now + 900  # 15 minutes
            new_status = "locked"
            msg = "❌ 4 failed attempts! Account locked for 15 minutes."
        elif current_attempts >= 5:
            current_attempts = 5
            lock_until = now + 315360000  # ~10 years (Permanent Lock)
            new_status = "locked"
            msg = "❌ 5 failed attempts! Account PERMANENTLY LOCKED. Contact Administrator to unlock."
            
        cursor.execute("""
            UPDATE users 
            SET failed_attempts = ?, lock_until = ?, account_status = ? 
            WHERE email = ?
        """, (current_attempts, lock_until, new_status, email))
        conn.commit()
        return msg

def record_successful_login(email: str):
    """Resets failed login attempts and clears account locks upon successful authentication."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET failed_attempts = 0, lock_until = 0, account_status = 'active'
            WHERE email = ?
        """, (email,))
        cursor.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        conn.commit()

# --- OTP Resend Cooldown Engine ---
def get_otp_cooldown_delay(resend_count: int) -> int:
    """
    Returns required cooldown seconds based on resend attempt count:
      - 1st resend: 60 sec
      - 2nd resend: 180 sec (3 min)
      - 3rd resend: 300 sec (5 min)
      - 4th+ resend: 3600 sec (1 hour)
    """
    if resend_count <= 1:
        return 60
    elif resend_count == 2:
        return 180
    elif resend_count == 3:
        return 300
    else:
        return 3600

def check_otp_resend_cooldown(email: str):
    """
    Checks whether an email OTP resend request is currently rate limited.
    Returns: (can_resend: bool, remaining_seconds: int, next_resend_count: int)
    """
    now = time.time()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT resend_count, last_resend_time FROM login_attempts WHERE email=?", (email,))
        row = cursor.fetchone()
        
    if not row:
        return True, 0, 1
        
    resend_count = row["resend_count"] or 0
    last_time = row["last_resend_time"] or 0
    
    required_delay = get_otp_cooldown_delay(resend_count + 1)
    elapsed = now - last_time
    
    if elapsed < required_delay:
        remaining = int(required_delay - elapsed)
        return False, remaining, resend_count + 1
        
    return True, 0, resend_count + 1

def record_otp_resend(email: str):
    """Updates OTP resend attempt counter and timestamp."""
    now = time.time()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT resend_count FROM login_attempts WHERE email=?", (email,))
        row = cursor.fetchone()
        
        count = (row["resend_count"] + 1) if row else 1
        cursor.execute("""
            INSERT INTO login_attempts (email, attempts, last_attempt, resend_count, last_resend_time)
            VALUES (?, 0, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                resend_count = ?,
                last_resend_time = ?
        """, (email, now, count, now, count, now))
        conn.commit()

# --- JWT Session & Recovery Tokens ---
def make_jwt(email: str) -> str:
    """Generates signed session JWT token valid for 2 hours."""
    payload = {
        "email": email,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_jwt(token: str):
    """Verifies session JWT token signature and expiration."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def generate_otp() -> str:
    """Generates random 6-digit verification code."""
    return f"{secrets.randbelow(900000) + 100000}"

def make_otp_token(email: str, otp: str) -> str:
    """Generates signed OTP verification token valid for 5 minutes."""
    payload = {
        "sub": email,
        "otp_hash": hash_txt(otp),
        "type": "password_reset_otp",
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_otp_token(token: str, input_otp: str, email: str):
    """Validates 6-digit OTP code against token payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("sub") != email or payload.get("type") != "password_reset_otp":
            return False, "Security token mismatch."
        if check_txt(input_otp, payload.get("otp_hash")):
            return True, "Valid"
        return False, "Invalid 6-digit OTP code."
    except jwt.ExpiredSignatureError:
        return False, f"⚠️ This OTP code expired after {OTP_EXPIRY_MINUTES} minutes. Please request a new one."
    except Exception:
        return False, "Invalid or corrupted verification token."

def send_otp_email(to_email: str, otp: str):
    """Dispatches RFC-compliant OTP verification email via SMTP or triggers Sandbox Mode."""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return True, "sandbox_mode"

    msg = MIMEMultipart('alternative')
    msg['From'] = f"Infosys Support <{EMAIL_ADDRESS}>"
    msg['To'] = to_email
    msg['Subject'] = "Infosys Springboard Portal - Verification Code"
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()
    msg['Reply-To'] = EMAIL_ADDRESS

    text_body = f"Your verification code for Infosys Springboard Portal is: {otp}\nThis code will expire in {OTP_EXPIRY_MINUTES} minutes.\nIf you did not request this code, please ignore this email."

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #F5F7FA; margin: 0; padding: 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background-color: #ffffff; border: 1px solid #E0E0E0; border-radius: 12px; padding: 30px; text-align: center; box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.05); }}
            .title {{ color: #0078D4; font-size: 22px; font-weight: bold; margin-bottom: 15px; }}
            .text {{ color: #323130; font-size: 15px; line-height: 1.5; margin-bottom: 20px; }}
            .otp-box {{ background-color: #F5F7FA; color: #0078D4; font-size: 28px; font-weight: bold; letter-spacing: 5px; padding: 15px 20px; border: 1px solid #0078D4; border-radius: 8px; display: inline-block; margin: 10px 0; }}
            .footer {{ color: #718096; font-size: 12px; margin-top: 25px; border-top: 1px solid #edf2f7; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="title">Infosys Springboard Portal</div>
            <div class="text">We received a request to reset your password for <b>{to_email}</b>. Please use the verification code below:</div>
            <div class="otp-box">{otp}</div>
            <div class="text">This code expires in <b>{OTP_EXPIRY_MINUTES} minutes</b>.</div>
            <div class="footer">If you did not request this code, you can safely ignore this email.<br>&copy; 2026 Infosys Springboard Portal.</div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        s.quit()
        return True, "sent"
    except Exception as e:
        return False, str(e)
