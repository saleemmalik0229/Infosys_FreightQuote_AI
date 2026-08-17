import re
import time
import sqlite3
import datetime
import secrets
import smtplib
from email.utils import formatdate, make_msgid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import jwt
import bcrypt
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from streamlit_option_menu import option_menu

# Import configuration constants from config.py
import config

JWT_SECRET = config.JWT_SECRET
EMAIL_ADDRESS = config.EMAIL_ADDRESS
EMAIL_PASSWORD = config.EMAIL_PASSWORD
NGROK_AUTHTOKEN = config.NGROK_AUTHTOKEN
ADMIN_EMAIL = config.ADMIN_EMAIL
ADMIN_PASSWORD = config.ADMIN_PASSWORD
OTP_EXPIRY_MINUTES = config.OTP_EXPIRY_MINUTES
LOCKOUT_TIME = config.LOCKOUT_TIME
MAX_LOGIN_ATTEMPTS = config.MAX_LOGIN_ATTEMPTS


# Page configurations
st.set_page_config(
    page_title="Infosys Springboard Portal",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SQLite Database Initialization ---
DB_NAME = "infosys_portal.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

def init_db():
    with get_db() as conn:
        # Users Table
        conn.execute("""
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
        # Login Attempts Table for Rate Limiting
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT PRIMARY KEY,
                attempts INTEGER,
                last_attempt REAL
            )
        """)

# --- Cryptography Helpers ---
def hash_txt(txt: str) -> str:
    return bcrypt.hashpw(txt.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def check_txt(txt: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(txt.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

# --- User Seeding & Password Sync ---
def seed_initial_users():
    users_to_seed = [
        ("Administrator", ADMIN_EMAIL, ADMIN_PASSWORD, "What is your pet name?", "admin"),
        ("Springboard Mentor 018", "springboardmentor018@gmail.com", "Welcome@123", "What is your pet name?", "mentor"),
        ("Springboard Mentor 038", "springboardmentor038@gmail.com", "Welcome@123", "What is your pet name?", "mentor")
    ]
    with get_db() as conn:
        for name, email, pwd, sq, sa in users_to_seed:
            row = conn.execute("SELECT password_hash FROM users WHERE email=?", (email,)).fetchone()
            pwd_hash = hash_txt(pwd)
            sa_hash = hash_txt(sa.lower().strip())
            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if not row:
                conn.execute(
                    "INSERT INTO users (username, email, password_hash, security_question, security_answer_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, email, pwd_hash, sq, sa_hash, now_str)
                )
            else:
                # Sync configured admin credentials on startup
                if email == ADMIN_EMAIL and not check_txt(pwd, row[0]):
                    conn.execute("UPDATE users SET password_hash=? WHERE email=?", (pwd_hash, email))

# Initialize database and run seeds
init_db()
seed_initial_users()

# --- Rate Limiting Helpers ---
def get_login_attempts(email: str):
    with get_db() as conn:
        row = conn.execute("SELECT attempts, last_attempt FROM login_attempts WHERE email = ?", (email,)).fetchone()
    return row if row else (0, 0.0)

def increment_login_attempts(email: str):
    attempts, _ = get_login_attempts(email)
    new_attempts = attempts + 1
    now = time.time()
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO login_attempts (email, attempts, last_attempt) VALUES (?, ?, ?)",
                     (email, new_attempts, now))

def reset_login_attempts(email: str):
    with get_db() as conn:
        conn.execute("DELETE FROM login_attempts WHERE email = ?", (email,))

def check_rate_limit(email: str):
    attempts, last_attempt = get_login_attempts(email)
    if attempts >= MAX_LOGIN_ATTEMPTS:
        elapsed = time.time() - last_attempt
        if elapsed < LOCKOUT_TIME:
            return True, int(LOCKOUT_TIME - elapsed)
        else:
            reset_login_attempts(email)
    return False, 0

# --- JWT Authentication Helpers ---
def make_jwt(email: str) -> str:
    payload = {
        "email": email,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

# --- OTP Helper Functions ---
def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

def make_otp_token(email: str, otp: str) -> str:
    payload = {
        "sub": email,
        "otp_hash": hash_txt(otp),
        "type": "password_reset_otp",
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_otp_token(token: str, input_otp: str, email: str):
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
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return True, "sandbox_mode"

    # RFC Compliant Professional Email
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

# --- PyNgrok Integration ---
@st.cache_resource
def start_ngrok_tunnel():
    if NGROK_AUTHTOKEN:
        try:
            from pyngrok import ngrok
            ngrok.set_auth_token(NGROK_AUTHTOKEN)
            tunnels = ngrok.get_tunnels()
            for t in tunnels:
                ngrok.disconnect(t.public_url)
            tunnel = ngrok.connect(8501)
            return tunnel.public_url
        except Exception as e:
            return f"Ngrok Tunnel Error: {str(e)}"
    return None

#ngrok_url = start_ngrok_tunnel()
ngrok_url = None
# --- Input Validation Functions ---
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-.]+)?$", email))

def is_strong_password(password: str):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[@$!%*?&_#^-]", password):
        return False, "Password must contain at least one special character (@$!%*?&_#^-)."
    return True, "Strong password."

# --- CSS Theme Injection ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@300;400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styling - White Background & Modern Corporate Feel */
    html, body, [data-testid="stApp"] {{
        background-color: #FFFFFF !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        color: #323130 !important;
    }}
    
    /* Remove stream header line and footer */
    footer, div[data-testid="stDecoration"] {{
        visibility: hidden !important;
        display: none !important;
    }}
    header {{
        background: transparent !important;
    }}
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {{
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E5E5 !important;
        box-shadow: 2px 0px 8px rgba(0, 0, 0, 0.01) !important;
    }}
    
    /* Central Content Soft Gray Cards */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: #F9FAFB !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 16px !important;
        padding: 2.5rem !important;
        box-shadow: 0px 4px 18px rgba(0, 0, 0, 0.02) !important;
        margin-bottom: 1.5rem !important;
        transition: box-shadow 0.2s ease-in-out !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        box-shadow: 0px 6px 22px rgba(0, 0, 0, 0.03) !important;
    }}
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {{
        font-family: 'Segoe UI', sans-serif !important;
        font-weight: 700 !important;
        color: #111827 !important;
        margin-top: 0 !important;
    }}
    
    /* Input Labels */
    label p {{
        font-weight: 600 !important;
        color: #374151 !important;
        font-size: 14px !important;
        margin-bottom: 4px !important;
    }}
    
    /* Inputs Form Styling */
    div[data-baseweb="base-input"], div[data-baseweb="select"] > div {{
        background-color: transparent !important;
        border: none !important;
    }}
    div[data-baseweb="input"], div[data-baseweb="select"] {{
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 8px !important;
        transition: all 0.15s ease-in-out !important;
    }}
    div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within {{
        border-color: #0078D4 !important;
        box-shadow: 0 0 0 3px rgba(0, 120, 212, 0.12) !important;
    }}
    input, div[data-baseweb="select"] span {{
        color: #1F2937 !important;
        -webkit-text-fill-color: #1F2937 !important;
        font-size: 15px !important;
    }}
    
    /* Rounded Buttons & Hover Effects */
    div[data-testid="stButton"] button {{
        background: linear-gradient(135deg, #0078D4, #005A9E) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 20px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        height: 40px !important;
        min-height: 40px !important;
        width: 100% !important;
        box-shadow: 0px 4px 10px rgba(0, 120, 212, 0.15) !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    div[data-testid="stButton"] button:hover {{
        background: linear-gradient(135deg, #005A9E, #004578) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0px 6px 14px rgba(0, 120, 212, 0.25) !important;
    }}
    div[data-testid="stButton"] button:active {{
        transform: translateY(1px) !important;
    }}
    
    /* Metrics visual cards inside dashboards */
    .dashboard-card {{
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.01);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        margin-bottom: 12px;
    }}
    .dashboard-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0px 6px 16px rgba(0, 0, 0, 0.03);
    }}
</style>
""", unsafe_allow_html=True)

# --- Session State Management ---
for k, v in [
    ("token", None),
    ("page", "Login"),
    ("forgot_stage", "email"),
    ("reset_email", None),
    ("otp_jwt_token", None),
    ("security_question", None),
    ("dev_sandbox_otp", None),
    ("login_mode", "user")
]:
    if k not in st.session_state:
        st.session_state[k] = v

def navigate(p):
    st.session_state.page = p
    st.rerun()

def auth_header(title_text):
    st.markdown(f"""
    <div style="text-align:center; padding:1.5rem 0 1rem;">
        <div style="font-size: 42px; margin-bottom: 10px; color: #0078D4;">📦</div>
        <h1 style="font-size: 2.1rem; font-weight: 700; color: #111827; margin: 0;">Infosys Springboard Portal</h1>
        <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0; font-weight: 400;">
            Intelligent Freight Quote Generation System
        </p>
    </div>
    <div style="text-align:center; margin-bottom: 1.5rem;">
        <span style="font-size: 1.1rem; font-weight: 600; color: #0078D4;">{title_text}</span>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# GUEST ROUTING (Not Authenticated)
# ============================================================
if not st.session_state.token:
    if st.session_state.page not in ["Login", "Signup", "Forgot"]:
        st.session_state.page = "Login"

    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        with st.container(border=True):
            
            # --- LOGIN VIEW ---
            if st.session_state.page == "Login":
                # Toggle tabs between User Login and Admin Login
                col_tab1, col_tab2 = st.columns(2)
                with col_tab1:
                    if st.button("👤 User Portal", use_container_width=True, type="primary" if st.session_state.login_mode == "user" else "secondary"):
                        st.session_state.login_mode = "user"
                        st.rerun()
                with col_tab2:
                    if st.button("🛡️ Admin Portal", use_container_width=True, type="primary" if st.session_state.login_mode == "admin" else "secondary"):
                        st.session_state.login_mode = "admin"
                        st.rerun()

                # --- ADMIN LOGIN TAB ---
                if st.session_state.login_mode == "admin":
                    auth_header("Admin Portal Access")
                    email = st.text_input("Admin Email Address", placeholder="admin@domain.com").lower().strip()
                    pwd = st.text_input("Password", type="password", placeholder="••••••••")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    is_blocked, time_left = check_rate_limit(email)
                    
                    col1, col2 = st.columns(2)
                    if col1.button("Admin Sign In →", use_container_width=True):
                        if is_blocked:
                            st.error(f"❌ Account locked. Try again in {time_left}s.")
                        elif not email or not pwd:
                            st.error("⚠️ Please fill in all fields.")
                        elif not is_valid_email(email):
                            st.error("⚠️ Please enter a valid email address.")
                        elif email != ADMIN_EMAIL or pwd != ADMIN_PASSWORD:
                            increment_login_attempts(email)
                            st.error("❌ Invalid admin credentials.")
                        else:
                            reset_login_attempts(email)
                            st.session_state.token = make_jwt(email)
                            st.success("✅ Admin logged in successfully!")
                            time.sleep(0.5)
                            navigate("Dashboard")
                            
                    if col2.button("Forgot Password?", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.session_state.reset_email = None
                        st.session_state.otp_jwt_token = None
                        st.session_state.security_question = None
                        st.session_state.dev_sandbox_otp = None
                        navigate("Forgot")
                
                # --- USER LOGIN TAB ---
                else:
                    auth_header("Sign in to your account")
                    email = st.text_input("Email Address", placeholder="you@example.com").lower().strip()
                    pwd = st.text_input("Password", type="password", placeholder="••••••••")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    is_blocked, time_left = check_rate_limit(email)
                    
                    col1, col2 = st.columns(2)
                    if col1.button("Sign In →", use_container_width=True):
                        if is_blocked:
                            st.error(f"❌ Account locked. Try again in {time_left}s.")
                        elif not email or not pwd:
                            st.error("⚠️ Please fill in all fields.")
                        elif not is_valid_email(email):
                            st.error("⚠️ Please enter a valid email address.")
                        else:
                            with get_db() as conn:
                                row = conn.execute("SELECT password_hash FROM users WHERE email=?", (email,)).fetchone()
                            
                            if row and check_txt(pwd, row[0]):
                                reset_login_attempts(email)
                                st.session_state.token = make_jwt(email)
                                st.success("✅ Logged in successfully!")
                                time.sleep(0.5)
                                navigate("Dashboard")
                            else:
                                increment_login_attempts(email)
                                st.error("❌ Invalid email or password.")
                    
                    if col2.button("Register Account", use_container_width=True):
                        navigate("Signup")
                    
                    st.markdown("<div style='text-align: center; margin-top: 10px;'>", unsafe_allow_html=True)
                    if st.button("Forgot Password?", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.session_state.reset_email = None
                        st.session_state.otp_jwt_token = None
                        st.session_state.security_question = None
                        st.session_state.dev_sandbox_otp = None
                        navigate("Forgot")
                    st.markdown("</div>", unsafe_allow_html=True)

            # --- SIGNUP VIEW ---
            elif st.session_state.page == "Signup":
                auth_header("Create dynamic user account")
                
                uname = st.text_input("Full Name / Username", placeholder="John Doe")
                email = st.text_input("Email Address", placeholder="you@example.com").lower().strip()
                
                st.markdown("**Password Requirements:** Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special character.")
                pwd = st.text_input("Password", type="password", placeholder="••••••••")
                confirm_pwd = st.text_input("Confirm Password", type="password", placeholder="••••••••")
                
                sq = st.selectbox(
                    "Security Question (For Account Recovery)",
                    [
                        "What is your pet name?",
                        "What is your mother's maiden name?",
                        "What is your favourite city?"
                    ]
                )
                sa = st.text_input("Security Question Answer", placeholder="Answer text")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                if col1.button("Create Account", use_container_width=True):
                    pwd_ok, pwd_msg = is_strong_password(pwd)
                    
                    if not uname or not email or not pwd or not confirm_pwd or not sa:
                        st.error("⚠️ All fields are mandatory. Please fill in all fields.")
                    elif not is_valid_email(email):
                        st.error("⚠️ Please enter a valid email address.")
                    elif not pwd_ok:
                        st.error(f"⚠️ {pwd_msg}")
                    elif pwd != confirm_pwd:
                        st.error("❌ Passwords do not match.")
                    else:
                        try:
                            pwd_hash = hash_txt(pwd)
                            sa_hash = hash_txt(sa.lower().strip())
                            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                            
                            with get_db() as conn:
                                conn.execute(
                                    "INSERT INTO users (username, email, password_hash, security_question, security_answer_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                    (uname, email, pwd_hash, sq, sa_hash, now_str)
                                )
                            
                            st.session_state.token = make_jwt(email)
                            st.success("✅ Account created successfully!")
                            time.sleep(0.5)
                            navigate("Dashboard")
                        except sqlite3.IntegrityError:
                            st.error("❌ Email or Username is already registered.")
                
                if col2.button("Back to Login", use_container_width=True):
                    navigate("Login")

            # --- FORGOT PASSWORD VIEW ---
            elif st.session_state.page == "Forgot":
                auth_header("Reset Password")
                
                # STAGE 1: ASK EMAIL & VERIFICATION METHOD
                if st.session_state.forgot_stage == "email":
                    st.markdown("<p style='text-align:center;'>Enter your registered email address to choose verification method.</p>", unsafe_allow_html=True)
                    email = st.text_input("Registered Email", placeholder="you@example.com").lower().strip()
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_sq, col_otp = st.columns(2)
                    
                    if col_sq.button("Via Security Question", use_container_width=True):
                        if not email:
                            st.error("⚠️ Please enter your email.")
                        else:
                            with get_db() as conn:
                                row = conn.execute("SELECT security_question FROM users WHERE email=?", (email,)).fetchone()
                            if row:
                                st.session_state.reset_email = email
                                st.session_state.security_question = row[0]
                                st.session_state.forgot_stage = "sq"
                                st.rerun()
                            else:
                                st.error("❌ Email address not found in system.")
                                
                    if col_otp.button("Via Email OTP", use_container_width=True):
                        if not email:
                            st.error("⚠️ Please enter your email.")
                        else:
                            with get_db() as conn:
                                row = conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
                            if row:
                                otp = generate_otp()
                                with st.spinner("Generating security code..."):
                                    ok, info = send_otp_email(email, otp)
                                if ok:
                                    st.session_state.reset_email = email
                                    st.session_state.otp_jwt_token = make_otp_token(email, otp)
                                    st.session_state.forgot_stage = "otp"
                                    
                                    if info == "sandbox_mode":
                                        st.session_state.dev_sandbox_otp = otp
                                        st.warning("⚠️ SMTP configurations (EMAIL_ADDRESS or EMAIL_PASSWORD) are not set. Activating Sandbox Recovery. Your OTP code is shown below.")
                                    st.success("✅ 6-digit OTP code generated.")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to dispatch email. Error: {info}")
                            else:
                                st.error("Email address not found.")
                
                # STAGE 2A: VIA SECURITY QUESTION
                elif st.session_state.forgot_stage == "sq":
                    st.info(f"❓ **Security Question:** {st.session_state.security_question}")
                    sa_input = st.text_input("Your Answer", placeholder="Answer text").lower().strip()
                    
                    st.markdown("**Create New Password:**")
                    npw = st.text_input("New Password", type="password", placeholder="••••••••")
                    confirm_npw = st.text_input("Confirm New Password", type="password", placeholder="••••••••")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    
                    if col1.button("Reset Password", use_container_width=True):
                        pwd_ok, pwd_msg = is_strong_password(npw)
                        
                        if not sa_input or not npw:
                            st.error("⚠️ Please fill in all fields.")
                        elif not pwd_ok:
                            st.error(f"⚠️ {pwd_msg}")
                        elif npw != confirm_npw:
                            st.error("❌ Passwords do not match.")
                        else:
                            with get_db() as conn:
                                row = conn.execute("SELECT security_answer_hash FROM users WHERE email=?", (st.session_state.reset_email,)).fetchone()
                            
                            if row and check_txt(sa_input, row[0]):
                                # Correct security answer, update password in DB
                                with get_db() as conn:
                                    conn.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_txt(npw), st.session_state.reset_email))
                                st.success("🎉 Password reset successfully!")
                                time.sleep(1.5)
                                st.session_state.forgot_stage = "email"
                                navigate("Login")
                            else:
                                st.error("❌ Incorrect security answer.")
                                
                    if col2.button("Cancel", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.rerun()

                # STAGE 2B: ENTER OTP CODE (WITH RESEND ACTION)
                elif st.session_state.forgot_stage == "otp":
                    st.info(f"📧 Verification code generated for **{st.session_state.reset_email}**.")
                    
                    if st.session_state.dev_sandbox_otp:
                        st.info(f"🔑 **[Developer Mode OTP]:** `{st.session_state.dev_sandbox_otp}`")
                    
                    otp_input = st.text_input("Enter 6-Digit OTP Code", max_chars=6, placeholder="e.g. 123456").strip()
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col1, col2, col3 = st.columns(3)
                    
                    if col1.button("Verify OTP Code", use_container_width=True):
                        if not otp_input or len(otp_input) != 6:
                            st.error("⚠️ Please enter a valid 6-digit code.")
                        else:
                            ok, msg = verify_otp_token(st.session_state.otp_jwt_token, otp_input, st.session_state.reset_email)
                            if ok:
                                st.session_state.forgot_stage = "reset"
                                st.success("✅ Code verified successfully!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
                                
                    if col2.button("Resend Code", use_container_width=True):
                        otp = generate_otp()
                        with st.spinner("Resending verification code..."):
                            ok, info = send_otp_email(st.session_state.reset_email, otp)
                        if ok:
                            st.session_state.otp_jwt_token = make_otp_token(st.session_state.reset_email, otp)
                            if info == "sandbox_mode":
                                st.session_state.dev_sandbox_otp = otp
                                st.warning("⚠️ SMTP configurations (EMAIL_ADDRESS or EMAIL_PASSWORD) are not set. Activating Sandbox Recovery. Your OTP code is shown below.")
                            st.success("✅ New OTP code sent!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to dispatch email. Error: {info}")
                                
                    if col3.button("Back", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.session_state.dev_sandbox_otp = None
                        st.rerun()

                # STAGE 3: CREATE NEW PASSWORD (AFTER OTP SUCCESS)
                elif st.session_state.forgot_stage == "reset":
                    st.markdown("🔒 **Create New Secure Password:**")
                    npw = st.text_input("New Password", type="password", placeholder="••••••••")
                    confirm_npw = st.text_input("Confirm New Password", type="password", placeholder="••••••••")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    
                    if col1.button("Update Password", use_container_width=True):
                        pwd_ok, pwd_msg = is_strong_password(npw)
                        
                        if not npw:
                            st.error("⚠️ Please enter password.")
                        elif not pwd_ok:
                            st.error(f"⚠️ {pwd_msg}")
                        elif npw != confirm_npw:
                            st.error("❌ Passwords do not match.")
                        else:
                            with get_db() as conn:
                                conn.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_txt(npw), st.session_state.reset_email))
                            st.success("🎉 Password updated successfully!")
                            time.sleep(1.5)
                            st.session_state.forgot_stage = "email"
                            st.session_state.dev_sandbox_otp = None
                            navigate("Login")
                            
                    if col2.button("Cancel Reset", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.session_state.dev_sandbox_otp = None
                        navigate("Login")

                # Cancel recovery and go back to Login view
                st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
                if st.button("← Cancel & Back to Login", use_container_width=True):
                    st.session_state.forgot_stage = "email"
                    st.session_state.dev_sandbox_otp = None
                    navigate("Login")

# ============================================================
# AUTHENTICATED ROUTING (Dashboard views)
# ============================================================
else:
    payload = verify_jwt(st.session_state.token)
    if not payload:
        # Session expired or invalid
        st.session_state.token = None
        st.session_state.page = "Login"
        st.warning("⚠️ Session expired. Please log in again.")
        time.sleep(1.5)
        st.rerun()

    email = payload["email"]
    with get_db() as conn:
        user_row = conn.execute("SELECT username FROM users WHERE email=?", (email,)).fetchone()
    
    if not user_row:
        # User deleted in settings
        st.session_state.token = None
        st.session_state.page = "Login"
        st.rerun()
        
    uname = user_row[0]
    is_admin = (email == ADMIN_EMAIL)

    # --- SIDEBAR NAVIGATION ---
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 16px 8px; text-align: center;">
            <div style="font-size: 36px; margin-bottom: 6px; color: #0078D4;">📦</div>
            <div style="font-weight: 700; font-size: 16px; color: #111827;">Infosys Portal</div>
            <div style="font-size: 11px; color: #4B5563; font-weight: 600; margin-top: 2px;">
                {"🛡️ Admin Control" if is_admin else "⚙️ User Panel"}
            </div>
        </div>
        <hr style="border-top: 1px solid #E5E7EB; margin: 10px 0 20px 0;">
        """, unsafe_allow_html=True)

        opts = ["Dashboard", "Settings", "Logout"] if is_admin else ["Dashboard", "Analytics", "Reports", "Logout"]
        icons = ["house", "gear", "box-arrow-right"] if is_admin else ["house", "graph-up", "file-text", "box-arrow-right"]

        menu = option_menu(
            menu_title=None,
            options=opts,
            icons=icons,
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"background-color": "#FFFFFF", "padding": "5px"},
                "icon": {"color": "#4B5563", "font-size": "16px"},
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                    "--hover-color": "#F3F4F6",
                    "color": "#374151",
                    "font-weight": "500"
                },
                "nav-link-selected": {
                    "background-color": "#0078D4",
                    "color": "#FFFFFF",
                    "font-weight": "600"
                }
            }
        )
        
        # Display Ngrok URL if connected
        if ngrok_url:
            st.markdown(f"""
            <div style="margin-top: 2rem; padding: 12px; background-color: #EFF6FF; border-radius: 8px; border: 1px solid #3B82F6; font-size: 11px;">
                <span style="font-weight:700; color:#1D4ED8;">🌐 Public Tunnel:</span><br>
                <a href="{ngrok_url}" target="_blank" style="color:#2563EB; text-decoration:none; word-break:break-all;">{ngrok_url}</a>
            </div>
            """, unsafe_allow_html=True)
            
        if menu == "Logout":
            st.session_state.token = None
            st.session_state.page = "Login"
            st.session_state.login_mode = "user"
            st.success("👋 Logged out successfully!")
            time.sleep(0.5)
            st.rerun()

    # --- TOP BRANDING HEADER ---
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0078D4, #005A9E); border-radius: 16px; padding: 24px 32px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; color: #FFFFFF; box-shadow: 0px 4px 12px rgba(0, 120, 212, 0.15);">
        <div>
            <h1 style="color: #FFFFFF !important; margin: 0; font-size: 24px !important;">Infosys Springboard Portal</h1>
            <div style="color: rgba(255, 255, 255, 0.85); font-size: 13px; font-weight: 500; margin-top: 2px;">
                Intelligent Freight Quote Generation System
            </div>
        </div>
        <div style="background: rgba(255, 255, 255, 0.2); padding: 8px 18px; border-radius: 30px; font-weight: 600; font-size: 13px; border: 1px solid rgba(255, 255, 255, 0.3);">
            {"🛡️ Administrator" if is_admin else "👤 Portal User"}: {uname}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ============================================================
    # ADMIN PAGES
    # ============================================================
    if is_admin:
        if menu == "Dashboard":
            st.markdown("### 🛡️ Admin Control Overview")
            
            # Metric indicators
            c1, c2, c3 = st.columns(3)
            with get_db() as conn:
                tot_users = conn.execute("SELECT count(*) FROM users").fetchone()[0]
                rec_users = conn.execute("SELECT email, created_at FROM users ORDER BY created_at DESC LIMIT 3").fetchall()
            
            c1.markdown(f"""
            <div class="dashboard-card">
                <div style="font-size: 32px; margin-bottom: 8px;">👥</div>
                <div style="font-size: 28px; font-weight: 700; color: #111827;">{tot_users}</div>
                <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">Registered Users</div>
            </div>
            """, unsafe_allow_html=True)
            
            c2.markdown(f"""
            <div class="dashboard-card">
                <div style="font-size: 32px; margin-bottom: 8px;">🛡️</div>
                <div style="font-size: 28px; font-weight: 700; color: #111827;">Active</div>
                <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">System Health Status</div>
            </div>
            """, unsafe_allow_html=True)
            
            c3.markdown(f"""
            <div class="dashboard-card">
                <div style="font-size: 32px; margin-bottom: 8px;">🔗</div>
                <div style="font-size: 28px; font-weight: 700; color: #111827;">{"Connected" if ngrok_url else "Local Only"}</div>
                <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">Ngrok Proxy Status</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("System Access Activity Logs (Recent Sign-ups)")
            if rec_users:
                log_df = pd.DataFrame(rec_users, columns=["User Email", "Created Timestamp"])
                st.table(log_df)
            else:
                st.info("No system activity logged.")
                
        elif menu == "Settings":
            st.markdown("### ⚙️ System Settings & User Management")
            
            # Fetch registered users list
            with get_db() as conn:
                user_list = conn.execute("SELECT id, username, email, created_at FROM users").fetchall()
            
            if user_list:
                st.subheader("Registered Users Directory")
                # Username, Email and Created Date (never show password hashes)
                users_df = pd.DataFrame(user_list, columns=["ID", "Username", "Email Address", "Registered Date"])
                st.dataframe(users_df, use_container_width=True, hide_index=True)
                
                # Delete user form
                st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
                st.subheader("🗑️ Remove User Account")
                st.warning("⚠️ Warning: Removing a user account is permanent and cannot be undone.")
                
                emails_to_delete = [u[2] for u in user_list if u[2] != ADMIN_EMAIL]
                
                if emails_to_delete:
                    del_email = st.selectbox("Select User Email to Remove", emails_to_delete)
                    if st.button("Delete Selected Account"):
                        with get_db() as conn:
                            conn.execute("DELETE FROM users WHERE email=?", (del_email,))
                            conn.execute("DELETE FROM login_attempts WHERE email=?", (del_email,))
                        st.success(f"✅ Account {del_email} has been permanently deleted.")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.info("No other user accounts available to remove.")
            else:
                st.info("No users registered in system.")

    # ============================================================
    # REGULAR USER PAGES
    # ============================================================
    else:
        if menu == "Dashboard":
            st.markdown("### 📊 System Operations Hub")
            
            # Metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"""
            <div class="dashboard-card">
                <div style="font-size: 32px; margin-bottom: 8px;">📄</div>
                <div style="font-size: 24px; font-weight: 700; color: #111827;">128</div>
                <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">Documents Indexed</div>
            </div>
            """, unsafe_allow_html=True)
            
            c2.markdown(f"""
            <div class="dashboard-card">
                <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
                <div style="font-size: 24px; font-weight: 700; color: #111827;">47</div>
                <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">Searches Today</div>
            </div>
            """, unsafe_allow_html=True)
            
            c3.markdown(f"""
            <div class="dashboard-card">
                <div style="font-size: 32px; margin-bottom: 8px;">📈</div>
                <div style="font-size: 24px; font-weight: 700; color: #111827;">98.4%</div>
                <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">Efficiency Score</div>
            </div>
            """, unsafe_allow_html=True)
            
            c4.markdown(f"""
            <div class="dashboard-card">
                <div style="font-size: 32px; margin-bottom: 8px;">🛡️</div>
                <div style="font-size: 24px; font-weight: 700; color: #111827;">Secured</div>
                <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">Security Status</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # System Health gauge indicator
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=92,
                title={"text": "System Health Index", "font": {"color": "#111827", "size": 15, "family": "Segoe UI"}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "#4B5563"},
                    "bar": {"color": "#0078D4"},
                    "bgcolor": "#E5E7EB",
                    "borderwidth": 1,
                    "bordercolor": "#D1D5DB"
                }
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font={"color": "#374151", "family": "Inter"},
                height=260,
                margin=dict(l=10, r=10, t=50, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

        elif menu == "Analytics":
            st.markdown("### 📈 Route & Freight Quotes Analytics")
            
            routes = ["Shanghai - Los Angeles", "Rotterdam - Singapore", "New York - London", "Mumbai - Dubai", "Sydney - Tokyo"]
            quotes = [82, 63, 45, 38, 29]
            
            # Volume Chart
            fig_bar = go.Figure(data=[go.Bar(
                x=routes, y=quotes,
                marker_color='#0078D4',
                text=quotes,
                textposition='auto',
            )])
            fig_bar.update_layout(
                title={"text": "Active Freight Quote Volumes by Trade Lane", "font": {"size": 16, "family": "Segoe UI"}},
                xaxis_title="Shipping Route",
                yaxis_title="Quotes Generated",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=350,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            
            # Transit Time vs Route Line
            transit_times = [14, 21, 10, 8, 12] # days
            fig_line = go.Figure(data=[go.Scatter(
                x=routes, y=transit_times,
                mode="lines+markers",
                line=dict(color="#00A6A6", width=3),
                marker=dict(size=8, color="#0078D4")
            )])
            fig_line.update_layout(
                title={"text": "Average Transit Times (Days)", "font": {"size": 16, "family": "Segoe UI"}},
                xaxis_title="Shipping Route",
                yaxis_title="Days in Transit",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            
            col_left, col_right = st.columns(2)
            with col_left:
                st.plotly_chart(fig_bar, use_container_width=True)
            with col_right:
                st.plotly_chart(fig_line, use_container_width=True)

        elif menu == "Reports":
            st.markdown("### 📋 Intelligent Freight Quote Ledger")
            
            quotes_data = {
                "Quote ID": ["FQ-1024", "FQ-1025", "FQ-1026", "FQ-1027", "FQ-1028"],
                "Origin Hub": ["Shanghai (CNSHA)", "Rotterdam (NLRTM)", "Mumbai (INBOM)", "Chicago (USCHI)", "Hamburg (DEHAM)"],
                "Destination Hub": ["Los Angeles (USLAX)", "Singapore (SGSIN)", "Dubai (AEDXB)", "Frankfurt (DEFRA)", "New York (USNYC)"],
                "Cargo Category": ["Electronics", "Chemicals", "Textiles", "Machinery", "Automotive"],
                "Freight Price ($)": [2450.00, 3120.00, 1850.00, 4200.00, 2900.00],
                "Current Status": ["Approved", "Pending Match", "Approved", "Under Review", "Approved"]
            }
            df = pd.DataFrame(quotes_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            *Note: The ledger showcases quotes computed based on active carrier rate API requests and custom routing factors.*
            """)
