import json
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any

# Scikit-learn models
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.metrics import accuracy_score, roc_auc_score, precision_score, recall_score, f1_score

# Regression algorithms
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

# Classification algorithms
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, AdaBoostClassifier
from sklearn.svm import SVC

# Set random seed for reproducibility
np.random.seed(42)

def generate_pricing_data(n_samples: int = 1200) -> pd.DataFrame:
    """Generates synthetic freight pricing data."""
    distance = np.random.uniform(50, 3000, n_samples)
    weight = np.random.uniform(1000, 45000, n_samples)
    fuel_index = np.random.uniform(2.5, 5.0, n_samples)
    rating = np.random.uniform(1.0, 5.0, n_samples)
    
    # Target pricing function with complexity and noise
    price = (120 
             + (distance * 1.65) 
             + (weight * 0.045) 
             + (fuel_index * 115) 
             - (rating * 35) 
             + np.random.normal(0, 120, n_samples))
    price = np.clip(price, 120, None)
    
    return pd.DataFrame({
        'distance_miles': distance,
        'weight_lbs': weight,
        'fuel_price_index': fuel_index,
        'carrier_rating': rating,
        'price_usd': price
    })

def generate_route_data(n_samples: int = 1200) -> pd.DataFrame:
    """Generates synthetic route delay prediction data."""
    distance = np.random.uniform(50, 3000, n_samples)
    traffic = np.random.uniform(0.1, 1.0, n_samples)
    weather = np.random.uniform(0.1, 1.0, n_samples)
    carrier_delay_rate = np.random.uniform(0.05, 0.45, n_samples)
    
    # Non-linear probability of delay
    prob = 0.08 + (distance / 3500) * 0.18 + (traffic ** 1.5) * 0.32 + (weather ** 1.2) * 0.28 + carrier_delay_rate * 0.12
    prob = np.clip(prob, 0.02, 0.98)
    is_delayed = np.random.binomial(1, prob)
    
    return pd.DataFrame({
        'distance_miles': distance,
        'traffic_density': traffic,
        'weather_severity': weather,
        'carrier_delay_rate': carrier_delay_rate,
        'is_delayed': is_delayed
    })

def generate_compliance_data(n_samples: int = 1200) -> pd.DataFrame:
    """Generates synthetic carrier compliance classification data."""
    safety_score = np.random.uniform(45, 100, n_samples)
    insurance = np.random.binomial(1, 0.94, n_samples) # 94% have valid insurance
    maintenance = np.random.binomial(1, 0.88, n_samples) # 88% pass safety inspections
    violations = np.random.poisson(0.6, n_samples)
    years = np.random.uniform(1, 20, n_samples)
    
    prob = np.zeros(n_samples)
    for i in range(n_samples):
        if insurance[i] == 0:
            # High probability of non-compliance if no insurance
            prob[i] = 0.02
        else:
            p = 0.35 + (safety_score[i] / 100) * 0.35 + maintenance[i] * 0.20 - min(violations[i] * 0.18, 0.45) + (years[i] / 20) * 0.10
            prob[i] = np.clip(p, 0.01, 0.99)
            
    is_compliant = np.random.binomial(1, prob)
    
    return pd.DataFrame({
        'safety_score': safety_score,
        'insurance_validity': insurance,
        'maintenance_checks_pass': maintenance,
        'violations_count': violations,
        'years_in_service': years,
        'is_compliant': is_compliant
    })

def train_pricing_models() -> Dict[str, Any]:
    df = generate_pricing_data()
    X = df.drop(columns=['price_usd'])
    y = df['price_usd']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train 5 different regression models
    models = {
        'Linear Regression': LinearRegression(),
        'Ridge': Ridge(alpha=1.0),
        'Lasso': Lasso(alpha=0.1),
        'Decision Tree': DecisionTreeRegressor(max_depth=6, random_state=42),
        'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
    }
    
    results = {}
    best_model_name = None
    best_r2 = -float('inf')
    best_model = None
    
    for name, model in models.items():
        model.fit(X_train_scaled, y_train)
        preds = model.predict(X_test_scaled)
        
        r2 = r2_score(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        mae = mean_absolute_error(y_test, preds)
        
        results[name] = {'R2': float(r2), 'RMSE': float(rmse), 'MAE': float(mae)}
        
        if r2 > best_r2:
            best_r2 = r2
            best_model_name = name
            best_model = model
            
    # Save best models
    joblib.dump(scaler, "pricing_scaler.joblib")
    joblib.dump(best_model, "best_pricing_model.joblib")
    
    with open("pricing_metrics.json", "w") as f:
        json.dump({"best_model": best_model_name, "metrics": results}, f, indent=4)
        
    return {"best": best_model_name, "metrics": results}

def train_route_delay_models() -> Dict[str, Any]:
    df = generate_route_data()
    X = df.drop(columns=['is_delayed'])
    y = df['is_delayed']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train 5 classification models
    models = {
        'Logistic Regression': LogisticRegression(),
        'Decision Tree': DecisionTreeClassifier(max_depth=5, random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42),
        'SVC': SVC(probability=True, random_state=42)
    }
    
    results = {}
    best_model_name = None
    best_f1 = -float('inf')
    best_model = None
    
    for name, model in models.items():
        model.fit(X_train_scaled, y_train)
        preds = model.predict(X_test_scaled)
        
        try:
            probs = model.predict_proba(X_test_scaled)[:, 1]
            auc = roc_auc_score(y_test, probs)
        except Exception:
            auc = 0.5
            
        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        
        results[name] = {
            'Accuracy': float(acc),
            'ROC-AUC': float(auc),
            'Precision': float(prec),
            'Recall': float(rec),
            'F1': float(f1)
        }
        
        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_model = model
            
    joblib.dump(scaler, "route_scaler.joblib")
    joblib.dump(best_model, "best_route_delay_model.joblib")
    
    with open("route_metrics.json", "w") as f:
        json.dump({"best_model": best_model_name, "metrics": results}, f, indent=4)
        
    return {"best": best_model_name, "metrics": results}

def train_carrier_compliance_models() -> Dict[str, Any]:
    df = generate_compliance_data()
    X = df.drop(columns=['is_compliant'])
    y = df['is_compliant']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train 5 classification models
    models = {
        'Logistic Regression': LogisticRegression(),
        'Decision Tree': DecisionTreeClassifier(max_depth=5, random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42),
        'AdaBoost': AdaBoostClassifier(n_estimators=100, random_state=42)
    }
    
    results = {}
    best_model_name = None
    best_f1 = -float('inf')
    best_model = None
    
    for name, model in models.items():
        model.fit(X_train_scaled, y_train)
        preds = model.predict(X_test_scaled)
        
        try:
            probs = model.predict_proba(X_test_scaled)[:, 1]
            auc = roc_auc_score(y_test, probs)
        except Exception:
            auc = 0.5
            
        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        
        results[name] = {
            'Accuracy': float(acc),
            'ROC-AUC': float(auc),
            'Precision': float(prec),
            'Recall': float(rec),
            'F1': float(f1)
        }
        
        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_model = model
            
    joblib.dump(scaler, "compliance_scaler.joblib")
    joblib.dump(best_model, "best_carrier_compliance_model.joblib")
    
    with open("compliance_metrics.json", "w") as f:
        json.dump({"best_model": best_model_name, "metrics": results}, f, indent=4)
        
    return {"best": best_model_name, "metrics": results}

def run_ml_pipeline():
    """Runs training on all 3 agents and prints select best model metrics."""
    print("Training Agent 1: Dynamic Freight Pricing...")
    pricing = train_pricing_models()
    print("Training Agent 2: Route Delay Prediction...")
    route = train_route_delay_models()
    print("Training Agent 3: Carrier Compliance Classifier...")
    compliance = train_carrier_compliance_models()
    
    # Write Model Card Markdown file
    model_card_md = f"""# FreightQuote AI - Machine Learning Model Card

This model card details the execution results, dataset parameters, and selected models for FreightQuote AI.

## Agent 1: Dynamic Freight Pricing (Regression)
- **Objective**: Predict price_usd for a given shipment.
- **Winner Algorithm**: **{pricing['best']}**
- **Validation Metrics**:
  - R²: {pricing['metrics'][pricing['best']]['R2']:.4f}
  - RMSE: ${pricing['metrics'][pricing['best']]['RMSE']:.2f}
  - MAE: ${pricing['metrics'][pricing['best']]['MAE']:.2f}

## Agent 2: Route Delay Prediction (Classification)
- **Objective**: Classify whether a scheduled route will suffer from transit delays.
- **Winner Algorithm**: **{route['best']}**
- **Validation Metrics**:
  - Accuracy: {route['metrics'][route['best']]['Accuracy']:.4f}
  - ROC-AUC: {route['metrics'][route['best']]['ROC-AUC']:.4f}
  - Precision: {route['metrics'][route['best']]['Precision']:.4f}
  - Recall: {route['metrics'][route['best']]['Recall']:.4f}
  - F1-Score: {route['metrics'][route['best']]['F1']:.4f}

## Agent 3: Carrier Compliance Prediction (Classification)
- **Objective**: Check if a carrier complies with regulatory guidelines (safety score, insurance validity, etc.).
- **Winner Algorithm**: **{compliance['best']}**
- **Validation Metrics**:
  - Accuracy: {compliance['metrics'][compliance['best']]['Accuracy']:.4f}
  - ROC-AUC: {compliance['metrics'][compliance['best']]['ROC-AUC']:.4f}
  - Precision: {compliance['metrics'][compliance['best']]['Precision']:.4f}
  - Recall: {compliance['metrics'][compliance['best']]['Recall']:.4f}
  - F1-Score: {compliance['metrics'][compliance['best']]['F1']:.4f}
"""
    with open("ml_model_card.md", "w") as f:
        f.write(model_card_md)
        
    print("\nML Model Pipeline Executed & Model Card Written.")
