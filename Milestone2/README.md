# FreightQuote AI — Milestone 2: Enterprise Multi-Agent Logistics Intelligence Platform

Welcome to **FreightQuote AI Milestone 2**, an enterprise multi-agent logistics platform built on clean architecture, Python modular design, SQLite relational storage, bcrypt cryptography, PyJWT session management, 3 independent ML Agents, and a 4-bit Quantized LLM Copilot (`Qwen/Qwen2.5-3B-Instruct`).

This milestone extends Milestone 1 with advanced machine learning, automated model selection, structured AI audits, and progressive account lockout security while preserving 100% backward compatibility and exact visual consistency with Milestone 1's UI design system.

---

## 🤖 3 Independent Machine Learning Agents

FreightQuote AI Milestone 2 deploys 3 specialized ML agents trained on logistics trade data:

### 1. Agent 1 — Dynamic Pricing Agent (Regression)
- **Objective**: Predicts freight quote prices ($) dynamically based on distance, cargo weight, container type, fuel index, port congestion, and shipping priority.
- **Algorithms Evaluated (5)**: Random Forest, Gradient Boosting, Extra Trees, Ridge Regression, Decision Tree.
- **Target R²**: $\ge 0.90$.
- **Champion Selection**: Automatically selects highest $R^2$ model, saves `dynamic_pricing_agent.pkl` via `joblib`, and logs metadata in SQLite `ml_models` table.

### 2. Agent 2 — Route Delay Prediction Agent (Classification)
- **Objective**: Classifies shipment delay probability (1 = Delayed, 0 = On-Time).
- **Algorithms Evaluated (5)**: Random Forest, Gradient Boosting, Extra Trees, Logistic Regression, AdaBoost.
- **Metric Optimization**: Evaluates and optimizes **ROC-AUC** score (`roc_auc_score`).
- **Champion Selection**: Automatically selects highest ROC-AUC classifier, saves `route_delay_agent.pkl` via `joblib`, and logs metadata in SQLite `ml_models` table.

### 3. Agent 3 — Carrier Compliance Agent (Classification)
- **Objective**: Classifies carrier compliance status (1 = Compliant, 0 = Non-Compliant / High Risk).
- **Algorithms Evaluated (5)**: Random Forest, Gradient Boosting, Extra Trees, Logistic Regression, Decision Tree.
- **Metric Optimization**: Evaluates and optimizes **ROC-AUC** score (`roc_auc_score`).
- **Champion Selection**: Automatically selects highest ROC-AUC classifier, saves `carrier_compliance_agent.pkl` via `joblib`, and logs metadata in SQLite `ml_models` table.

---

## 🤖 Qwen2.5-3B-Instruct 4-Bit AI Copilot Engine

- **LLM Specification**: `Qwen/Qwen2.5-3B-Instruct`.
- **4-Bit GPU Acceleration**: Loaded using `bitsandbytes` with `load_in_4bit=True` and `torch.float16` compute on Colab T4 GPU.
- **CPU Fallback**: Falls back gracefully to CPU pipeline / expert rule fallback engine when CUDA is unavailable.
- **Multi-Agent Audit Generation**: `produce_structured_audit()` orchestrates predictions from Agent 1, Agent 2, and Agent 3 into verified **Structured JSON Audit Outputs**.

---

## 🔒 Security Upgrades (Preserved from Milestone 1)

1. **Progressive Account Lockout Engine**:
   - 3 failed attempts => 5 min lock (300s)
   - 4 failed attempts => 15 min lock (900s)
   - 5 failed attempts => Permanent lock (`account_status = 'locked'`) requiring Admin unlock.
2. **Live Password Strength Evaluator**:
   - Dynamic score calculation rendering live color badges (🔴 Weak, 🟠 Average, 🟢 Good).
3. **Escalating OTP Resend Cooldown**:
   - Rate limits password reset emails (60s, 180s, 300s, 3600s).

---

## 📁 System Clean Architecture

```
Milestone2/
├── app.py                         # Streamlit application entry point (Dynamic Pricing UI & AI Copilot Desk)
├── auth.py                        # Cryptography, JWT, Progressive Lockout, OTP Cooldown & Password Checker
├── db.py                          # SQLite database engine, schema migrations & ml_models table management
├── ui_theme.py                    # Milestone 1 CSS theme engine & reusable UI components
├── admin_dash.py                  # Admin Control Overview & Admin Account Unlock management
├── train_ml_freight.py            # Master ML training pipeline (Agent 1, Agent 2, Agent 3)
├── llm_engine_freight.py          # Qwen2.5-3B-Instruct 4-bit quantized LLM Copilot Engine
├── models/                        # Joblib model artifact directory (auto-created)
│   ├── dynamic_pricing_agent.pkl
│   ├── route_delay_agent.pkl
│   └── carrier_compliance_agent.pkl
├── requirements.txt               # Milestone 2 Python package dependencies
├── FreightQuote_AI_Milestone2.ipynb # Google Colab & Jupyter Notebook execution workflow
├── README.md                      # Platform documentation (this file)
└── screenshots/                   # Application visual documentation
```

---

## ⚓ Indian Port Coverage Matrix

| Port Name | Port Code | Major Logistics Operations & Cargo Handling | Primary International Corridors |
| :--- | :--- | :--- | :--- |
| **Nhava Sheva (JNPT)** | `INNSA` | Largest container port in India, automated handling | US West Coast, Northern Europe |
| **Mundra Port** | `INMUN` | Largest private commercial port, deep draft berths | Middle East, Mediterranean |
| **Chennai Port** | `INMAA` | Major East Coast hub for automotive and electronics | Far East, Southeast Asia |
| **Kolkata / Haldia** | `INCCU` | Premier riverine port handling bulk & containerized cargo | East Asia, Bangladesh, Nepal |
| **Cochin (Vallarpadam)** | `INCOK` | International Transshipment Terminal | Red Sea, Europe, Direct Americas |
| **Visakhapatnam** | `INVTZ` | Deepwater port specializing in minerals & petroleum | Asia-Pacific, Australia |
| **Tuticorin (V.O.C.)** | `INTUT` | Major Southern hub for textiles & agricultural exports | Gulf Ports, Colombo Transshipment |

---

## ⚙️ Local Setup & Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Train Champion ML Models
```bash
python train_ml_freight.py
```

### 3. Launch Streamlit Portal
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.
