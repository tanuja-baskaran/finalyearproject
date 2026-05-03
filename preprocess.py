import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

def load_data(path):
    df = pd.read_csv(path)
    return df

# 1. STANDARDIZE COLUMN NAMES
COLUMN_MAP = {
    "glu": "blood_glucose_level",
    "glucose": "blood_glucose_level",
    "age_years": "age",
    "sex": "gender",
    "bmi_value": "bmi"
}

def standardize_columns(df):
    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})
    return df

# 2. HARMONIZE DATA TYPES
def harmonize_types(df):
    # strip spaces and lower-case for gender
    df['gender'] = df['gender'].astype(str).str.strip().str.capitalize()

    # Fix smoking history variations
    if 'smoking_history' in df.columns:
        df['smoking_history'] = df['smoking_history'].astype(str).str.strip().str.lower()

    # convert numeric columns
    numeric_cols = ['age', 'bmi', 'HbA1c_level', 'blood_glucose_level']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna()
    return df

# 3. ENCODING CATEGORICAL VARIABLES
def encode_categorical(df):
    encoder = LabelEncoder()
    df['gender'] = encoder.fit_transform(df['gender'])
    df['smoking_history'] = encoder.fit_transform(df['smoking_history'])
    return df

# 4. SCALING NUMERICAL COLUMNS
def scale_features(df):
    scaler = StandardScaler()
    num_cols = ['age', 'bmi', 'HbA1c_level', 'blood_glucose_level']
    df[num_cols] = scaler.fit_transform(df[num_cols])
    return df

# MASTER FUNCTION
def preprocess(path):
    df = load_data(path)
    df = standardize_columns(df)
    df = harmonize_types(df)
    df = encode_categorical(df)
    df = scale_features(df)
    return df
