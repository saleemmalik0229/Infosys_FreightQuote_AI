import os
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

class FreightMLPredictor:
    """
    Production-ready Machine Learning pipeline architecture for Freight Quote Price
    and Route Delay prediction.
    """
    
    def __init__(self):
        self.quote_model = None
        self.delay_model = None
        self.feature_columns = [
            "origin_hub_code", "dest_hub_code", "cargo_weight_tons",
            "container_type_code", "fuel_price_index", "distance_nautical_miles"
        ]
        
    def generate_synthetic_freight_data(self, samples: int = 1000) -> pd.DataFrame:
        """
        Generates realistic freight logistics dataset covering major Indian ports
        (Nhava Sheva, Mundra, Chennai, Kolkata, Cochin, Visakhapatnam, Tuticorin)
        and global hubs.
        """
        np.random.seed(42)
        
        origins = [101, 102, 103, 104, 105, 106, 107]  # Indian port codes
        dests = [201, 202, 203, 204, 205]              # Global destination codes
        
        data = {
            "origin_hub_code": np.random.choice(origins, size=samples),
            "dest_hub_code": np.random.choice(dests, size=samples),
            "cargo_weight_tons": np.random.uniform(2.0, 35.0, size=samples),
            "container_type_code": np.random.choice([1, 2, 3], size=samples), # 20ft, 40ft, Reefer
            "fuel_price_index": np.random.uniform(85.0, 140.0, size=samples),
            "distance_nautical_miles": np.random.uniform(500, 12000, size=samples)
        }
        
        df = pd.DataFrame(data)
        
        # Synthetic Target 1: Freight Quote Price ($)
        df["freight_price"] = (
            df["distance_nautical_miles"] * 0.45 +
            df["cargo_weight_tons"] * 85.0 +
            df["container_type_code"] * 350.0 +
            df["fuel_price_index"] * 12.0 +
            np.random.normal(0, 150, size=samples)
        )
        
        # Synthetic Target 2: Delay Hours
        df["delay_hours"] = (
            (df["distance_nautical_miles"] / 1000.0) * 4.5 +
            df["container_type_code"] * 2.0 +
            np.random.exponential(scale=5.0, size=samples)
        )
        
        return df

    def train_models(self, data: pd.DataFrame = None):
        """
        Trains RandomForest Regression models for price and delay prediction.
        """
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_squared_error, r2_score
        
        if data is None:
            data = self.generate_synthetic_freight_data()
            
        X = data[self.feature_columns]
        y_price = data["freight_price"]
        y_delay = data["delay_hours"]
        
        X_train, X_test, y_p_train, y_p_test = train_test_split(X, y_price, test_state=42, test_size=0.2)
        _, _, y_d_train, y_d_test = train_test_split(X, y_delay, test_state=42, test_size=0.2)
        
        # Freight Price Model
        self.quote_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.quote_model.fit(X_train, y_p_train)
        p_preds = self.quote_model.predict(X_test)
        p_rmse = np.sqrt(mean_squared_error(y_p_test, p_preds))
        p_r2 = r2_score(y_p_test, p_preds)
        
        # Route Delay Model
        self.delay_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.delay_model.fit(X_train, y_d_train)
        d_preds = self.delay_model.predict(X_test)
        d_rmse = np.sqrt(mean_squared_error(y_d_test, d_preds))
        d_r2 = r2_score(y_d_test, d_preds)
        
        # Save trained models
        try:
            import joblib
            joblib.dump(self.quote_model, os.path.join(MODEL_DIR, "freight_quote_model.pkl"))
            joblib.dump(self.delay_model, os.path.join(MODEL_DIR, "route_delay_model.pkl"))
        except ImportError:
            pass
        
        return {
            "freight_price_rmse": float(p_rmse),
            "freight_price_r2": float(p_r2),
            "route_delay_rmse": float(d_rmse),
            "route_delay_r2": float(d_r2)
        }

    def predict_freight_quote(self, features: dict) -> float:
        """Predicts freight price from input feature vector."""
        if not self.quote_model:
            model_path = os.path.join(MODEL_DIR, "freight_quote_model.pkl")
            if os.path.exists(model_path):
                try:
                    import joblib
                    self.quote_model = joblib.load(model_path)
                except ImportError:
                    pass
            
            if not self.quote_model:
                # Fallback calculation if model not yet trained or joblib missing
                dist = features.get("distance_nautical_miles", 3000)
                weight = features.get("cargo_weight_tons", 10)
                return round(dist * 0.45 + weight * 85.0 + 1200.0, 2)
                
        df_feat = pd.DataFrame([features])[self.feature_columns]
        return float(round(self.quote_model.predict(df_feat)[0], 2))

    def predict_route_delay(self, features: dict) -> float:
        """Predicts estimated transit delay in hours."""
        if not self.delay_model:
            model_path = os.path.join(MODEL_DIR, "route_delay_model.pkl")
            if os.path.exists(model_path):
                try:
                    import joblib
                    self.delay_model = joblib.load(model_path)
                except ImportError:
                    pass
            
            if not self.delay_model:
                dist = features.get("distance_nautical_miles", 3000)
                return round((dist / 1000.0) * 4.5 + 6.0, 1)
                
        df_feat = pd.DataFrame([features])[self.feature_columns]
        return float(round(self.delay_model.predict(df_feat)[0], 1))

if __name__ == "__main__":
    predictor = FreightMLPredictor()
    metrics = predictor.train_models()
    print("✅ Model Training Architecture Validated.")
    print("Metrics:", metrics)
