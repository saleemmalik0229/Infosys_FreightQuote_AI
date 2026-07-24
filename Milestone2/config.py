import os
from dotenv import load_dotenv
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Programmatically write Streamlit theme
os.makedirs(".streamlit", exist_ok=True)
with open(".streamlit/config.toml", "w") as f:
    f.write("""[theme]
base="light"
primaryColor="#0078D4"
backgroundColor="#FFFFFF"
secondaryBackgroundColor="#F3F4F6"
textColor="#1F2937"
""")

# ==========================
# Security Configuration
# ==========================

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not defined in .env")

# Gmail SMTP
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Ngrok
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN")

# Kaggle
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME")
KAGGLE_KEY = os.getenv("KAGGLE_KEY")

# Hugging Face
HF_TOKEN = os.getenv("HF_TOKEN")

# Admin Credentials
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "infosys@ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin@123")

# ==========================
# Application Settings
# ==========================

OTP_EXPIRY_MINUTES = 5
LOCKOUT_TIME = 300
MAX_LOGIN_ATTEMPTS = 3