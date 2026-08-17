import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import json
import joblib
import sqlite3
import datetime
from typing import Dict, Tuple, Optional

# Import local engines (written to same directory in Colab)
from db_engine import (
    validate_email, validate_password, check_password_strength,
    create_jwt_token, decode_jwt_token, check_user_lockout,
    handle_failed_login, reset_failed_login, request_otp,
    send_otp_email, verify_otp, DB_FILE
)
from copilot_engine import AICopilot

# Page configuration
st.set_page_config(
    page_title="FreightQuote AI Enterprise",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling using CSS injection
st.markdown("""
<style>
    /* Main Layout Styling */
    .main {
        background: linear-gradient(135deg, #121824 0%, #0c0f17 100%);
        color: #e2e8f0;
    }
    
    /* Headers styling */
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    /* Card Styles */
    .metric-card {
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        margin-bottom: 20px;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 10px 24px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #60a5fa 0%, #2563eb 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
    }
    
    /* Inputs */
    .stTextInput>div>div>input {
        background-color: #1e293b !important;
        border: 1px solid #475569 !important;
        color: #f8fafc !important;
        border-radius: 8px !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
</style>
""", unsafe_allow_html=True)

# Helper function to get SQLite connection
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Helper function to check if the user is an admin
def is_admin(user_email: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE email = ?", (user_email,))
    row = cursor.fetchone()
    conn.close()
    return row and row['role'] == 'Admin'

# Session state initialization
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'auth_checked' not in st.session_state:
    st.session_state.auth_checked = False
if 'view' not in st.session_state:
    st.session_state.view = "login"  # login, signup, forgot_pw_question, forgot_pw_otp
if 'copilot_instance' not in st.session_state:
    # Initialize the copilot once to reuse
    st.session_state.copilot_instance = AICopilot()
    st.session_state.copilot_instance.load_model()

# Decode JWT token to maintain session
if st.session_state.token and not st.session_state.auth_checked:
    payload = decode_jwt_token(st.session_state.token)
    if payload:
        st.session_state.user_email = payload['email']
        st.session_state.user_role = payload['role']
        st.session_state.auth_checked = True
    else:
        st.session_state.token = None
        st.session_state.user_email = None
        st.session_state.user_role = None

# LOGOUT HANDLER
def handle_logout():
    st.session_state.token = None
    st.session_state.user_email = None
    st.session_state.user_role = None
    st.session_state.auth_checked = False
    st.session_state.view = "login"
    st.rerun()

# ----------------- VIEWS -----------------

# SIGNUP VIEW
def render_signup():
    st.markdown("<h1>🚚 Create a New Account</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Access FreightQuote AI enterprise analytics suites.</p>", unsafe_allow_html=True)
    
    with st.form("signup_form"):
        email = st.text_input("Corporate Email Address")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        # Security Question Setup
        question = st.selectbox(
            "Security Question (used for account recovery)",
            [
                "What is your mother's maiden name?",
                "What was the name of your first pet?",
                "What is your favorite color?",
                "In what city were you born?"
            ]
        )
        answer = st.text_input("Security Answer")
        
        # Real-time Password Strength meter inside the form (as description)
        strength = check_password_strength(password) if password else "Enter password"
        color = "#ef4444" if strength == "Weak" else ("#eab308" if strength == "Average" else "#22c55e")
        st.markdown(f"Password Strength: <b style='color: {color};'>{strength}</b>", unsafe_allow_html=True)
        
        submit_btn = st.form_submit_button("Sign Up")
        
        if submit_btn:
            if not validate_email(email):
                st.error("Invalid email address format.")
            elif not validate_password(password):
                st.error("Password must be at least 8 characters long and contain uppercase, lowercase, numbers, and special characters.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            elif not answer.strip():
                st.error("Security answer cannot be blank.")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                if cursor.fetchone():
                    st.error("Email is already registered.")
                    conn.close()
                else:
                    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    cursor.execute("""
                    INSERT INTO users (email, password_hash, security_question, security_answer, role, created_at)
                    VALUES (?, ?, ?, ?, 'User', ?)
                    """, (email, hashed, question, answer.strip(), datetime.datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                    st.success("Account created successfully! Please log in.")
                    st.session_state.view = "login"
                    time.sleep(1.5)
                    st.rerun()
                    
    if st.button("Already have an account? Log In"):
        st.session_state.view = "login"
        st.rerun()

# LOGIN VIEW
def render_login():
    st.markdown("<h1>🚚 Log In to FreightQuote AI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Enterprise Logistics Optimization & Smart Carrier Routing</p>", unsafe_allow_html=True)
    
    # Check if there is a local testing helper OTP code
    if os.path.exists("mock_otp.txt"):
        try:
            with open("mock_otp.txt", "r") as f:
                mock_data = f.read().strip()
                if ":" in mock_data:
                    m_email, m_otp = mock_data.split(":", 1)
                    st.info(f"💡 [Colab Helper] Last requested OTP for **{m_email}** is **{m_otp}**")
        except Exception:
            pass

    with st.form("login_form"):
        email = st.text_input("Corporate Email Address")
        password = st.text_input("Password", type="password")
        submit_btn = st.form_submit_button("Log In")
        
        if submit_btn:
            if not email or not password:
                st.error("Please enter email and password.")
            else:
                # Check Lockout Policy first
                locked, lock_msg = check_user_lockout(email)
                if locked:
                    st.error(lock_msg)
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT password_hash, role, id FROM users WHERE email = ?", (email,))
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row and bcrypt.checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8')):
                        # Success, reset attempts & logs JWT
                        reset_failed_login(email)
                        token = create_jwt_token(email, row['role'])
                        st.session_state.token = token
                        st.session_state.user_email = email
                        st.session_state.user_role = row['role']
                        st.session_state.auth_checked = True
                        st.success("Login successful!")
                        time.sleep(1.0)
                        st.rerun()
                    else:
                        # Fail attempts
                        fail_msg = handle_failed_login(email)
                        st.error(fail_msg)
                        
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Reset via Security Question"):
            st.session_state.view = "forgot_pw_question"
            st.rerun()
    with col2:
        if st.button("Reset via Gmail OTP"):
            st.session_state.view = "forgot_pw_otp"
            st.rerun()
    with col3:
        if st.button("Create Account (Sign Up)"):
            st.session_state.view = "signup"
            st.rerun()

# FORGOT PASSWORD - SECURITY QUESTION VIEW
def render_forgot_question():
    st.markdown("<h1>🔒 Password Reset via Security Question</h1>", unsafe_allow_html=True)
    
    email = st.text_input("Enter your registered email address")
    
    if email:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT security_question FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            st.error("Email address not found in system.")
        else:
            st.info(f"Question: {row['security_question']}")
            
            with st.form("security_question_reset_form"):
                answer = st.text_input("Your Security Answer")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")
                submit = st.form_submit_button("Reset Password")
                
                if submit:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT security_answer FROM users WHERE email = ?", (email,))
                    real_answer = cursor.fetchone()['security_answer']
                    
                    if answer.strip().lower() != real_answer.lower():
                        st.error("Incorrect security answer.")
                        conn.close()
                    elif not validate_password(new_password):
                        st.error("Password must be >= 8 characters and contain uppercase, lowercase, numbers, and symbols.")
                        conn.close()
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                        conn.close()
                    else:
                        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hashed, email))
                        conn.commit()
                        conn.close()
                        reset_failed_login(email) # Reset lockout attempts on password change
                        st.success("Password reset successful! Please login.")
                        st.session_state.view = "login"
                        time.sleep(1.5)
                        st.rerun()
                        
    if st.button("Cancel & Go Back"):
        st.session_state.view = "login"
        st.rerun()

# FORGOT PASSWORD - OTP VIEW
def render_forgot_otp():
    st.markdown("<h1>📧 Password Reset via OTP Code</h1>", unsafe_allow_html=True)
    
    email = st.text_input("Enter your registered email address")
    
    if 'otp_requested' not in st.session_state:
        st.session_state.otp_requested = False
        
    if email:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            st.error("Email address not found in system.")
        else:
            if st.button("Request OTP Code"):
                success, msg, code = request_otp(email)
                if success:
                    st.success(msg)
                    # Trigger background email delivery (SMTP or local mock log)
                    send_otp_email(email, code)
                    st.session_state.otp_requested = True
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(msg)
                    
            if st.session_state.otp_requested:
                # Helper for local testing to show OTP in UI
                if os.path.exists("mock_otp.txt"):
                    with open("mock_otp.txt", "r") as f:
                        mock_data = f.read().strip()
                        if ":" in mock_data:
                            m_email, m_otp = mock_data.split(":", 1)
                            if m_email == email:
                                st.info(f"💡 [Colab Helper] OTP verification code is: **{m_otp}**")
                                
                with st.form("otp_reset_form"):
                    code = st.text_input("Enter 6-digit OTP Code")
                    new_password = st.text_input("New Password", type="password")
                    confirm_password = st.text_input("Confirm New Password", type="password")
                    submit = st.form_submit_button("Reset Password")
                    
                    if submit:
                        # Verify OTP
                        valid, otp_msg = verify_otp(email, code)
                        if not valid:
                            st.error(otp_msg)
                        elif not validate_password(new_password):
                            st.error("Password must be >= 8 characters and contain uppercase, lowercase, numbers, and symbols.")
                        elif new_password != confirm_password:
                            st.error("Passwords do not match.")
                        else:
                            # Complete reset
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hashed, email))
                            # Delete used OTP
                            cursor.execute("DELETE FROM otps WHERE email = ?", (email,))
                            conn.commit()
                            conn.close()
                            reset_failed_login(email)
                            st.session_state.otp_requested = False
                            st.success("Password reset successful! Please login.")
                            st.session_state.view = "login"
                            time.sleep(1.5)
                            st.rerun()
                            
    if st.button("Cancel & Go Back"):
        st.session_state.otp_requested = False
        st.session_state.view = "login"
        st.rerun()

# USER DASHBOARD TAB - MODEL CARD VIEW
def render_model_card():
    st.markdown("<h2>📊 ML Model Specifications & Card</h2>", unsafe_allow_html=True)
    if os.path.exists("ml_model_card.md"):
        with open("ml_model_card.md", "r") as f:
            st.markdown(f.read())
    else:
        st.warning("Model card file not generated. Run model training pipeline cell in the notebook first.")

# USER DASHBOARD TAB - SHIPMENT CALCULATORS
def render_calculators():
    st.markdown("<h2>⚡ Predictive Shipments Optimizer</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Utilizes winner algorithms trained in the ML pipeline to predict pricing, route delay risks, and compliance.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    # File check
    pricing_model_exists = os.path.exists("best_pricing_model.joblib")
    route_model_exists = os.path.exists("best_route_delay_model.joblib")
    compliance_model_exists = os.path.exists("best_carrier_compliance_model.joblib")
    
    if not (pricing_model_exists and route_model_exists and compliance_model_exists):
        st.warning("⚠️ Warning: One or more ML models are missing. Ensure all notebook pipeline cells have run successfully.")
        
    with col1:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.markdown("<h3>💲 Price Estimator (Agent 1)</h3>", unsafe_allow_html=True)
        dist = st.number_input("Distance (miles)", min_value=1.0, value=500.0, step=50.0)
        weight = st.number_input("Weight (lbs)", min_value=10.0, value=15000.0, step=500.0)
        fuel = st.slider("Fuel Index Price ($/gal)", 1.0, 7.0, 3.5, 0.1)
        rating = st.slider("Carrier Quality Rating (1-5)", 1.0, 5.0, 4.2, 0.1)
        
        if st.button("Predict Pricing") and pricing_model_exists:
            scaler = joblib.load("pricing_scaler.joblib")
            model = joblib.load("best_pricing_model.joblib")
            
            features = pd.DataFrame([[dist, weight, fuel, rating]], columns=['distance_miles', 'weight_lbs', 'fuel_price_index', 'carrier_rating'])
            scaled_features = scaler.transform(features)
            predicted_price = model.predict(scaled_features)[0]
            st.markdown(f"<div style='font-size: 24px; font-weight: bold; color: #22c55e;'>Est Price: ${predicted_price:,.2f}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.markdown("<h3>⏰ Route Delay Predictor (Agent 2)</h3>", unsafe_allow_html=True)
        route_dist = st.number_input("Route Distance (miles)", min_value=1.0, value=650.0, step=50.0, key="r_dist")
        traffic = st.slider("Traffic Congestion Level", 0.0, 1.0, 0.4, 0.05)
        weather = st.slider("Extreme Weather Index", 0.0, 1.0, 0.2, 0.05)
        delay_rate = st.slider("Carrier Average Delay Rate", 0.0, 1.0, 0.15, 0.01)
        
        if st.button("Check Delay Risk") and route_model_exists:
            scaler = joblib.load("route_scaler.joblib")
            model = joblib.load("best_route_delay_model.joblib")
            
            features = pd.DataFrame([[route_dist, traffic, weather, delay_rate]], columns=['distance_miles', 'traffic_density', 'weather_severity', 'carrier_delay_rate'])
            scaled_features = scaler.transform(features)
            
            prediction = model.predict(scaled_features)[0]
            prob = model.predict_proba(scaled_features)[0][1] if hasattr(model, "predict_proba") else (0.95 if prediction == 1 else 0.05)
            
            color = "#ef4444" if prediction == 1 else "#22c55e"
            status = "DELAY RISK DETECTED" if prediction == 1 else "ON-TIME TRANSIT PROJECTION"
            st.markdown(f"<div style='font-weight: bold; color: {color};'>{status} ({prob*100:.1f}% probability)</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col3:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.markdown("<h3>🛡️ Carrier Compliance Check (Agent 3)</h3>", unsafe_allow_html=True)
        safety = st.slider("Safety Audit Score", 0.0, 100.0, 85.0, 1.0)
        ins = st.checkbox("Valid Insurance Status", value=True)
        maint = st.checkbox("Maintenance Inspections Pass", value=True)
        violations = st.number_input("Violations Count (Last 12mo)", min_value=0, value=0, step=1)
        years = st.number_input("Carrier Operating Years", min_value=0.5, value=5.0, step=0.5)
        
        if st.button("Evaluate Carrier Compliance") and compliance_model_exists:
            scaler = joblib.load("compliance_scaler.joblib")
            model = joblib.load("best_carrier_compliance_model.joblib")
            
            ins_val = 1 if ins else 0
            maint_val = 1 if maint else 0
            
            features = pd.DataFrame([[safety, ins_val, maint_val, violations, years]], 
                                    columns=['safety_score', 'insurance_validity', 'maintenance_checks_pass', 'violations_count', 'years_in_service'])
            scaled_features = scaler.transform(features)
            prediction = model.predict(scaled_features)[0]
            
            color = "#22c55e" if prediction == 1 else "#ef4444"
            status = "COMPLIANT / APPROVED" if prediction == 1 else "NON-COMPLIANT / HOLD"
            st.markdown(f"<b style='color: {color};'>{status}</b>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# USER DASHBOARD TAB - AI COPILOT
def render_copilot():
    st.markdown("<h2>🤖 AI Copilot (Qwen2.5-3B-Instruct)</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Ask recommendations based on real-time shipment constraints. Output is parsed in structured JSON format.</p>", unsafe_allow_html=True)
    
    # Check fallback/GPU status
    copilot = st.session_state.copilot_instance
    if copilot.gpu_available and copilot.model is not None:
        st.success("🟢 GPU Mode: Qwen2.5-3B Running in quantized 4-bit mode.")
    else:
        st.info("🔵 Fallback Mode: Running deterministic rules recommendations (CPU mode).")
        
    col1, col2 = st.columns([1, 1])
    
    with col1:
        dist = st.number_input("Distance", min_value=1.0, value=850.0, step=10.0, key="cp_dist")
        weight = st.number_input("Weight", min_value=1.0, value=22000.0, step=100.0, key="cp_w")
        traffic = st.slider("Traffic Level", 0.0, 1.0, 0.5, 0.05, key="cp_traf")
        weather = st.slider("Weather Severity", 0.0, 1.0, 0.3, 0.05, key="cp_wea")
        safety = st.slider("Safety Score", 0.0, 100.0, 90.0, 1.0, key="cp_saf")
        
        generate_btn = st.button("Generate Recommendation")
        
    with col2:
        if generate_btn:
            with st.spinner("Analyzing parameters and generating JSON recommendation..."):
                response_str = copilot.generate_recommendation(dist, weight, traffic, weather, safety)
                
                try:
                    res_json = json.loads(response_str)
                    
                    st.markdown("### Recommendation Summary")
                    st.json(res_json)
                    
                    # Styled presentation
                    price_col = "#22c55e" if res_json.get("price_status") == "Low" else ("#eab308" if res_json.get("price_status") == "Fair" else "#ef4444")
                    delay_col = "#22c55e" if res_json.get("delay_risk") == "Low" else ("#eab308" if res_json.get("delay_risk") == "Medium" else "#ef4444")
                    compliance_col = "#22c55e" if res_json.get("compliance_risk") == "Low" else ("#eab308" if res_json.get("compliance_risk") == "Medium" else "#ef4444")
                    
                    st.markdown(f"""
                    - **Pricing Verdict**: <span style='color: {price_col}; font-weight: bold;'>{res_json.get("price_status")}</span>
                    - **Transit Delay Risk**: <span style='color: {delay_col}; font-weight: bold;'>{res_json.get("delay_risk")}</span>
                    - **Compliance Risk**: <span style='color: {compliance_col}; font-weight: bold;'>{res_json.get("compliance_risk")}</span>
                    
                    **Copilot Assessment**:
                    > {res_json.get("recommendation_text")}
                    """, unsafe_allow_html=True)
                except Exception as e:
                    st.error("Failed to parse Copilot output as JSON.")
                    st.text(response_str)

# ADMIN DASHBOARD
def render_admin_dashboard():
    st.markdown("<h1>🛡️ Admin Administration Console</h1>", unsafe_allow_html=True)
    
    menu = ["View Users", "Add User", "Delete User", "Unlock User", "Assign Roles"]
    choice = st.sidebar.selectbox("Admin Controls", menu)
    
    if choice == "View Users":
        st.markdown("<h3>Registered Users</h3>", unsafe_allow_html=True)
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT id, email, role, is_locked, lock_until, failed_attempts, created_at FROM users", conn)
        conn.close()
        
        # Format timestamps
        df['lock_until'] = df['lock_until'].apply(lambda x: "Permanent" if x == 9999999999 else (datetime.datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S') if x > 0 else "None"))
        st.dataframe(df, use_container_width=True)
        
    elif choice == "Add User":
        st.markdown("<h3>Add User Manually</h3>", unsafe_allow_html=True)
        with st.form("admin_add_form"):
            new_email = st.text_input("Corporate Email")
            new_password = st.text_input("Temp Password", type="password")
            role_choice = st.selectbox("Role", ["User", "Admin"])
            question = st.text_input("Security Question", value="What is your favorite color?")
            answer = st.text_input("Security Answer", value="Blue")
            submit = st.form_submit_button("Add User")
            
            if submit:
                if not validate_email(new_email):
                    st.error("Invalid email address format.")
                elif not validate_password(new_password):
                    st.error("Password does not meet validation criteria.")
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = ?", (new_email,))
                    if cursor.fetchone():
                        st.error("User email already exists.")
                    else:
                        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        cursor.execute("""
                        INSERT INTO users (email, password_hash, security_question, security_answer, role, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (new_email, hashed, question, answer.strip(), role_choice, datetime.datetime.now().isoformat()))
                        conn.commit()
                        st.success(f"User {new_email} successfully added as {role_choice}!")
                    conn.close()
                    
    elif choice == "Delete User":
        st.markdown("<h3>Remove User Access</h3>", unsafe_allow_html=True)
        email_to_delete = st.text_input("User Email Address to Delete")
        
        if st.button("Delete User Account"):
            if email_to_delete == "admin@freightquote.ai":
                st.error("Cannot delete root Admin account.")
            elif email_to_delete == st.session_state.user_email:
                st.error("You cannot delete your own account.")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ?", (email_to_delete,))
                if not cursor.fetchone():
                    st.error("User email not found.")
                else:
                    cursor.execute("DELETE FROM users WHERE email = ?", (email_to_delete,))
                    conn.commit()
                    st.success(f"User {email_to_delete} was deleted.")
                conn.close()
                
    elif choice == "Unlock User":
        st.markdown("<h3>Administrative Lockout Release</h3>", unsafe_allow_html=True)
        email_to_unlock = st.text_input("Locked Email Address")
        
        if st.button("Unlock and Reset Login Attempts"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email_to_unlock,))
            if not cursor.fetchone():
                st.error("User not found.")
            else:
                cursor.execute("""
                UPDATE users 
                SET failed_attempts = 0, is_locked = 0, lock_until = 0 
                WHERE email = ?
                """, (email_to_unlock,))
                conn.commit()
                st.success(f"User {email_to_unlock} account locks have been administratively released.")
            conn.close()
            
    elif choice == "Assign Roles":
        st.markdown("<h3>Modify Role Clearance</h3>", unsafe_allow_html=True)
        email_to_change = st.text_input("Target Email Address")
        new_role = st.selectbox("Assign New Role", ["User", "Admin"])
        
        if st.button("Apply Role Modification"):
            if email_to_change == "admin@freightquote.ai":
                st.error("Cannot modify root Admin account.")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ?", (email_to_change,))
                if not cursor.fetchone():
                    st.error("User not found.")
                else:
                    cursor.execute("UPDATE users SET role = ? WHERE email = ?", (new_role, email_to_change))
                    conn.commit()
                    st.success(f"User {email_to_change} has been updated to {new_role}.")
                conn.close()


# ----------------- MAIN APP NAVIGATION -----------------

def main():
    if not st.session_state.token:
        # Show Auth Page depending on view
        if st.session_state.view == "signup":
            render_signup()
        elif st.session_state.view == "forgot_pw_question":
            render_forgot_question()
        elif st.session_state.view == "forgot_pw_otp":
            render_forgot_otp()
        else:
            render_login()
    else:
        # Main Dashboard Layout
        st.sidebar.markdown(f"### Logged in as:")
        st.sidebar.markdown(f"**{st.session_state.user_email}**")
        st.sidebar.markdown(f"Security Clearance: `{st.session_state.user_role}`")
        
        # Navigation
        nav_options = ["User Dashboard", "Admin Console"] if st.session_state.user_role == "Admin" else ["User Dashboard"]
        page = st.sidebar.radio("Navigation Pane", nav_options)
        
        if st.sidebar.button("Logout"):
            handle_logout()
            
        if page == "User Dashboard":
            st.markdown("<h1>🚚 FreightQuote AI Enterprise Dashboard</h1>", unsafe_allow_html=True)
            
            sub_tabs = st.tabs(["⚡ Optimize Shipments", "🤖 AI Copilot Assistant", "📊 ML Model Specs (Model Card)"])
            
            with sub_tabs[0]:
                render_calculators()
                
            with sub_tabs[1]:
                render_copilot()
                
            with sub_tabs[2]:
                render_model_card()
                
        elif page == "Admin Console" and st.session_state.user_role == "Admin":
            render_admin_dashboard()

if __name__ == "__main__":
    main()
