import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from db import get_all_users, unlock_user_account, delete_user_by_email
from ui_theme import render_dashboard_card

ADMIN_EMAIL = config.ADMIN_EMAIL

def render_admin_dashboard(ngrok_url: str = None):
    """
    Renders the Admin Control Overview screen with metrics and system activity logs.
    """
    st.markdown("### 🛡️ Admin Control Overview")
    
    users = get_all_users()
    tot_users = len(users)
    locked_users = len([u for u in users if u["account_status"] == "locked"])
    
    c1, c2, c3 = st.columns(3)
    
    c1.markdown(render_dashboard_card("👥", str(tot_users), "Registered Users"), unsafe_allow_html=True)
    c2.markdown(render_dashboard_card("🔒", str(locked_users), "Locked Accounts"), unsafe_allow_html=True)
    c3.markdown(render_dashboard_card("🔗", "Connected" if ngrok_url else "Local Only", "Ngrok Proxy Status"), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("System Access Activity Logs (Recent Sign-ups)")
    
    if users:
        sorted_users = sorted(users, key=lambda x: x["created_at"] or "", reverse=True)[:5]
        log_df = pd.DataFrame(sorted_users)[["username", "email", "account_status", "created_at"]]
        log_df.columns = ["Username", "User Email", "Account Status", "Created Timestamp"]
        st.table(log_df)
    else:
        st.info("No system activity logged.")

def render_admin_settings():
    """
    Renders Admin User Management tools: Directory, Account Unlocker, and User Deletion.
    """
    st.markdown("### ⚙️ System Settings & User Directory")
    
    users = get_all_users()
    
    if users:
        st.subheader("Registered Users Directory")
        # Format user directory DataFrame (never exposing password hashes)
        users_df = pd.DataFrame(users)[["id", "username", "email", "failed_attempts", "account_status", "created_at"]]
        users_df.columns = ["ID", "Username", "Email Address", "Failed Attempts", "Account Status", "Registered Date"]
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        
        st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
        
        # --- ADMIN UNLOCK SECTION ---
        st.subheader("🔓 Admin Account Unlock")
        st.info("Admins can unlock accounts locked due to progressive failed login attempts.")
        
        locked_emails = [u["email"] for u in users if u["account_status"] == "locked" or u["failed_attempts"] >= 3]
        
        if locked_emails:
            unlock_email = st.selectbox("Select Locked Account to Unlock", locked_emails, key="unlock_select")
            if st.button("Unlock Selected Account", key="btn_unlock"):
                if unlock_user_account(unlock_email):
                    st.success(f"✅ Account {unlock_email} has been unlocked successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to unlock account.")
        else:
            st.success("✅ No accounts are currently locked.")
            
        st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
        
        # --- REMOVE USER SECTION ---
        st.subheader("🗑️ Remove User Account")
        st.warning("⚠️ Warning: Removing a user account is permanent and cannot be undone.")
        
        emails_to_delete = [u["email"] for u in users if u["email"] != ADMIN_EMAIL]
        
        if emails_to_delete:
            del_email = st.selectbox("Select User Email to Remove", emails_to_delete, key="del_select")
            if st.button("Delete Selected Account", key="btn_del"):
                if delete_user_by_email(del_email):
                    st.success(f"✅ Account {del_email} has been permanently deleted.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to delete account.")
        else:
            st.info("No regular user accounts available to remove.")
    else:
        st.info("No users registered in system.")
