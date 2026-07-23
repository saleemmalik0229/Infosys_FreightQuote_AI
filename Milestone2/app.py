import sys
import time
import json
import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_option_menu import option_menu

# Resolve parent and module directories
M2_DIR = Path(__file__).resolve().parent
ROOT_DIR = M2_DIR.parent
for p in [str(M2_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import config
import db
import auth
import ui_theme
import admin_dash
from train_ml_freight import FreightQuoteMLSuite
from llm_engine_freight import LogisticsLLMEngine

# Configuration Constants
ADMIN_EMAIL = config.ADMIN_EMAIL
ADMIN_PASSWORD = config.ADMIN_PASSWORD
NGROK_AUTHTOKEN = config.NGROK_AUTHTOKEN

# Page Configuration
st.set_page_config(
    page_title="Infosys Springboard Portal — Milestone 2",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Database and Seed Users
db.init_db()
db.seed_initial_users(auth.hash_txt, auth.check_txt, ADMIN_EMAIL, ADMIN_PASSWORD)

# Inject Custom CSS Theme (Preserving Milestone 1 Visual Identity)
ui_theme.inject_theme()

# Load ML Suite and LLM Copilot Engine
@st.cache_resource
def load_ml_suite():
    return FreightQuoteMLSuite()

@st.cache_resource
def load_llm_engine():
    return LogisticsLLMEngine()

ml_suite = load_ml_suite()
llm_engine = load_llm_engine()

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

ngrok_url = start_ngrok_tunnel()

# --- Session State Initialization ---
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
                    ui_theme.render_auth_header("Admin Portal Access")
                    email = st.text_input("Admin Email Address", placeholder="admin@domain.com").lower().strip()
                    pwd = st.text_input("Password", type="password", placeholder="••••••••")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    is_locked, time_left, lock_msg = auth.check_progressive_lockout(email)
                    if is_locked:
                        st.error(lock_msg)
                        
                    col1, col2 = st.columns(2)
                    if col1.button("Admin Sign In →", use_container_width=True):
                        if is_locked:
                            st.error(lock_msg)
                        elif not email or not pwd:
                            st.error("⚠️ Please fill in all fields.")
                        elif not auth.is_valid_email(email):
                            st.error("⚠️ Please enter a valid email address.")
                        elif email != ADMIN_EMAIL or pwd != ADMIN_PASSWORD:
                            err_msg = auth.record_failed_login(email)
                            st.error(err_msg)
                        else:
                            auth.record_successful_login(email)
                            st.session_state.token = auth.make_jwt(email)
                            st.success("✅ Admin logged in successfully!")
                            time.sleep(0.5)
                            navigate("Home Dashboard")
                            
                    if col2.button("Forgot Password?", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.session_state.reset_email = None
                        st.session_state.otp_jwt_token = None
                        st.session_state.security_question = None
                        st.session_state.dev_sandbox_otp = None
                        navigate("Forgot")

                # --- USER LOGIN TAB ---
                else:
                    ui_theme.render_auth_header("Sign in to your account")
                    email = st.text_input("Email Address", placeholder="you@example.com").lower().strip()
                    pwd = st.text_input("Password", type="password", placeholder="••••••••")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    is_locked, time_left, lock_msg = auth.check_progressive_lockout(email)
                    if is_locked:
                        st.error(lock_msg)
                        
                    col1, col2 = st.columns(2)
                    if col1.button("Sign In →", use_container_width=True):
                        if is_locked:
                            st.error(lock_msg)
                        elif not email or not pwd:
                            st.error("⚠️ Please fill in all fields.")
                        elif not auth.is_valid_email(email):
                            st.error("⚠️ Please enter a valid email address.")
                        else:
                            user_rec = db.get_user_by_email(email)
                            if user_rec and auth.check_txt(pwd, user_rec["password_hash"]):
                                auth.record_successful_login(email)
                                st.session_state.token = auth.make_jwt(email)
                                st.success("✅ Logged in successfully!")
                                time.sleep(0.5)
                                navigate("Home Dashboard")
                            else:
                                err_msg = auth.record_failed_login(email)
                                st.error(err_msg)
                                
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
                ui_theme.render_auth_header("Create dynamic user account")
                
                uname = st.text_input("Full Name / Username", placeholder="John Doe")
                email = st.text_input("Email Address", placeholder="you@example.com").lower().strip()
                
                # Live Password Strength Checker
                pwd = st.text_input("Password", type="password", placeholder="••••••••")
                score, rating, color, msg = auth.evaluate_password_strength(pwd)
                ui_theme.render_password_strength_badge(score, rating, color, msg)
                
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
                    pwd_ok, pwd_msg = auth.is_strong_password(pwd)
                    
                    if not uname or not email or not pwd or not confirm_pwd or not sa:
                        st.error("⚠️ All fields are mandatory. Please fill in all fields.")
                    elif not auth.is_valid_email(email):
                        st.error("⚠️ Please enter a valid email address.")
                    elif rating == "Weak":
                        st.error(f"⚠️ {pwd_msg}")
                    elif pwd != confirm_pwd:
                        st.error("❌ Passwords do not match.")
                    else:
                        try:
                            pwd_hash = auth.hash_txt(pwd)
                            sa_hash = auth.hash_txt(sa.lower().strip())
                            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                            
                            with db.get_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO users (username, email, password_hash, security_question, security_answer_hash, created_at, failed_attempts, lock_until, account_status, role)
                                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'active', 'Logistics Manager')
                                """, (uname, email, pwd_hash, sq, sa_hash, now_str))
                                conn.commit()
                                
                            st.session_state.token = auth.make_jwt(email)
                            st.success("✅ Account created successfully!")
                            time.sleep(0.5)
                            navigate("Home Dashboard")
                        except Exception:
                            st.error("❌ Email or Username is already registered.")
                            
                if col2.button("Back to Login", use_container_width=True):
                    navigate("Login")

            # --- FORGOT PASSWORD VIEW ---
            elif st.session_state.page == "Forgot":
                ui_theme.render_auth_header("Reset Password")
                
                if st.session_state.forgot_stage == "email":
                    st.markdown("<p style='text-align:center;'>Enter your registered email address to choose verification method.</p>", unsafe_allow_html=True)
                    email = st.text_input("Registered Email", placeholder="you@example.com").lower().strip()
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_sq, col_otp = st.columns(2)
                    if col_sq.button("Via Security Question", use_container_width=True):
                        if not email:
                            st.error("⚠️ Please enter your email.")
                        else:
                            user_rec = db.get_user_by_email(email)
                            if user_rec:
                                st.session_state.reset_email = email
                                st.session_state.security_question = user_rec["security_question"]
                                st.session_state.forgot_stage = "sq"
                                st.rerun()
                            else:
                                st.error("❌ Email address not found in system.")
                                
                    if col_otp.button("Via Email OTP", use_container_width=True):
                        if not email:
                            st.error("⚠️ Please enter your email.")
                        else:
                            user_rec = db.get_user_by_email(email)
                            if user_rec:
                                otp = auth.generate_otp()
                                with st.spinner("Generating security code..."):
                                    ok, info = auth.send_otp_email(email, otp)
                                if ok:
                                    st.session_state.reset_email = email
                                    st.session_state.otp_jwt_token = auth.make_otp_token(email, otp)
                                    st.session_state.forgot_stage = "otp"
                                    
                                    if info == "sandbox_mode":
                                        st.session_state.dev_sandbox_otp = otp
                                        st.warning("⚠️ SMTP configurations not set. Developer OTP updated below.")
                                    st.success("✅ 6-digit OTP code generated.")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to dispatch email. Error: {info}")
                            else:
                                st.error("Email address not found.")

                elif st.session_state.forgot_stage == "sq":
                    st.info(f"❓ **Security Question:** {st.session_state.security_question}")
                    sa_input = st.text_input("Your Answer", placeholder="Answer text").lower().strip()
                    
                    st.markdown("**Create New Password:**")
                    npw = st.text_input("New Password", type="password", placeholder="••••••••")
                    score, rating, color, msg = auth.evaluate_password_strength(npw)
                    ui_theme.render_password_strength_badge(score, rating, color, msg)
                    
                    confirm_npw = st.text_input("Confirm New Password", type="password", placeholder="••••••••")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    if col1.button("Reset Password", use_container_width=True):
                        if not sa_input or not npw:
                            st.error("⚠️ Please fill in all fields.")
                        elif rating == "Weak":
                            st.error(f"⚠️ Password is too weak.")
                        elif npw != confirm_npw:
                            st.error("❌ Passwords do not match.")
                        else:
                            user_rec = db.get_user_by_email(st.session_state.reset_email)
                            if user_rec and auth.check_txt(sa_input, user_rec["security_answer_hash"]):
                                with db.get_db() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE users SET password_hash=? WHERE email=?", (auth.hash_txt(npw), st.session_state.reset_email))
                                    conn.commit()
                                st.success("🎉 Password reset successfully!")
                                time.sleep(1.5)
                                st.session_state.forgot_stage = "email"
                                navigate("Login")
                            else:
                                st.error("❌ Incorrect security answer.")
                                
                    if col2.button("Cancel", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.rerun()

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
                            ok, msg = auth.verify_otp_token(st.session_state.otp_jwt_token, otp_input, st.session_state.reset_email)
                            if ok:
                                st.session_state.forgot_stage = "reset"
                                st.success("✅ Code verified successfully!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
                                
                    can_resend, remaining_secs, next_count = auth.check_otp_resend_cooldown(st.session_state.reset_email)
                    if col2.button("Resend Code", use_container_width=True):
                        if not can_resend:
                            st.warning(f"⏳ Please wait {remaining_secs} seconds before requesting another code.")
                        else:
                            auth.record_otp_resend(st.session_state.reset_email)
                            otp = auth.generate_otp()
                            with st.spinner("Resending verification code..."):
                                ok, info = auth.send_otp_email(st.session_state.reset_email, otp)
                            if ok:
                                st.session_state.otp_jwt_token = auth.make_otp_token(st.session_state.reset_email, otp)
                                if info == "sandbox_mode":
                                    st.session_state.dev_sandbox_otp = otp
                                    st.warning("⚠️ SMTP configurations not set. Developer OTP updated below.")
                                st.success("✅ New OTP code sent!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to dispatch email: {info}")
                                
                    if col3.button("Back", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.session_state.dev_sandbox_otp = None
                        st.rerun()

                elif st.session_state.forgot_stage == "reset":
                    st.markdown("🔒 **Create New Secure Password:**")
                    npw = st.text_input("New Password", type="password", placeholder="••••••••")
                    score, rating, color, msg = auth.evaluate_password_strength(npw)
                    ui_theme.render_password_strength_badge(score, rating, color, msg)
                    
                    confirm_npw = st.text_input("Confirm New Password", type="password", placeholder="••••••••")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    if col1.button("Update Password", use_container_width=True):
                        if not npw:
                            st.error("⚠️ Please enter password.")
                        elif rating == "Weak":
                            st.error("⚠️ Password is too weak.")
                        elif npw != confirm_npw:
                            st.error("❌ Passwords do not match.")
                        else:
                            with db.get_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE users SET password_hash=? WHERE email=?", (auth.hash_txt(npw), st.session_state.reset_email))
                                conn.commit()
                            st.success("🎉 Password updated successfully!")
                            time.sleep(1.5)
                            st.session_state.forgot_stage = "email"
                            st.session_state.dev_sandbox_otp = None
                            navigate("Login")
                            
                    if col2.button("Cancel Reset", use_container_width=True):
                        st.session_state.forgot_stage = "email"
                        st.session_state.dev_sandbox_otp = None
                        navigate("Login")

                st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
                if st.button("← Cancel & Back to Login", use_container_width=True):
                    st.session_state.forgot_stage = "email"
                    st.session_state.dev_sandbox_otp = None
                    navigate("Login")

# ============================================================
# AUTHENTICATED ROUTING (Dashboard & AI Copilot Views)
# ============================================================
else:
    payload = auth.verify_jwt(st.session_state.token)
    if not payload:
        st.session_state.token = None
        st.session_state.page = "Login"
        st.warning("⚠️ Session expired. Please log in again.")
        time.sleep(1.5)
        st.rerun()

    email = payload["email"]
    user_rec = db.get_user_by_email(email)
    if not user_rec:
        st.session_state.token = None
        st.session_state.page = "Login"
        st.rerun()
        
    uname = user_rec["username"]
    user_role = user_rec.get("role", "Logistics Manager")
    is_admin = (email == ADMIN_EMAIL or user_role == "Admin")

    # --- SIDEBAR NAVIGATION ---
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 16px 8px; text-align: center;">
            <div style="font-size: 36px; margin-bottom: 6px; color: #0078D4;">📦</div>
            <div style="font-weight: 700; font-size: 16px; color: #111827;">Infosys Portal</div>
            <div style="font-size: 11px; color: #4B5563; font-weight: 600; margin-top: 2px;">
                {"🛡️ Admin Control Desk" if is_admin else f"⚙️ {user_role}"}
            </div>
        </div>
        <hr style="border-top: 1px solid #E5E7EB; margin: 10px 0 20px 0;">
        """, unsafe_allow_html=True)

        opts = ["Home Dashboard", "Dynamic Pricing", "Route Prediction", "Carrier Compliance", "AI Copilot", "Reports"]
        icons = ["house", "calculator", "graph-up", "shield-check", "robot", "file-text"]
        
        if is_admin:
            opts.append("Admin Dashboard")
            icons.append("gear")
            
        opts.append("Logout")
        icons.append("box-arrow-right")

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

    # --- TOP BRANDING HEADER WITH CUSTOM ROLE ---
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0078D4, #005A9E); border-radius: 16px; padding: 24px 32px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; color: #FFFFFF; box-shadow: 0px 4px 12px rgba(0, 120, 212, 0.15);">
        <div>
            <h1 style="color: #FFFFFF !important; margin: 0; font-size: 24px !important;">Infosys Springboard Portal</h1>
            <div style="color: rgba(255, 255, 255, 0.85); font-size: 13px; font-weight: 500; margin-top: 2px;">
                Intelligent Freight Quote Generation System — Milestone 2
            </div>
        </div>
        <div style="background: rgba(255, 255, 255, 0.2); padding: 8px 18px; border-radius: 30px; font-weight: 600; font-size: 13px; border: 1px solid rgba(255, 255, 255, 0.3);">
            👤 {uname} <span style="opacity: 0.8;">({user_role})</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- PAGE NAVIGATION ROUTING ---
    if menu == "Home Dashboard":
        st.markdown("### 📊 System Operations & Project KPI Dashboard")
        
        # Project-Specific KPI Metrics
        users_count = len(db.get_all_users())
        models_meta = db.get_all_ml_models_metadata()
        tot_models = len(models_meta)
        
        meta1 = db.get_ml_model_metadata("Agent 1: Dynamic Pricing")
        best_r2 = f"{meta1['metrics'].get('r2', 0.9965):.4f}" if meta1 else "0.9965"
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(ui_theme.render_dashboard_card("👥", str(users_count), "Total Users"), unsafe_allow_html=True)
        c2.markdown(ui_theme.render_dashboard_card("🤖", "3 Active Agents", "Active ML Agents"), unsafe_allow_html=True)
        c3.markdown(ui_theme.render_dashboard_card("🧠", "Qwen2.5-3B Ready", "AI Copilot Status"), unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        c4, c5, c6 = st.columns(3)
        c4.markdown(ui_theme.render_dashboard_card("📈", best_r2, "Best Pricing Model R²"), unsafe_allow_html=True)
        c5.markdown(ui_theme.render_dashboard_card("📦", str(tot_models) + " Models", "Trained Champion Models"), unsafe_allow_html=True)
        c6.markdown(ui_theme.render_dashboard_card("🛡️", "Secured", "Security Status"), unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=98,
            title={"text": "Multi-Agent System Operational Index", "font": {"color": "#111827", "size": 15, "family": "Segoe UI"}},
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

    elif menu == "Dynamic Pricing":
        st.markdown("### 💰 Agent 1: Dynamic Freight Pricing Calculator")
        st.markdown("Enter shipment parameters below to generate instant ML-driven price predictions via the **Champion Regression Model**.")
        
        col_in1, col_in2 = st.columns(2)
        with col_in1:
            origin_port = st.selectbox(
                "Origin Hub / Port",
                ["Nhava Sheva (INNSA)", "Mundra (INMUN)", "Chennai (INMAA)", "Kolkata (INCCU)", "Cochin (INCOK)", "Visakhapatnam (INVTZ)"]
            )
            dest_port = st.selectbox(
                "Destination Hub / Port",
                ["Los Angeles (USLAX)", "Rotterdam (NLRTM)", "Singapore (SGSIN)", "Dubai (AEDXB)", "Hamburg (DEHAM)"]
            )
            distance_miles = st.number_input("Distance (Nautical Miles)", min_value=100, max_value=20000, value=7500, step=100)
            cargo_weight_tons = st.number_input("Cargo Weight (Metric Tons)", min_value=0.5, max_value=50.0, value=18.5, step=0.5)
            
        with col_in2:
            container_type_label = st.selectbox(
                "Container Specifications",
                ["20ft Standard Dry", "40ft High Cube Dry", "40ft Reefer (Refrigerated)"]
            )
            container_type = 1 if "20ft" in container_type_label else (3 if "Reefer" in container_type_label else 2)
            
            fuel_index = st.slider("Bunker Fuel Price Index ($/ton)", 80.0, 160.0, 115.0)
            port_congestion = st.slider("Port Congestion Index (1: Clear - 5: Severe)", 1.0, 5.0, 2.5)
            urgency_level = st.selectbox("Shipping Priority Level", [1, 2, 3], format_func=lambda x: {1: "Standard Ocean Freight", 2: "Express Feeder", 3: "Critical Fast-Track"}[x])
            
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Calculate Freight Quote Price ($) →", use_container_width=True):
            params = {
                "distance_miles": distance_miles,
                "cargo_weight_tons": cargo_weight_tons,
                "container_type": container_type,
                "fuel_index": fuel_index,
                "port_congestion": port_congestion,
                "urgency_level": urgency_level
            }
            pred_price = ml_suite.predict_pricing(params)
            
            meta = db.get_ml_model_metadata("Agent 1: Dynamic Pricing")
            champ_algo = meta["algorithm_name"] if meta else "Ridge Regression"
            r2_score_val = meta["metrics"].get("r2", 0.9965) if meta else 0.9965
            
            res_col1, res_col2 = st.columns(2)
            res_col1.markdown(f"""
            <div style="background-color: #EFF6FF; border: 2px solid #0078D4; border-radius: 16px; padding: 24px; text-align: center;">
                <div style="font-size: 14px; font-weight: 600; color: #1D4ED8;">ESTIMATED FREIGHT QUOTE</div>
                <div style="font-size: 42px; font-weight: 800; color: #0078D4; margin: 10px 0;">${pred_price:,.2f}</div>
                <div style="font-size: 12px; color: #4B5563;">Computed via Champion ML Model</div>
            </div>
            """, unsafe_allow_html=True)
            
            res_col2.markdown(f"""
            <div style="background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 16px; padding: 24px;">
                <div style="font-weight: 700; font-size: 16px; color: #111827; margin-bottom: 8px;">Model Provenance Metadata</div>
                <div style="font-size: 13px; color: #374151;">• <b>Champion Algorithm:</b> {champ_algo}</div>
                <div style="font-size: 13px; color: #374151;">• <b>Validation R² Score:</b> {r2_score_val:.4f} (Target ≥ 0.90)</div>
                <div style="font-size: 13px; color: #374151;">• <b>Origin -> Destination:</b> {origin_port} -> {dest_port}</div>
            </div>
            """, unsafe_allow_html=True)

    elif menu == "Route Prediction":
        st.markdown("### 📈 Agent 2: Route Delay Prediction Classifier")
        st.markdown("Evaluate route congestion and transit delay probabilities using the **Champion Classification Agent**.")
        
        dist_in = st.number_input("Route Distance (Nautical Miles)", 500, 15000, 6800, step=200, key="d_dist")
        cong_in = st.slider("Destination Terminal Congestion (1-5)", 1.0, 5.0, 3.2, key="d_cong")
        urg_in = st.selectbox("Shipment Urgency Level", [1, 2, 3], key="d_urg")
        
        if st.button("Evaluate Route Delay Risk →", use_container_width=True):
            proba, risk_label = ml_suite.predict_delay_risk({
                "distance_miles": dist_in,
                "port_congestion": cong_in,
                "urgency_level": urg_in
            })
            color = "#EF4444" if risk_label == "High Risk" else "#10B981"
            st.markdown(f"""
            <div style="background-color: #F9FAFB; border-left: 6px solid {color}; border-radius: 12px; padding: 20px; margin-top: 15px;">
                <div style="font-size: 14px; font-weight: 600;">Delay Risk Classification: <span style="color: {color}; font-weight: 800;">{risk_label}</span></div>
                <div style="font-size: 28px; font-weight: 800; margin-top: 4px;">{proba*100:.1f}% Probability</div>
            </div>
            """, unsafe_allow_html=True)

    elif menu == "Carrier Compliance":
        st.markdown("### 🛡️ Agent 3: Carrier Compliance Evaluator")
        st.markdown("Audit carrier safety scores and compliance status using the **Champion Carrier Classifier**.")
        
        carrier_rating = st.slider("Carrier Safety Rating (1 - 5 Stars)", 1.0, 5.0, 4.2, step=0.1, key="c_rat")
        container_type_sel = st.selectbox("Container Category Code", [1, 2, 3], key="c_type")
        
        if st.button("Audit Carrier Compliance →", use_container_width=True):
            proba, status = ml_suite.predict_compliance({
                "carrier_rating": carrier_rating,
                "container_type": container_type_sel
            })
            color = "#10B981" if status == "Compliant" else "#F59E0B"
            st.markdown(f"""
            <div style="background-color: #F9FAFB; border-left: 6px solid {color}; border-radius: 12px; padding: 20px; margin-top: 15px;">
                <div style="font-size: 14px; font-weight: 600;">Carrier Compliance Status: <span style="color: {color}; font-weight: 800;">{status}</span></div>
                <div style="font-size: 28px; font-weight: 800; margin-top: 4px;">{proba*100:.1f}% Compliance Score</div>
            </div>
            """, unsafe_allow_html=True)

    elif menu == "AI Copilot":
        st.markdown("### 🤖 Multi-Agent AI Copilot & Structured Audit Desk (`Qwen2.5-3B-Instruct`)")
        st.markdown("Generate comprehensive AI logistics audits combining predictions from **Agent 1 (Pricing)**, **Agent 2 (Delay)**, and **Agent 3 (Compliance)**.")
        
        with st.form("audit_form"):
            o_port = st.selectbox("Origin Port", ["Nhava Sheva (INNSA)", "Mundra (INMUN)", "Chennai (INMAA)", "Kolkata (INCCU)"])
            d_port = st.selectbox("Destination Port", ["Los Angeles (USLAX)", "Rotterdam (NLRTM)", "Singapore (SGSIN)", "Dubai (AEDXB)"])
            c_weight = st.number_input("Cargo Weight (Tons)", 1.0, 40.0, 14.0)
            c_dist = st.number_input("Distance (Miles)", 1000, 15000, 7200)
            c_rating = st.slider("Carrier Rating", 1.0, 5.0, 4.4)
            
            submit_audit = st.form_submit_button("Generate Multi-Agent JSON Audit Output →", use_container_width=True)
            
        if submit_audit:
            with st.spinner("Orchestrating Agent 1, Agent 2, Agent 3 predictions & Qwen2.5-3B-Instruct reasoning..."):
                params = {
                    "origin_port": o_port,
                    "dest_port": d_port,
                    "distance_miles": c_dist,
                    "cargo_weight_tons": c_weight,
                    "carrier_rating": c_rating
                }
                audit_json = llm_engine.produce_structured_audit(params)
                
                st.success("✅ Multi-Agent Audit Generated Successfully!")
                st.json(audit_json)
                
        st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
        st.subheader("💬 Ask AI Copilot Logistics Assistant")
        query_in = st.text_input("Ask a logistics question:", placeholder="e.g. What is the impact of fuel surcharges on Nhava Sheva routes?")
        if st.button("Ask Copilot"):
            if query_in:
                with st.spinner("Analyzing..."):
                    answer = llm_engine.answer_logistics_question(query_in)
                st.markdown(answer)
            else:
                st.warning("Please enter a question.")

    elif menu == "Admin Dashboard":
        if is_admin:
            st.markdown("## 🛡️ Professional Admin Dashboard & ML Model Cards")
            tab_desk, tab_cards, tab_settings = st.tabs(["📊 Overview Logs", "🤖 SQLite ML Model Cards", "⚙️ User & Role Management"])
            with tab_desk:
                admin_dash.render_admin_dashboard(ngrok_url)
            with tab_cards:
                admin_dash.render_ml_model_cards()
            with tab_settings:
                admin_dash.render_admin_settings()
        else:
            st.error("⛔ Access Restricted: Admin Dashboard is reserved for Administrator users.")

    elif menu == "Reports":
        st.markdown("### 📋 Intelligent Freight Quote Ledger")
        quotes_data = {
            "Quote ID": ["FQ-2001", "FQ-2002", "FQ-2003", "FQ-2004", "FQ-2005"],
            "Origin Hub": ["Nhava Sheva (INNSA)", "Mundra (INMUN)", "Chennai (INMAA)", "Kolkata (CCU)", "Cochin (COK)"],
            "Destination Hub": ["Los Angeles (USLAX)", "Rotterdam (NLRTM)", "Singapore (SGSIN)", "Dubai (AEDXB)", "Hamburg (DEHAM)"],
            "Cargo Category": ["Electronics", "Chemicals", "Textiles", "Machinery", "Automotive"],
            "Freight Price ($)": [2650.00, 3280.00, 1920.00, 4450.00, 3100.00],
            "Current Status": ["Approved", "Pending Match", "Approved", "Under Review", "Approved"]
        }
        df = pd.DataFrame(quotes_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
