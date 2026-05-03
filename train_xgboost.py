import pandas as pd
import xgboost as xgb
import joblib
import numpy as np
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------
try:
    df = pd.read_csv("diabetes_prediction_dataset.csv")
except FileNotFoundError:
    df = pd.read_csv("data/raw/diabetes_prediction_dataset.csv")

print(f"Data Loaded. Shape: {df.shape}")

# ---------------------------------------------------------
# 2. PREPROCESSING (ALIGNING WITH APP.PY)
# ---------------------------------------------------------
# Order of columns in app.py:
# [gender, age, hypertension, heart_disease, smoking_history, bmi, HbA1c_level, blood_glucose_level]

# 2.1 CLEAN & MAP CATEGORICALS
# Gender: Male=1, Female=0
df = df[df['gender'] != 'Other'] # Optional: drop ambiguous
df['gender'] = df['gender'].apply(lambda x: 1 if x == 'Male' else 0)

# Smoking: Map to Binary (Simple approach for consistency)
# App sends: Yes=1 (if smoker), No=0
# Dataset has: 'never', 'No Info', 'current', 'former', 'ever', 'not current'
# We map 'current', 'former', 'ever', 'not current' -> 1 (Has history), others -> 0
def map_smoking(val):
    if val in ['current', 'former', 'ever', 'not current']:
        return 1
    return 0

df['smoking_history'] = df['smoking_history'].apply(map_smoking)

# 2.2 DEFINE X and y
target = "diabetes"
features = ['gender', 'age', 'hypertension', 'heart_disease', 'smoking_history', 'bmi', 'HbA1c_level', 'blood_glucose_level']

X = df[features].copy()
y = df[target]

print("Features configured. Format:")
print(X.head())

# 2.3 SCALING
# Crucial: We must save the scaler that sees ALL 8 features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ---------------------------------------------------------
# 3. SAVE SCALER
# ---------------------------------------------------------
if not os.path.exists("models"):
    os.makedirs("models")

scaler_path = "models/scaler.pkl"
joblib.dump(scaler, scaler_path)
print(f"✅ Scaler saved to {scaler_path} (Trained on {X.shape[1]} features)")

# ---------------------------------------------------------
# 4. TRAIN MODEL
# ---------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

model = xgb.XGBClassifier(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=6,
    use_label_encoder=False,
    eval_metric='logloss',
    random_state=42
)

model.fit(X_train, y_train)

acc = model.score(X_test, y_test)
print(f"✅ XGBoost Accuracy: {acc * 100:.2f}%")

# ---------------------------------------------------------
# 5. SAVE MODElS
# ---------------------------------------------------------
model_path = "models/model_xgb.pkl"
joblib.dump(model, model_path)
print(f"🎉 Saved XGBoost to {model_path}")


# Train & Save Random Forest
from sklearn.ensemble import RandomForestClassifier
rf_model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
rf_model.fit(X_train, y_train)
joblib.dump(rf_model, "models/model_rf.pkl")
print(f"🎉 Saved Random Forest ({rf_model.score(X_test, y_test)*100:.2f}%)")