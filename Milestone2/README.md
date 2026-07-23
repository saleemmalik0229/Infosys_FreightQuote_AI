# FreightQuote AI — Milestone 2: Enterprise Multi-Agent Logistics Intelligence Platform

Welcome to **FreightQuote AI Milestone 2**, an enterprise multi-agent logistics platform built on clean architecture, Python modular design, SQLite relational storage, bcrypt cryptography, and JWT authentication tokens.

This milestone extends Milestone 1 with enhanced security features, dynamic database schema migrations, and modular ML/LLM pipelines while preserving 100% backward compatibility and exact visual consistency with Milestone 1's UI design system.

---

## 🚀 Key Platform Features & Upgrades

### 1. Progressive Account Lockout Engine
- **3 Failed Attempts**: Account is temporarily locked for **5 minutes** (300 seconds).
- **4 Failed Attempts**: Account is temporarily locked for **15 minutes** (900 seconds).
- **5 Failed Attempts**: Account is **locked** (`account_status = 'locked'`). Permanent unlock requires Administrator action via the Admin Desk.

### 2. Live Password Strength Evaluator
- Evaluates character length, uppercase/lowercase diversity, numbers, and special symbols dynamically as users type.
- Displays a real-time badge in Streamlit:
  - 🔴 **Weak (<5)**: Requires complexity improvements.
  - 🟠 **Average (5-9)**: Meets basic security thresholds.
  - 🟢 **Good (10+)**: Optimal cryptographic resistance.

### 3. Escalating OTP Resend Cooldown
- Protects password recovery against abuse by enforcing escalating delay intervals:
  - 1st Resend: 60 seconds
  - 2nd Resend: 180 seconds (3 minutes)
  - 3rd Resend: 300 seconds (5 minutes)
  - 4th+ Resend: 3600 seconds (1 hour)

### 4. Non-Destructive Database Migrations
- Dynamically updates the `users` table via `PRAGMA table_info` checks:
  - `failed_attempts` (INTEGER)
  - `lock_until` (REAL)
  - `account_status` (TEXT)
- All existing registered users, password hashes, and security credentials remain 100% intact.

---

## 📁 System Clean Architecture

```
Milestone2/
├── app.py                         # Streamlit application entry point
├── auth.py                        # Cryptography, JWT, Progressive Lockout, OTP Cooldown & Password Checker
├── db.py                          # SQLite database engine, schema migrations, and admin data utilities
├── ui_theme.py                    # Milestone 1 CSS theme engine & reusable UI components
├── admin_dash.py                  # Admin Control Overview & Admin Account Unlock management
├── train_ml_freight.py            # Modular Machine Learning pipeline (Freight Quote & Delay models)
├── llm_engine_freight.py          # Modular Multi-Agent LLM Copilot Engine
├── requirements.txt               # Milestone 2 Python package dependencies
├── FreightQuote_AI_Milestone2.ipynb # Google Colab & Jupyter Notebook execution workflow
├── README.md                      # Platform documentation (this file)
└── screenshots/                   # Application visual documentation
```

---

## ⚓ Indian Port Coverage Matrix

FreightQuote AI supports end-to-end logistics analytics and rate generation across major Indian maritime hubs and trade lanes:

| Port Name | Port Code | Major Logistics Operations & Cargo Handling | Primary International Corridors |
| :--- | :--- | :--- | :--- |
| **Nhava Sheva (JNPT)** | `INNSA` | Largest container port in India, automated handling | US West Coast, Northern Europe |
| **Mundra Port** | `INMUN` | Largest private commercial port, deep draft berths | Middle East, Mediterranean |
| **Chennai Port** | `INMAA` | Major East Coast hub for automotive and electronics | Far East, Southeast Asia |
| **Kolkata / Haldia** | `INCCU` | Premier riverine port handling bulk & containerized cargo | East Asia, Bangladesh, Nepal |
| **Cochin (Vallarpadam)** | `INCOK` | International Transshipment Terminal | Red Sea, Europe, Direct Americas |
| **Visakhapatnam** | `INVTZ` | Deepwater port specializing in minerals & petroleum | Asia-Pacific, Australia |
| **Tuticorin (V.O.C.)** | `INTUT` | Major Southern hub for textiles & agricultural exports | Gulf Ports, Colombo Transshipment |
| **Kandla (Deendayal)** | `IXY` | High-volume dry bulk and liquid cargo hub | Gulf Region, East Africa |
| **Mormugao Port** | `INMRM` | Leading ore export terminal & container feeder hub | Western Europe, Asia |
| **Paradip Port** | `INPRT` | Primary East Coast industrial dry bulk transshipment | East Asia, Southeast Asia |

---

## 🔑 Environment Variables & Colab Secrets Setup

The system reads credentials strictly from environment variables or Google Colab Secrets (never hardcoded):

| Variable / Secret Key | Description | Required / Optional |
| :--- | :--- | :--- |
| `JWT_SECRET` | Secret key used to sign session and OTP tokens | Required (Fallback provided) |
| `ADMIN_EMAIL` | Config-driven administrator email | Optional (Default: `infosys@ai`) |
| `ADMIN_PASSWORD` | Config-driven administrator password | Optional (Default: `admin@123`) |
| `EMAIL_ADDRESS` | Gmail address for sending OTP verification emails | Optional (Triggers Sandbox if missing) |
| `EMAIL_PASSWORD` | Gmail App Password for SMTP authentication | Optional (Triggers Sandbox if missing) |
| `HF_TOKEN` | HuggingFace Access Token for LLM multi-agent engine | Optional (Triggers Fallback if missing) |
| `KAGGLE_USERNAME` | Kaggle account username for dataset access | Optional |
| `KAGGLE_KEY` | Kaggle API key token for dataset downloading | Optional |
| `NGROK_AUTHTOKEN` | Auth token for public proxy tunnel deployment | Optional |

---

## 📊 Kaggle API Credentials Setup

To configure Kaggle dataset access in Google Colab or local terminal:

1. Download your `kaggle.json` key from **Kaggle Account Settings -> Create New Token**.
2. Save credentials to environment variables or Colab Secrets:
   ```bash
   export KAGGLE_USERNAME="your_kaggle_username"
   export KAGGLE_KEY="your_kaggle_api_key"
   ```
3. Or write `kaggle.json` programmatically:
   ```python
   import os, json
   kaggle_dir = os.path.expanduser('~/.kaggle')
   os.makedirs(kaggle_dir, exist_ok=True)
   with open(os.path.join(kaggle_dir, 'kaggle.json'), 'w') as f:
       json.dump({"username": os.environ["KAGGLE_USERNAME"], "key": os.environ["KAGGLE_KEY"]}, f)
   os.chmod(os.path.join(kaggle_dir, 'kaggle.json'), 0o600)
   ```

---

## ⚙️ Local Setup & Execution

### 1. Prerequisites
- Python 3.10 or higher.

### 2. Environment Configuration
In `Milestone2/`, create a `.env` file:
```ini
JWT_SECRET=your-secure-jwt-secret-key-2026
ADMIN_EMAIL=infosys@ai
ADMIN_PASSWORD=admin@123
EMAIL_ADDRESS=your-gmail@gmail.com
EMAIL_PASSWORD=your-app-password
NGROK_AUTHTOKEN=your-ngrok-token
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Launch Application
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## 🐍 Google Colab Setup (Ngrok Proxy Tunnel)

1. Open `FreightQuote_AI_Milestone2.ipynb` in Google Colab.
2. Add secrets in Colab Secrets tab (`NGROK_AUTHTOKEN`, `HF_TOKEN`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`).
3. Run notebook cells sequentially to initialize environment, execute DB migrations, and launch Streamlit server with public Ngrok proxy URL.

---

## 📷 Screenshots Section

Visual documentation stored in `Milestone2/screenshots/`:
- `login.png`: Dual-tab User & Admin login screen with progressive lockout notices.
- `signup.png`: Account registration with live password strength badge.
- `forgot_password.png`: Password reset options with escalating OTP cooldown.
- `admin_dashboard.png`: Admin Control Desk & Account Unlocker interface.
- `user_dashboard.png`: System Operations Hub with health index gauge.
