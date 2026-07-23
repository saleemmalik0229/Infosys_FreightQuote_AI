import sys
from pathlib import Path

# Add Milestone2 and parent root directory to sys.path
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
                                navigate("Dashboard")
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
                                    INSERT INTO users (username, email, password_hash, security_question, security_answer_hash, created_at, failed_attempts, lock_until, account_status)
                                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'active')
                                """, (uname, email, pwd_hash, sq, sa_hash, now_str))
                                conn.commit()
                                
                            st.session_state.token = auth.make_jwt(email)
                            st.success("✅ Account created successfully!")
                            time.sleep(0.5)
                            navigate("Dashboard")
                        except Exception:
                            st.error("❌ Email or Username is already registered.")
                            
                if col2.button("Back to Login", use_container_width=True):
                    navigate("Login")

            # --- FORGOT PASSWORD VIEW ---
            elif st.session_state.page == "Forgot":
                ui_theme.render_auth_header("Reset Password")
                
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

                # STAGE 2B: ENTER OTP CODE (WITH ESCALATING COOLDOWN)
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
                                
                    # OTP Resend with Cooldown
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

                # STAGE 3: CREATE NEW PASSWORD (AFTER OTP SUCCESS)
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
# AUTHENTICATED ROUTING (Dashboard views)
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
    ui_theme.render_top_header(uname, is_admin)

    # --- ADMIN PAGES ---
    if is_admin:
        if menu == "Dashboard":
            admin_dash.render_admin_dashboard(ngrok_url)
        elif menu == "Settings":
            admin_dash.render_admin_settings()

    # --- REGULAR USER PAGES ---
    else:
        if menu == "Dashboard":
            st.markdown("### 📊 System Operations Hub")
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(ui_theme.render_dashboard_card("📄", "128", "Documents Indexed"), unsafe_allow_html=True)
            c2.markdown(ui_theme.render_dashboard_card("🔍", "47", "Searches Today"), unsafe_allow_html=True)
            c3.markdown(ui_theme.render_dashboard_card("📈", "98.4%", "Efficiency Score"), unsafe_allow_html=True)
            c4.markdown(ui_theme.render_dashboard_card("🛡️", "Secured", "Security Status"), unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
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
            routes = ["Nhava Sheva - LA", "Mundra - Rotterdam", "Chennai - Singapore", "Mumbai - Dubai", "Kolkata - Tokyo"]
            quotes = [94, 78, 62, 51, 35]
            
            fig_bar = go.Figure(data=[go.Bar(
                x=routes, y=quotes,
                marker_color='#0078D4', text=quotes, textposition='auto',
            )])
            fig_bar.update_layout(
                title={"text": "Active Freight Quote Volumes by Indian & Global Trade Lanes", "font": {"size": 16, "family": "Segoe UI"}},
                xaxis_title="Shipping Route", yaxis_title="Quotes Generated",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=350, margin=dict(l=20, r=20, t=50, b=20)
            )
            
            transit_times = [14, 21, 10, 8, 12]
            fig_line = go.Figure(data=[go.Scatter(
                x=routes, y=transit_times,
                mode="lines+markers",
                line=dict(color="#00A6A6", width=3),
                marker=dict(size=8, color="#0078D4")
            )])
            fig_line.update_layout(
                title={"text": "Average Transit Times (Days)", "font": {"size": 16, "family": "Segoe UI"}},
                xaxis_title="Shipping Route", yaxis_title="Days in Transit",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=300, margin=dict(l=20, r=20, t=50, b=20)
            )
            
            col_left, col_right = st.columns(2)
            with col_left:
                st.plotly_chart(fig_bar, use_container_width=True)
            with col_right:
                st.plotly_chart(fig_line, use_container_width=True)

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
