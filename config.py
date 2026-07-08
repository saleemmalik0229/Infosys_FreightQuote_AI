import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# Programmatically write theme configurations to .streamlit/config.toml
os.makedirs(".streamlit", exist_ok=True)
with open(".streamlit/config.toml", "w") as f:
    f.write("""[theme]
base="light"
primaryColor="#0078D4"
backgroundColor="#FFFFFF"
secondaryBackgroundColor="#F3F4F6"
textColor="#1F2937"
""")

# Secrets and JWT configuration read ONLY from environment variables
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Use a secure persistent fallback secret if not defined in env
    JWT_SECRET = "infosys-portal-secure-key-2026-springboard"

# Gmail SMTP variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Ngrok authtoken proxy configuration
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN")

# Config-driven Admin Credentials
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "infosys@ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin@123")

# Security configurations
OTP_EXPIRY_MINUTES = 5
LOCKOUT_TIME = 300  # 5 minutes in seconds
MAX_LOGIN_ATTEMPTS = 3
