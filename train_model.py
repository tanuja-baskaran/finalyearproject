import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import joblib

# Load dataset
df = pd.read_csv("diabetes_prediction_dataset.csv")

# Handle missing values
df = df.fillna(df.mean(numeric_only=True))    # Numeric NaN → mean
df = df.fillna("Unknown")                     # Categorical NaN → label

# Separate features and target
X = df.drop("diabetes", axis=1)
y = df["diabetes"]

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Encode categorical columns
categorical_cols = X_train.select_dtypes(include=['object']).columns
label_encoders = {}

for col in categorical_cols:
    le = LabelEncoder()
    X_train[col] = le.fit_transform(X_train[col].astype(str))
    X_test[col] = le.transform(X_test[col].astype(str))
    label_encoders[col] = le

# Scale numeric features (for Logistic Regression)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)


print("\nTraining Random Forest...")
rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    random_state=42
)
rf.fit(X_train, y_train)   # No scaling needed for Random Forest
joblib.dump(rf, "model_rf.pkl")
print("✔ Random Forest Saved")

# Save scaler + encoders
joblib.dump(scaler, "scaler.pkl")
joblib.dump(label_encoders, "encoders.pkl")

print("\nTraining complete!")
print("Saved files: model_rf.pkl, scaler.pkl, encoders.pkl")
