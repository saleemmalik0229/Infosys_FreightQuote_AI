import time
import pandas as pd
import streamlit as st

import config
import db
import auth
from ui_theme import render_dashboard_card

ADMIN_EMAIL = config.ADMIN_EMAIL

CUSTOM_ROLES = ["Admin", "Logistics Manager", "Operations Manager", "Auditor", "Portal Client"]

def render_admin_dashboard(ngrok_url: str = None):
    """
    Renders Admin Control Overview metrics and system log table.
    """
    st.markdown("### 🛡️ Admin Control Desk Overview")
    
    users = db.get_all_users()
    tot_users = len(users)
    locked_users = len([u for u in users if u["account_status"] == "locked"])
    models = db.get_all_ml_models_metadata()
    tot_models = len(models)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(render_dashboard_card("👥", str(tot_users), "Total Users"), unsafe_allow_html=True)
    c2.markdown(render_dashboard_card("🔒", str(locked_users), "Locked Accounts"), unsafe_allow_html=True)
    c3.markdown(render_dashboard_card("🤖", str(tot_models), "Trained ML Models"), unsafe_allow_html=True)
    c4.markdown(render_dashboard_card("🔗", "Connected" if ngrok_url else "Local Only", "Ngrok Proxy Status"), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("System Access Activity Logs (Recent Sign-ups)")
    
    if users:
        sorted_users = sorted(users, key=lambda x: x["created_at"] or "", reverse=True)[:5]
        log_df = pd.DataFrame(sorted_users)[["username", "email", "role", "account_status", "created_at"]]
        log_df.columns = ["Username", "User Email", "Role", "Account Status", "Created Timestamp"]
        st.table(log_df)
    else:
        st.info("No system activity logged.")

def render_ml_model_cards():
    """
    Renders SQLite-driven ML Model Cards displaying Agent Name, Champion Algorithm,
    R^2, RMSE, ROC-AUC, Training Date, Dataset, and Saved Model File Path.
    """
    st.markdown("### 🤖 SQLite ML Champion Model Cards (`ml_models` table)")
    models_data = db.get_all_ml_models_metadata()
    
    if not models_data:
        st.warning("⚠️ No ML champion models logged in SQLite database yet. Run `python train_ml_freight.py` to train models.")
        return
        
    cols = st.columns(len(models_data))
    
    for idx, md in enumerate(models_data):
        with cols[idx % len(cols)]:
            metrics = md.get("metrics", {})
            r2_val = metrics.get("r2", "N/A")
            rmse_val = metrics.get("rmse", "N/A")
            roc_auc_val = metrics.get("roc_auc", "N/A")
            
            r2_str = f"{r2_val:.4f}" if isinstance(r2_val, float) else str(r2_val)
            rmse_str = f"${rmse_val:.2f}" if isinstance(rmse_val, float) else str(rmse_val)
            roc_auc_str = f"{roc_auc_val:.4f}" if isinstance(roc_auc_val, float) else str(roc_auc_val)
            
            st.markdown(f"""
            <div style="background-color: #F9FAFB; border: 2px solid #0078D4; border-radius: 16px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 15px;">
                <div style="font-size: 16px; font-weight: 800; color: #0078D4; margin-bottom: 8px;">{md['agent_name']}</div>
                <div style="font-size: 13px; color: #111827; margin-bottom: 4px;">• <b>Champion Algorithm:</b> {md['algorithm_name']}</div>
                <div style="font-size: 13px; color: #111827; margin-bottom: 4px;">• <b>Model Type:</b> {md['model_type']}</div>
                <div style="font-size: 13px; color: #111827; margin-bottom: 4px;">• <b>R² Score:</b> <span style="color:#10B981; font-weight:700;">{r2_str}</span></div>
                <div style="font-size: 13px; color: #111827; margin-bottom: 4px;">• <b>RMSE:</b> {rmse_str}</div>
                <div style="font-size: 13px; color: #111827; margin-bottom: 4px;">• <b>ROC-AUC Score:</b> <span style="color:#0078D4; font-weight:700;">{roc_auc_str}</span></div>
                <div style="font-size: 12px; color: #6B7280; margin-top: 8px;">• <b>Training Date:</b> {md['created_at']}</div>
                <div style="font-size: 12px; color: #6B7280;">• <b>Dataset:</b> Indian & Global Corridors</div>
                <div style="font-size: 11px; color: #374151; background: #EFF6FF; padding: 6px; border-radius: 6px; margin-top: 8px; word-break: break-all;">
                    📁 <b>Saved Model:</b><br>{md['model_file_path']}
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_admin_settings():
    """
    Renders Admin User Management tools: User Table, Role Management, Add User, Unlock User, and Delete User.
    """
    st.markdown("### ⚙️ System User Directory & Role Management")
    
    users = db.get_all_users()
    
    if users:
        st.subheader("Registered Users Directory")
        users_df = pd.DataFrame(users)[["id", "username", "email", "role", "failed_attempts", "account_status", "created_at"]]
        users_df.columns = ["ID", "Username", "Email Address", "Custom Role", "Failed Attempts", "Account Status", "Registered Date"]
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        
        st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
        
        # --- ROLE MANAGEMENT SECTION ---
        st.subheader("👑 Role Management")
        st.info("Assign custom enterprise roles to users: Admin, Logistics Manager, Operations Manager, Auditor, Portal Client.")
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            target_email = st.selectbox("Select User Email to Update Role", [u["email"] for u in users], key="role_select_email")
        with col_r2:
            new_role = st.selectbox("Assign Custom Role", CUSTOM_ROLES, key="role_select_val")
            
        if st.button("Update Role", key="btn_update_role"):
            if db.update_user_role(target_email, new_role):
                st.success(f"✅ Updated role for {target_email} to '{new_role}'.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to update user role.")
                
        st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
        
        # --- ADD USER SECTION ---
        st.subheader("➕ Add New User Account")
        with st.form("add_user_form"):
            new_uname = st.text_input("Full Name / Username")
            new_email = st.text_input("Email Address").lower().strip()
            new_role_val = st.selectbox("User Role", CUSTOM_ROLES)
            new_pwd = st.text_input("Initial Password", type="password")
            new_sq = st.selectbox("Security Question", ["What is your pet name?", "What is your mother's maiden name?", "What is your favourite city?"])
            new_sa = st.text_input("Security Answer")
            
            submit_user = st.form_submit_button("Create User Account", use_container_width=True)
            if submit_user:
                if not new_uname or not new_email or not new_pwd or not new_sa:
                    st.error("⚠️ All fields are required.")
                elif not auth.is_valid_email(new_email):
                    st.error("⚠️ Invalid email format.")
                else:
                    try:
                        pwd_h = auth.hash_txt(new_pwd)
                        sa_h = auth.hash_txt(new_sa.lower().strip())
                        db.add_user_by_admin(new_uname, new_email, pwd_h, new_role_val, new_sq, sa_h)
                        st.success(f"✅ User {new_email} created with role '{new_role_val}'.")
                        time.sleep(1)
                        st.rerun()
                    except Exception:
                        st.error("❌ User email already exists.")
                        
        st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
        
        # --- ADMIN UNLOCK SECTION ---
        st.subheader("🔓 Admin Account Unlock")
        locked_emails = [u["email"] for u in users if u["account_status"] == "locked" or u["failed_attempts"] >= 3]
        if locked_emails:
            unlock_email = st.selectbox("Select Locked Account to Unlock", locked_emails, key="unlock_select")
            if st.button("Unlock Selected Account", key="btn_unlock"):
                if db.unlock_user_account(unlock_email):
                    st.success(f"✅ Account {unlock_email} has been unlocked!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to unlock account.")
        else:
            st.success("✅ No accounts are currently locked.")
            
        st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
        
        # --- REMOVE USER SECTION ---
        st.subheader("🗑️ Remove User Account")
        emails_to_delete = [u["email"] for u in users if u["email"] != ADMIN_EMAIL]
        if emails_to_delete:
            del_email = st.selectbox("Select User Email to Remove", emails_to_delete, key="del_select")
            if st.button("Delete Selected Account", key="btn_del"):
                if db.delete_user_by_email(del_email):
                    st.success(f"✅ Account {del_email} has been deleted.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to delete account.")
        else:
            st.info("No regular user accounts available to remove.")
    else:
        st.info("No users registered in system.")
