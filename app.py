import streamlit as st # type: ignore
import numpy as np # type: ignore
import pandas as pd # type: ignore
import joblib # type: ignore
from pathlib import Path
import plotly.figure_factory as ff # type: ignore
import plotly.graph_objects as go # type: ignore
from fpdf import FPDF # type: ignore
import base64
from datetime import datetime, timedelta
import time
import os
try:
    from dotenv import load_dotenv # type: ignore
    load_dotenv(override=True)
except ImportError:
    pass
import json
import threading
import re
import io
import logging
import urllib.parse
import subprocess
import socket
# ── Configure logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("HealthAI")


# ── New module imports ─────────────────────────────────────────────────────────
try:
    from database import init_db, save_health_record, get_health_records, delete_health_record # type: ignore
    DB_AVAILABLE = True
except Exception as _db_err:
    DB_AVAILABLE = False
    logger.warning("database.py unavailable: %s", _db_err)

# ── Reminder Engine ───────────────────────────────────────────────────────────
try:
    import reminder_engine as re_eng  # type: ignore
    RE_AVAILABLE = True
except Exception as _re_err:
    RE_AVAILABLE = False
    logger.warning("reminder_engine unavailable: %s", _re_err)

# Chatbot moved to separate FastAPI (chat_api.py)
CHATBOT_MODULE = True

try:
    from voice_handler import transcribe as voice_transcribe, check_dependencies as voice_check # type: ignore
    VOICE_MODULE = True
except Exception as _vh_err:
    VOICE_MODULE = False
    logger.warning("voice_handler.py unavailable: %s", _vh_err)
try:
    from streamlit_mic_recorder import mic_recorder # type: ignore
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False
try:
    import speech_recognition as sr # type: ignore
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
try:
    from gtts import gTTS # type: ignore
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
try:
    import av as _av_lib # type: ignore
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False

st.set_page_config(
    page_title="DiabetesGuard Pro – HealthAI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------
# THEME MANAGEMENT
# -----------------------------------------------------
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

THEMES = {
    "light": {
        "primary": "#2563EB",
        "secondary": "#10B981",
        "background": "#F8FAFC",
        "surface": "#FFFFFF",
        "text_primary": "#1E293B",
        "text_secondary": "#64748B",
        "border": "#E2E8F0",
        "danger": "#EF4444",
        "warning": "#F59E0B",
    }
}

current_theme = THEMES["light"]

st.markdown(f"""
    <style>
    :root {{
        --primary-color: {current_theme['primary']};
        --secondary-color: {current_theme['secondary']};
        --background-color: {current_theme['background']};
        --surface-color: {current_theme['surface']};
        --text-primary: {current_theme['text_primary']};
        --text-secondary: {current_theme['text_secondary']};
        --border-color: {current_theme['border']};
    }}
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------
# CUSTOM CSS
# -----------------------------------------------------
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, .stApp {
        font-family: 'Inter', sans-serif !important;
        background-color: #F8FAFC;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translate3d(0, 20px, 0); }
        to { opacity: 1; transform: translate3d(0, 0, 0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(37, 99, 235, 0); }
        100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
    }

    .stChatInputContainer { padding-bottom: 1rem; }

    .glass-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        animation: fadeInUp 0.4s ease both;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08);
    }

    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        border: none;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        padding: 0.5rem 1rem;
    }
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    .stButton>button:hover { transform: translateY(-2px); }

    .result-card-high {
        background: linear-gradient(135deg, #FEE2E2 0%, #FECACA 100%);
        border: 1.5px solid #F87171;
        border-radius: 20px;
        padding: 28px 24px;
        text-align: center;
        animation: fadeInUp 0.5s ease both;
    }
    .result-card-low {
        background: linear-gradient(135deg, #D1FAE5 0%, #A7F3D0 100%);
        border: 1.5px solid #34D399;
        border-radius: 20px;
        padding: 28px 24px;
        text-align: center;
        animation: fadeInUp 0.5s ease both;
    }
    .result-label { font-size: 1.3rem; font-weight: 800; margin: 8px 0; }
    .result-pct { font-size: 2.8rem; font-weight: 900; line-height: 1; }
    .result-sub { font-size: 0.85rem; color: #475569; margin-top: 8px; }

    .stat-badge {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 12px 8px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stat-badge .val { font-size: 1.4rem; font-weight: 800; color: #1E293B; }
    .stat-badge .lbl { font-size: 0.65rem; color: #64748B; font-weight: 500; text-transform: uppercase; letter-spacing: 0.07em; }

    .rec-chip {
        display: inline-block;
        background: #F1F5F9;
        border: 1px solid #E2E8F0;
        border-radius: 20px;
        padding: 6px 14px;
        font-size: 0.82rem;
        margin: 3px 4px;
        color: #334155;
    }

    .dash-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 22px 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
        position: relative;
        overflow: hidden;
    }
    .dash-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.09); }
    .dash-card-icon { font-size: 1.8rem; margin-bottom: 8px; display: block; }
    .dash-card-value { font-size: 2.2rem; font-weight: 800; line-height: 1; margin-bottom: 4px; }
    .dash-card-label { font-size: 0.78rem; color: #64748B; font-weight: 500; text-transform: uppercase; letter-spacing: 0.07em; }
    .dash-card-delta { font-size: 0.8rem; font-weight: 600; margin-top: 6px; }

    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
    </style>
""", unsafe_allow_html=True)

script_dir = Path(__file__).parent

# -----------------------------------------------------
# SESSION STATE
# -----------------------------------------------------
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = True
if 'prediction_history' not in st.session_state:
    st.session_state.prediction_history = []
if 'dashboard_data' not in st.session_state:
    st.session_state.dashboard_data = {
        'glucose': 105, 'bmi': 24.5,
        'risk_label': 'Low', 'risk_delta': 'Stable', 'health_score': 85
    }

# Chat sessions for rule-based engine
if 'chat_sessions' not in st.session_state:
    st.session_state.chat_sessions = [
        {"id": 0, "title": "New Chat", "messages": [
            {"role": "assistant", "content": "Hello! I am your rule-based clinical assistant. I can define medical terms, explain diabetes types, HbA1c, insulin, and basic symptoms."}
        ]}
    ]
if 'active_chat_id' not in st.session_state:
    st.session_state.active_chat_id = 0

# Voice assistant state
if 'voice_enabled' not in st.session_state:
    st.session_state.voice_enabled = True
if 'last_voice_audio' not in st.session_state:
    st.session_state.last_voice_audio = None
if 'voice_prompt' not in st.session_state:
    st.session_state.voice_prompt = None
if 'mic_key_counter' not in st.session_state:
    st.session_state.mic_key_counter = 0
# API key (populated from sidebar input)
if 'huggingface_api_key' not in st.session_state:
    st.session_state.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY", "")

# ── Initialise database ────────────────────────────────────────────────────────
if DB_AVAILABLE:
    try:
        init_db()
    except Exception as _e:
        logger.error("DB init failed: %s", _e)

# -----------------------------------------------------
# HELPER: LOAD RESOURCES
# -----------------------------------------------------
@st.cache_resource
def load_resource(filenames, description):
    for fname in filenames:
        p = script_dir / fname
        if p.exists():
            try:
                return joblib.load(p)
            except Exception:
                pass
        p2 = script_dir / "models" / fname
        if p2.exists():
            try:
                return joblib.load(p2)
            except Exception:
                pass
    return None

scaler = load_resource(["scaler.pkl"], "Scaler")
if not scaler:
    st.error("❌ Critical Error: Scaler file missing.")
    st.stop()

models_dict = {
    "Random Forest":       "model_rf.pkl",
    "XGBoost":             "model_xgb.pkl"
}

def get_model(name):
    return load_resource([models_dict[name]], name)

@st.cache_data
def load_data():
    for fname in ["diabetes_prediction_dataset.csv", "diabetes.csv"]:
        p = script_dir / fname
        if p.exists():
            try:
                return pd.read_csv(p)
            except Exception:
                pass
    return pd.DataFrame()

df_population = load_data()

# -----------------------------------------------------
# PDF REPORT
# -----------------------------------------------------
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "HealthAI Medical Report", ln=True, align="C")
        self.ln(4)
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} | Not a medical diagnosis", align="C")

def generate_pdf(details: dict, risk_score: float, advice: list) -> bytes:
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, "Patient Details", ln=True)
    pdf.set_font("Arial", "", 11)
    for k, v in details.items():
        pdf.cell(0, 7, f"  {k}: {v}", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, f"Risk Score: {risk_score*100:.1f}%", ln=True)
    pdf.set_font("Arial", "", 11)
    for item in advice:
        clean = re.sub(r'[^\x00-\x7F]+', '', str(item))
        pdf.cell(0, 7, f"  - {clean}", ln=True)
    out = pdf.output(dest='S')
    return out if isinstance(out, bytes) else out.encode('latin-1')

def create_download_link(val: bytes, filename: str) -> str:
    b64 = base64.b64encode(val).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" style="display:inline-block;background:linear-gradient(135deg,#2563EB,#1D4ED8);color:white;padding:10px 20px;border-radius:10px;text-decoration:none;font-weight:600;font-size:0.9rem;">📄 Download PDF Report</a>'

def get_ai_response(user_input: str) -> str:
    import os
    try:
        from huggingface_hub import InferenceClient # type: ignore
    except ImportError:
        return "Error: `huggingface_hub` package is missing. Please run `pip install huggingface_hub`."
        
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return "Hey! I cannot process your request without a Hugging Face API key. Please add it to your `.env` file."
        
    try:
        # We use Zephyr as our reliable free-tier Serverless chat model
        client = InferenceClient(model="HuggingFaceH4/zephyr-7b-beta", token=api_key)
        
        system_prompt = """You are a healthcare assistant focused on diabetes.

Response Rules:
- Answer in bullet points only
- Keep it short and simple (max 5–7 points)
- Use easy language for beginners
- Do NOT write paragraphs
- Highlight key terms in bold
- Stay strictly on the topic

If the question is outside health/diabetes:
Say: "I can only help with diabetes-related questions."
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        response = client.chat_completion(messages=messages, max_tokens=180, temperature=0.5)
        ans = response.choices[0].message.content # type: ignore
        
        # If the model echoes the prompt, keep only the text after [/INST]
        if "[/INST]" in ans:
            ans = ans.split("[/INST]")[-1]
            
        # Strip subsequent hallucinated turns
        for token in ["[/USER]", "<|user|>", "<|assistant|>"]:
            if token in ans:
                ans = ans.split(token)[0]
                
        # Clean up any remaining generation artifacts
        for token in ["<s>", "</s>", "[INST]", "\u200b"]:
            ans = ans.replace(token, "")
            
        return ans.strip()
    except Exception as e:
        return f"API Error via HuggingFace Hub: {str(e)}"

# -----------------------------------------------------
# REMINDER SYSTEM
# -----------------------------------------------------
def get_reminder_system():
    class SimpleReminderSystem:
        def __init__(self):
            self.path = script_dir / "reminders.json"
        def load_reminders(self):
            try:
                if self.path.exists():
                    with open(self.path) as f:
                        data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception:
                pass
            return []
        def save_reminder(self, name, time_str, days):
            reminders = self.load_reminders()
            new_id = max([r.get('id', 0) for r in reminders], default=0) + 1
            reminders.append({"id": new_id, "name": name, "time": time_str, "days": days})
            with open(self.path, 'w') as f:
                json.dump(reminders, f)
        def update_reminder(self, rem_id, name, time_str, days):
            reminders = self.load_reminders()
            for r in reminders:
                if r['id'] == rem_id:
                    r['name'] = name; r['time'] = time_str; r['days'] = days
            with open(self.path, 'w') as f:
                json.dump(reminders, f)
        def delete_reminder(self, rem_id):
            reminders = [r for r in self.load_reminders() if r['id'] != rem_id]
            with open(self.path, 'w') as f:
                json.dump(reminders, f)
    return SimpleReminderSystem()

# -----------------------------------------------------
# DIET PDF GENERATOR
# -----------------------------------------------------
def _pdf_safe(text: str) -> str:
    """Sanitise text for PyFPDF which only supports latin-1 encoding."""
    t = str(text)
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2014': '-', '\u2013': '-',  # em-dash, en-dash
        '\u2018': "'", '\u2019': "'",  # smart quotes
        '\u201c': '"', '\u201d': '"',
        '\u2026': '...', '\u00d7': 'x',  # ellipsis, multiplication sign
        '\u2022': '*',  # bullet
    }
    for uni_char, ascii_char in replacements.items():
        t = t.replace(uni_char, ascii_char)
    # Strip remaining non-latin-1 characters (emojis etc.)
    t = re.sub(r'[^\x00-\xFF]', '', t)
    return t.strip()

def generate_diet_pdf(diet: dict, prob: float, age: int, bmi: float, gender: str) -> bytes:
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 10, _pdf_safe(f"HealthAI Personalised Diet Plan - {diet['tier']} RISK"), ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 7, _pdf_safe(f"Generated: {datetime.now().strftime('%B %d, %Y')}  |  Age: {age}  |  BMI: {bmi:.1f}  |  Gender: {gender}"), ln=True, align="C")
    pdf.ln(4)

    def section(title, items, bullet="- "):
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, _pdf_safe(title), ln=True)
        pdf.set_font("Arial", "", 10)
        for item in items:
            pdf.cell(0, 6, _pdf_safe(f"  {bullet}{item}"), ln=True)
        pdf.ln(2)

    pdf.set_font("Arial", "I", 10)
    pdf.multi_cell(0, 6, _pdf_safe(diet['intro']))
    pdf.ln(4)
    section("Foods to Include", diet['foods_include'])
    section("Foods to Avoid", diet['foods_avoid'])
    section("Hydration Tips", diet['hydration'])
    section("Lifestyle Recommendations", diet['lifestyle'])
    section("Sample Daily Meal Plan", [
        f"Breakfast: {diet['meal_plan']['Breakfast']}",
        f"Mid-Morning: {diet['meal_plan']['Mid-Morning']}",
        f"Lunch: {diet['meal_plan']['Lunch']}",
        f"Evening Snack: {diet['meal_plan']['Evening Snack']}",
        f"Dinner: {diet['meal_plan']['Dinner']}",
        f"Estimated Calories: {diet['meal_plan']['Calories']}",
    ])
    pdf.set_font("Arial", "I", 9)
    pdf.multi_cell(0, 6, "DISCLAIMER: This is not a medical diagnosis. These are general guidelines only. "
                          "Please consult a qualified healthcare professional or registered dietitian "
                          "before making any significant dietary changes.")
    out = pdf.output(dest='S')
    return out if isinstance(out, bytes) else out.encode('latin-1')

# -----------------------------------------------------
# DIET RECOMMENDATIONS
# -----------------------------------------------------
def get_diet_recommendations(prob, age, bmi, gender):

    # ── Personalise based on age & BMI ────────────────────────────
    senior = age >= 60
    young  = age <= 30
    obese  = bmi >= 30
    overwt = bmi >= 25
    bmi_note = (
        f"Your BMI is {bmi:.1f} (Obese). Weight reduction is medically critical."
        if obese else
        f"Your BMI is {bmi:.1f} (Overweight). Aim to reach 18.5–24.9."
        if overwt else
        f"Your BMI is {bmi:.1f} (Healthy). Maintain your current weight."
    )
    age_note = (
        "As a senior (60+), focus on maintaining muscle mass and bone density alongside blood sugar control."
        if senior else
        "At your age, prevention through lifestyle changes is highly effective."
        if young else
        "At this life stage, consistent dietary habits and regular check-ups are key."
    )

    if prob > 0.70:
        tier = "HIGH"
        tier_color = "#DC2626"
        tier_bg = "#FFF1F2"
        tier_border = "#FECDD3"
        tier_icon = "🔴"
        headline = "Strict Diabetic Nutrition Therapy Required"
        intro = (
            f"With a {prob*100:.0f}% risk score, your profile indicates a high likelihood of diabetes. "
            f"{bmi_note} {age_note} "
            "Immediate dietary intervention, medical consultation, and daily monitoring are essential."
        )
        foods_include = [
            "🥦 Non-starchy vegetables (spinach, broccoli, karela) — fill half your plate",
            "🌾 Barley, oats, ragi — high fiber, lowest GI grains",
            "🫘 Masoor dal, moong dal, chickpeas — protein + fiber combo",
            "🥚 Egg whites, grilled fish, tofu, paneer (small portions)",
            "🫐 Berries, guava, jamun — low Sugar fruits only",
            "🥜 5–6 almonds or walnuts daily (healthy fats)",
            "🧄 Garlic, fenugreek seeds (methi) — natural blood sugar modulators",
        ]
        foods_avoid = [
            "🍬 All sweets, mithai, chocolates — strictly avoid",
            "🍚 White rice, maida, white bread — high glycemic, dangerous",
            "🥤 Cold drinks, packaged juices, energy drinks",
            "🍟 All deep-fried foods (samosa, puri, pakora)",
            "🍌 High-sugar fruits (mango, banana, grapes, chikoo)",
            "🧁 Biscuits, cakes, cookies",
            "🍺 Alcohol & smoking — accelerates complications",
        ]
        hydration = [
            "💧 3.5–4 litres of plain water daily",
            "🍵 Methi water (soaked overnight) every morning",
            "🫖 Cinnamon tea or tulsi tea — helps insulin sensitivity",
            "🚫 Avoid all sweetened beverages completely",
        ]
        lifestyle = [
            f"🏃 45 min moderate exercise, 6 days/week {'(low-impact if senior)' if senior else ''}",
            "🩸 Monitor fasting & post-meal blood sugar daily",
            f"⚖️ {'Critical to lose 5–10% body weight — start with 0.5 kg/week' if obese else 'Maintain healthy BMI — even small weight loss helps'}",
            "😴 7–8 hours of uninterrupted sleep every night",
            "🧘 Stress management: 10 min deep breathing or meditation daily",
            "🩺 Consult an endocrinologist within the next 2 weeks",
        ]
        portion_tip = "Use the diabetic plate rule: 1/2 plate non-starchy vegetables, 1/4 plate lean protein, 1/4 plate low-GI grains. No second servings. Eat on a 9-inch plate."
        meal_plan = {
            "Breakfast": "Oat porridge with chia seeds + 1 boiled egg + green tea (no sugar)",
            "Mid-Morning": "5 almonds + 1 small guava or 10 jamuns",
            "Lunch": "1 cup brown rice / 2 jowar rotis + moong dal + mixed sabzi (no potato) + salad",
            "Evening Snack": "Roasted chana (30g) + cucumber sticks + methi water",
            "Dinner": "2 multigrain rotis + palak paneer / fish curry + karela sabzi + chaas",
            "Calories": "1,400–1,600 kcal (strict caloric control required)",
        }
    elif prob > 0.30:
        tier = "MODERATE"
        tier_color = "#D97706"
        tier_bg = "#FFFBEB"
        tier_border = "#FDE68A"
        tier_icon = "🟡"
        headline = "Preventive Blood Sugar Control Diet"
        intro = (
            f"Your {prob*100:.0f}% risk score places you in the moderate risk zone — this is the best time to act. "
            f"{bmi_note} {age_note} "
            "Switching to a low glycemic index diet now can prevent progression to diabetes."
        )
        foods_include = [
            "🥗 Leafy greens (palak, methi, coriander) + colourful vegetables daily",
            "🍎 Low-GI fruits: apple, pear, papaya, guava, pomegranate",
            "🌾 Brown rice, whole wheat atta, jowar, bajra, oats",
            "🥚 Eggs, paneer, tofu, dal, lean chicken (non-fried)",
            "🫘 Rajma, chana, sprouts — excellent low-GI protein",
            "🥜 Almonds, walnuts, flaxseeds — small portions daily",
            "🧄 Include haldi (turmeric), methi seeds, jeera in cooking",
        ]
        foods_avoid = [
            "🍭 Indian sweets, mithai, jalebi, gulab jamun",
            "🥤 Cold drinks, packaged juices, energy drinks",
            "🍕 Maida-based foods: naan, white bread, biscuits",
            "🍔 Fast food, fried snacks, chips, namkeen",
            "🛢️ Trans fats: vanaspati, margarine, dalda",
            "🍌 Limit high-sugar fruits (mango, banana — max 1/day)",
        ]
        hydration = [
            "💧 2.5–3 litres of water daily",
            "🍵 Green tea or tulsi tea (1–2 cups, no sugar)",
            "🥛 Buttermilk (chaas) — great post-meal option",
            "🫖 Coriander seed water or methi water in the morning",
        ]
        lifestyle = [
            f"🚶 30–40 min brisk walk, 5 days/week {'(pool walking or yoga if joints are a concern)' if senior else ''}",
            "🧘 Yoga, pranayama, or meditation for stress control",
            f"⚖️ {'Target BMI under 27 — lose 0.3–0.5 kg/week gradually' if overwt else 'Maintain your healthy weight with regular activity'}",
            "🩺 Get HbA1c tested every 6 months",
            "🚭 Quit smoking — doubles diabetes progression risk",
        ]
        portion_tip = "Use a smaller 9-inch plate. Eat 3 main meals + 2 light snacks. Never skip breakfast. Chew slowly — it takes 20 mins for satiety signals to reach your brain."
        meal_plan = {
            "Breakfast": "Vegetable upma (suji/semolina) OR 2 moong dal chilla + green tea",
            "Mid-Morning": "1 apple or pear + 5 walnuts",
            "Lunch": "2 whole wheat chapatis + dal (any) + vegetable sabzi + curd",
            "Evening Snack": "Sprout chaat or roasted makhana (fox nuts) + tulsi tea",
            "Dinner": "2 multigrain rotis + dal tadka + mixed sabzi + a small bowl of curd",
            "Calories": "1,600–1,900 kcal (moderate restriction)",
        }
    else:
        tier = "LOW"
        tier_color = "#059669"
        tier_bg = "#F0FDF4"
        tier_border = "#BBF7D0"
        tier_icon = "🟢"
        headline = "Balanced Preventive Nutrition Plan"
        intro = (
            f"Great news — your {prob*100:.0f}% risk score is in the healthy range! "
            f"{bmi_note} {age_note} "
            "Continue these healthy habits and stay proactive with regular screenings."
        )
        foods_include = [
            "🥗 Rainbow of vegetables and seasonal fruits daily",
            "🌾 Whole grains: brown rice, oats, multigrain atta",
            "🐟 Lean proteins: dal, eggs, fish, chicken, paneer",
            "🥛 Low-fat dairy: curd, chaas, skimmed milk",
            "🫒 Healthy fats: mustard oil, ghee (small amounts), nuts",
            "🌰 Almonds, walnuts, sunflower seeds as snacks",
            "🫚 Include coconut, flaxseed, sesame in cooking",
        ]
        foods_avoid = [
            "🍟 Limit deep-fried foods to once a week max",
            "🥤 Restrict sugary beverages to special occasions",
            "🍰 Limit desserts and sweets — enjoy mindfully",
            "🧂 Watch sodium intake (avoid excess processed/packaged food)",
        ]
        hydration = [
            "💧 2–3 litres of water daily",
            "🍵 Herbal tea, green tea, or nimbu paani (no sugar)",
            "🥛 Coconut water is an excellent natural hydrator",
            "🚫 Minimise caffeinated & sweetened drinks",
        ]
        lifestyle = [
            f"🚶 7,000–10,000 steps daily {'or equivalent low-impact activity' if senior else ''}",
            "💪 Include strength or resistance training 2–3×/week",
            "😴 7–8 hours of quality sleep nightly",
            "🎯 Annual health check-up including fasting blood glucose",
            "🧘 Keep stress low — chronic stress raises blood sugar",
        ]
        portion_tip = "No strict restrictions needed, but practice mindful eating. Enjoy all food groups in balance. Follow the 80% rule — stop eating when you feel 80% full."
        meal_plan = {
            "Breakfast": "Poha / idli + sambar OR oats with fruits + tea/coffee (less sugar)",
            "Mid-Morning": "Seasonal fruit (any) + a handful of nuts",
            "Lunch": "2 chapatis + dal + sabzi + curd + salad",
            "Evening Snack": "Roasted makhana / sprouts / fruit chaat + tea",
            "Dinner": "2 chapatis / rice + sabzi + dal + a small bowl of curd",
            "Calories": "1,800–2,200 kcal (balanced for healthy weight maintenance)",
        }

    return {
        "tier": tier, "tier_color": tier_color, "tier_bg": tier_bg,
        "tier_border": tier_border, "tier_icon": tier_icon,
        "headline": headline, "intro": intro,
        "foods_include": foods_include, "foods_avoid": foods_avoid,
        "hydration": hydration, "lifestyle": lifestyle,
        "portion_tip": portion_tip, "meal_plan": meal_plan,
        "bmi_note": bmi_note, "age_note": age_note,
    }

# -----------------------------------------------------
# SMART MEAL PLANNER
# -----------------------------------------------------
def get_smart_meal_plan(age, gender, bmi, glucose, hba1c, risk_prob, preference="Vegetarian"):
    veg = preference.lower() in ["vegetarian", "vegan"]
    protein = "tofu or paneer" if veg else "grilled chicken or fish"
    high_risk = risk_prob > 0.5
    plan = {
        "Breakfast": f"{'Oats porridge with chia seeds' if high_risk else 'Whole wheat upma'} + Green tea",
        "Mid-Morning": "Small apple + 5 almonds",
        "Lunch": f"Brown rice + Vegetable dal + Salad + {protein}",
        "Evening Snack": "Roasted chana or cucumber sticks with hummus",
        "Dinner": f"Roti (2) + Sabzi + Dal + {'Sprout salad' if veg else 'Egg whites or grilled fish'}",
        "Calories": f"{'1400–1600' if high_risk else '1600–2000'} kcal approx.",
        "Note": "Adjust portions based on appetite. Eat slowly and mindfully."
    }
    return plan

# -----------------------------------------------------
# RULE-BASED ENGINE
# -----------------------------------------------------
def get_rule_based_response(user_input):
    user_input = user_input.lower()
    
    # Predefined medical rules
    if re.search(r'\b(hi|hello|hey|greetings)\b', user_input):
        return "Hello! I am a clinical rule-based assistant. Ask me about diabetes, HbA1c, insulin, or symptoms."
    elif re.search(r'\b(diabetes)\b', user_input):
        if re.search(r'\b(type 1|type i)\b', user_input):
            return "Type 1 diabetes is a chronic condition in which the pancreas produces little or no insulin. It is typically diagnosed in childhood or adolescence."
        elif re.search(r'\b(type 2|type ii)\b', user_input):
            return "Type 2 diabetes affects how your body metabolizes sugar (glucose), typically resulting from insulin resistance. It often develops in adults but is increasingly seen in younger age groups."
        elif re.search(r'\b(symptoms|signs)\b', user_input):
            return "Common symptoms of diabetes include increased thirst, frequent urination, extreme hunger, unexplained weight loss, fatigue, irritability, and blurred vision."
        else:
            return "Diabetes is a chronic illness that occurs when blood glucose is too high. I can explain Type 1, Type 2, or common symptoms."
    elif re.search(r'\b(hba1c|a1c|blood sugar|glucose)\b', user_input):
        return "The HbA1c test measures average blood sugar levels over the past 3 months. Normal is below 5.7%, prediabetes is 5.7% to 6.4%, and 6.5%+ indicates diabetes."
    elif re.search(r'\b(insulin)\b', user_input):
        return "Insulin is a hormone made by the pancreas that allows your body to use sugar (glucose) from carbohydrates in the food that you eat for energy or storage."
    elif re.search(r'\b(bmi|weight|diet)\b', user_input):
        return "Maintaining a healthy Body Mass Index (BMI) through a balanced diet and regular exercise is crucial for managing and preventing diabetes."
    elif re.search(r'\b(blood pressure|hypertension)\b', user_input):
        return "Hypertension (high blood pressure) often coexists with diabetes. Maintaining blood pressure below 130/80 mmHg is recommended for most individuals with diabetes."
    elif re.search(r'\b(cure|treat|medication)\b', user_input):
        return "While diabetes has no definitive cure, it is managed effectively through diet, exercise, and medication (like insulin or metformin). Always consult a physician for a treatment plan."
    elif re.search(r'\b(heart|cardio)\b', user_input):
        return "Cardiovascular disease is a significant risk factor associated with diabetes. Monitoring cholesterol, blood pressure, and blood sugar are critical."
    else:
        return "I am a simple rule-based clinical engine. Please ask me specifically about diabetes, HbA1c, insulin, BMI, blood pressure, or symptoms. For detailed diagnoses, you MUST consult a qualified doctor."

# -----------------------------------------------------
# MAIN APP
# -----------------------------------------------------
def main_app():
    reminder_sys = get_reminder_system()

    # ── Determine system status ────────────────────────────────────────────
    db_status    = "Online" if DB_AVAILABLE else "Offline"
    model_status = "Ready"  if get_model(list(models_dict.keys())[0]) else "Missing"
    voice_status = "Ready"  if VOICE_MODULE else "Unavailable"
    db_color     = "#10B981" if DB_AVAILABLE else "#EF4444"
    model_color  = "#10B981" if model_status == "Ready" else "#F59E0B"
    voice_color  = "#10B981" if VOICE_MODULE else "#94A3B8"

    with st.sidebar:
        # Logo + brand
        st.markdown("""
        <div style="display:flex;align-items:center;gap:12px;padding:8px 0 16px;">
            <div style="background:linear-gradient(135deg,#2563EB,#1D4ED8);width:42px;height:42px;
                        border-radius:10px;display:flex;align-items:center;justify-content:center;
                        font-size:1.3rem;">🏥</div>
            <div>
                <div style="font-weight:700;font-size:1rem;color:#1E293B;line-height:1.2;">DiabetesGuard</div>
                <div style="font-size:0.72rem;color:#64748B;font-weight:500;">PRO · v2.0</div>
            </div>
        </div>
        <div style="font-size:0.78rem;color:#64748B;padding:0 0 12px;
                    border-bottom:1px solid #E2E8F0;line-height:1.5;">
            AI-Based Diabetes Prediction &amp; Health Analytics
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='font-size:0.7rem;font-weight:700;color:#94A3B8;letter-spacing:0.1em;text-transform:uppercase;margin:16px 0 8px;'>NAVIGATION</div>", unsafe_allow_html=True)

        nav_items = [
            ("🏠", "Dashboard",       "View health metrics & history"),
            ("🩺", "Assessment",      "Run diabetes risk prediction"),
            ("💬", "AI Assistant",    "Chat with HealthGuard AI"),
            ("💊", "Medicine Cabinet", "Manage medication reminders"),
        ]
        for icon, label, desc in nav_items:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:10px;padding:10px 8px;
                        border-radius:10px;margin-bottom:4px;
                        background:rgba(37,99,235,0.04);
                        transition:background 0.2s;
                        cursor:pointer;">
                <div style="font-size:1.1rem;width:28px;text-align:center;">{icon}</div>
                <div>
                    <div style="font-weight:600;font-size:0.85rem;color:#1E293B;">{label}</div>
                    <div style="font-size:0.72rem;color:#64748B;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='font-size:0.7rem;font-weight:700;color:#94A3B8;letter-spacing:0.1em;text-transform:uppercase;margin:20px 0 8px;'>SYSTEM STATUS</div>", unsafe_allow_html=True)

        for label, color, val in [
            ("Database",  db_color,    db_status),
            ("AI Model",  model_color, model_status),
            ("Voice",     voice_color, voice_status),
        ]:
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:6px 4px;font-size:0.82rem;">
                <span style="color:#475569;font-weight:500;">{label}</span>
                <span style="display:flex;align-items:center;gap:5px;font-weight:600;color:{color};">
                    <span style="width:8px;height:8px;border-radius:50%;background:{color};
                                 display:inline-block;"></span>{val}
                </span>
            </div>
            """, unsafe_allow_html=True)

        # Footer
        st.markdown("""
        <div style="position:fixed;bottom:20px;font-size:0.72rem;color:#94A3B8;
                    line-height:1.5;">
            <div style="font-weight:600;color:#64748B;">Final Year Project</div>
            <div>AI-Based Diabetes Prediction System</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Hide Streamlit Top header ──────────────────────────────────────
    st.markdown("""
    <style>
    .stApp > header { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero Banner ────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1E3A5F 0%,#2563EB 60%,#3B82F6 100%);
                border-radius:20px;padding:32px 40px;margin-bottom:24px;
                display:flex;align-items:center;justify-content:space-between;
                box-shadow:0 8px 32px rgba(37,99,235,0.25);">
        <div>
            <div style="font-size:0.75rem;font-weight:700;letter-spacing:0.15em;
                        color:rgba(255,255,255,0.65);text-transform:uppercase;margin-bottom:8px;">
                HEALTHCARE AI PLATFORM
            </div>
            <h1 style="margin:0;font-size:2rem;font-weight:800;color:#FFFFFF;
                       line-height:1.2;letter-spacing:-0.02em;">DiabetesGuard Pro</h1>
            <p style="margin:8px 0 0;font-size:0.9rem;color:rgba(255,255,255,0.75);">
                AI-Powered Risk Assessment &amp; Health Analytics Dashboard
            </p>
        </div>
        <div style="text-align:right;">
            <div style="font-size:3.5rem;opacity:0.85;">🩺</div>
            <div style="font-size:0.72rem;color:rgba(255,255,255,0.55);margin-top:4px;">
                Final Year Project
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Model selector (used by Assessment tab) — store in session state
    if "model_choice" not in st.session_state:
        st.session_state.model_choice = list(models_dict.keys())[0]
    model_choice = st.session_state.model_choice
    selected_model = get_model(model_choice)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏠 Dashboard", "🩺 Assessment", "💬 AI Assistant", "💊 Medicine Cabinet"
    ])

    # Initialize shared prediction variables with defaults
    prob = st.session_state.dashboard_data.get('risk_score', 0.15)
    age = 35
    bmi = st.session_state.dashboard_data.get('bmi', 24.5)
    glucose = st.session_state.dashboard_data.get('glucose', 105)
    hba1c = 5.5
    no_lab_data = False

    # --- TAB 1: DASHBOARD ---
    with tab1:
        # Dashboard CSS
        st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.dashboard-wrapper { font-family: 'Inter', sans-serif; margin-bottom: 2rem; }
.dash-header-container { display: flex; align-items: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #E2E8F0; }
.dash-header-icon { background-color: #EFF6FF; color: #2563EB; padding: 10px; border-radius: 12px; margin-right: 15px; display: flex; align-items: center; justify-content: center; }
.dash-title { margin: 0; font-size: 2rem; font-weight: 700; color: #1E293B; letter-spacing: -0.025em; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem; margin-bottom: 2.5rem; }
.metric-card { background: #FFFFFF; border-radius: 16px; padding: 20px 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.05); border: 1px solid #F1F5F9; transition: all 0.2s; display: flex; flex-direction: column; justify-content: space-between; }
.metric-card:hover { transform: translateY(-4px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.08); }
.metric-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
.metric-label { font-size: 0.95rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; }
.icon-circle { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.metric-value { font-size: 2.5rem; font-weight: 700; color: #0F172A; line-height: 1.2; }
.metric-subtext { font-size: 0.85rem; color: #94A3B8; margin-top: 4px; }
.history-section { background: #FFFFFF; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #F1F5F9; margin-bottom: 2.5rem; }
.section-header { display: flex; align-items: center; margin-bottom: 1.5rem; }
.section-title { font-size: 1.25rem; font-weight: 600; color: #1E293B; margin: 0; margin-left: 12px; }
.styled-table-container { overflow-x: auto; border-radius: 12px; border: 1px solid #E2E8F0; }
.styled-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; text-align: left; }
.styled-table th { background-color: #F8FAFC; color: #475569; font-weight: 600; padding: 14px 16px; border-bottom: 1px solid #E2E8F0; text-transform: uppercase; font-size: 0.75rem; }
.styled-table td { padding: 16px; border-bottom: 1px solid #E2E8F0; color: #334155; font-weight: 500; }
.styled-table tbody tr:last-of-type td { border-bottom: none; }
.styled-table tbody tr:hover { background-color: #F8FAFC; }
.status-badge { padding: 6px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
.status-low { background-color: #D1FAE5; color: #065F46; }
.status-moderate { background-color: #FEF3C7; color: #92400E; }
.status-high { background-color: #FEE2E2; color: #991B1B; }
</style>
        """, unsafe_allow_html=True)
        
        st.markdown("""
<div class="dashboard-wrapper">
<div class="dash-header-container">
<div class="dash-header-icon">
<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
</div>
<h1 class="dash-title">Health Dashboard</h1>
</div>
        """, unsafe_allow_html=True)
        
        dd = st.session_state.dashboard_data
        
        icon_drop = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>'
        icon_scale = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>'
        icon_alert = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>'
        icon_heart = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>'
        
        metrics_html = f"""
<div class="metrics-grid">
<div class="metric-card">
<div class="metric-header">
<span class="metric-label">Blood Glucose</span>
<div class="icon-circle" style="background-color: #FEE2E2; color: #EF4444;">{icon_drop}</div>
</div>
<div>
<div class="metric-value">{dd.get('glucose', 'N/A')}</div>
<div class="metric-subtext">Current mg/dL level</div>
</div>
</div>
<div class="metric-card">
<div class="metric-header">
<span class="metric-label">BMI Index</span>
<div class="icon-circle" style="background-color: #D1FAE5; color: #10B981;">{icon_scale}</div>
</div>
<div>
<div class="metric-value">{dd.get('bmi', 'N/A')}</div>
<div class="metric-subtext">Body Mass Index</div>
</div>
</div>
<div class="metric-card">
<div class="metric-header">
<span class="metric-label">Risk Level</span>
<div class="icon-circle" style="background-color: #FEF3C7; color: #F59E0B;">{icon_alert}</div>
</div>
<div>
<div class="metric-value">{dd.get('risk_label', 'Low')}</div>
<div class="metric-subtext">Calculated ML risk</div>
</div>
</div>
<div class="metric-card">
<div class="metric-header">
<span class="metric-label">Health Score</span>
<div class="icon-circle" style="background-color: #F3E8FF; color: #8B5CF6;">{icon_heart}</div>
</div>
<div>
<div class="metric-value" style="color:#8B5CF6;">{dd.get('health_score', 85)}<span style="font-size:1.4rem; color:#94A3B8;">/100</span></div>
<div class="metric-subtext">Overall wellness</div>
</div>
</div>
</div>
"""
        st.markdown(metrics_html, unsafe_allow_html=True)
        
        sec_icon_hist = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>'
        st.markdown(f"""
<div class="history-section">
<div class="section-header">
{sec_icon_hist}
<h2 class="section-title">Recent Prediction History</h2>
</div>
        """, unsafe_allow_html=True)
        if st.session_state.prediction_history:
            hist_rows = ""
            for item in st.session_state.prediction_history[-10:]:
                rl = str(item.get('Risk Level', 'Low')).lower()
                status_class = "status-low" if "low" in rl else "status-high" if "high" in rl else "status-moderate"
                indicator = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>' if "low" in rl else '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>' if "high" in rl else '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
                hist_rows += f"""<tr>
<td>{item.get('Timestamp', 'N/A')}</td>
<td><b>{item.get('Blood Glucose', 'N/A')}</b> mg/dL</td>
<td>{item.get('BMI', 'N/A')}</td>
<td><span class="status-badge {status_class}">{indicator} {item.get('Risk Level', 'Low')}</span></td>
<td><b>{item.get('Health Score', 85)}</b></td>
</tr>"""
            table_html = f"""
<div class="styled-table-container">
<table class="styled-table">
<thead>
<tr><th>Date & Time</th><th>Blood Glucose</th><th>BMI</th><th>Risk Level</th><th>Health Score</th></tr>
</thead>
<tbody>
{hist_rows}
</tbody>
</table>
</div>
"""
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.info("📊 Run a diabetes assessment to populate your dashboard with results.")
            
        st.markdown("</div>", unsafe_allow_html=True)
        
        # ── Health Record History ──────────────────────────────────────────────
        sec_icon_db = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/></svg>'
        st.markdown(f"""
<div class="history-section">
<div class="section-header">
{sec_icon_db}
<h2 class="section-title">Health Record History</h2>
</div>
        """, unsafe_allow_html=True)
        
        if DB_AVAILABLE:
            db_records = get_health_records(limit=20)
            if db_records:
                db_rows = ""
                for r in db_records:
                    pct = round(r["risk_score"] * 100, 1)
                    res = r["prediction_result"].lower()
                    status_class = "status-low" if "low" in res else "status-high" if "high" in res else "status-moderate"
                    indicator = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>' if "low" in res else '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>' if "high" in res else '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
                    db_rows += f"""<tr>
<td style="color:#64748B;">#{r["id"]}</td>
<td>{r["timestamp"]}</td>
<td>{r["blood_glucose"]}</td>
<td>{r["bmi"]}</td>
<td><span class="status-badge {status_class}">{indicator} {pct}% Risk</span></td>
<td>{r["model_used"]}</td>
</tr>"""
                db_table = f"""
<div class="styled-table-container" style="max-height: 400px; overflow-y: auto;">
<table class="styled-table">
<thead>
<tr><th>Ref #</th><th>Date & Time</th><th>Glucose (mg/dL)</th><th>BMI</th><th>Risk Indicator</th><th>Model Engine</th></tr>
</thead>
<tbody>
{db_rows}
</tbody>
</table>
</div>
"""
                st.markdown(db_table, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("🗑️ Manage Records", expanded=False):
                    rec_ids = [r["id"] for r in db_records]
                    del_id = st.selectbox("Select Record ID to delete", rec_ids, key="del_rec_id")
                    if st.button("Delete Selected Record", type="primary", key="del_rec_btn"):
                        delete_health_record(del_id)
                        st.success(f"Record #{del_id} deleted.")
                        st.rerun()
            else:
                st.info("📋 No health records yet. Download your data automatically when you run an assessment.")
        else:
             st.warning("⚠️ Database module unavailable — history is session-only.")
             
        st.markdown("</div></div>", unsafe_allow_html=True)

    # --- TAB 2: ASSESSMENT ---
    with tab2:
        st.markdown("## 🩺 Diabetes Risk Assessment")

        # CSS for assessment tab
        st.markdown("""
        <style>
        .result-card-high { background: linear-gradient(135deg,#FEE2E2,#FECACA); border:1.5px solid #F87171; border-radius:20px; padding:28px 24px; text-align:center; }
        .result-card-low  { background: linear-gradient(135deg,#D1FAE5,#A7F3D0); border:1.5px solid #34D399; border-radius:20px; padding:28px 24px; text-align:center; }
        .result-label { font-size:1.3rem; font-weight:800; margin:8px 0; }
        .result-pct { font-size:2.8rem; font-weight:900; line-height:1; }
        .result-sub { font-size:0.85rem; color:#475569; margin-top:8px; }
        </style>
        """, unsafe_allow_html=True)

        # Model selector for prediction
        _mc1, _mc2 = st.columns([3, 1])
        with _mc2:
            mc = st.selectbox("⚙️ AI Model", list(models_dict.keys()),
                              index=list(models_dict.keys()).index(st.session_state.model_choice),
                              key="assessment_model_picker")
            if mc != st.session_state.model_choice:
                st.session_state.model_choice = mc
                st.rerun()
        model_choice = st.session_state.model_choice
        selected_model = get_model(model_choice)

        with st.form("assessment_form"):
            st.markdown("### 👤 Patient Information")
            col1, col2, col3 = st.columns(3)
            with col1:
                age = st.number_input("Age (years)", min_value=1, max_value=120, value=35, step=1)
                gender = st.selectbox("Gender", ["Male", "Female"])
            with col2:
                hypertension = st.selectbox("Hypertension", ["No", "Yes"])
                heart_disease = st.selectbox("Heart Disease", ["No", "Yes"])
            with col3:
                smoking = st.selectbox("Smoking History", ["Never", "Former", "Current"])
                bmi = st.number_input("BMI", min_value=10.0, max_value=70.0, value=24.5, step=0.1)

            st.markdown("### 🔬 Lab Results")
            no_lab_data = st.checkbox("No lab data available (use symptom-based estimate)")

            if not no_lab_data:
                col4, col5 = st.columns(2)
                with col4:
                    hba1c = st.number_input("HbA1c (%)", 3.0, 15.0, 5.5, 0.1)
                with col5:
                    glucose = st.number_input("Blood Glucose (mg/dL)", 50.0, 500.0, 105.0, 1.0)
            else:
                hba1c = 5.5
                glucose = 100.0
                st.markdown("#### Symptom Checklist")
                sym_cols = st.columns(3)
                sym1 = sym_cols[0].checkbox("Frequent urination")
                sym2 = sym_cols[0].checkbox("Excessive thirst")
                sym3 = sym_cols[1].checkbox("Blurred vision")
                sym4 = sym_cols[1].checkbox("Unexplained weight loss")
                sym5 = sym_cols[2].checkbox("Fatigue")
                sym6 = sym_cols[2].checkbox("Slow-healing wounds")

            submitted = st.form_submit_button("🔍 Analyse Risk", type="primary", use_container_width=True)

        if submitted:
            # Medico-Logic Override
            if not no_lab_data:
                if glucose >= 200 or hba1c >= 6.5:
                    prob = min(0.95, 0.7 + (glucose - 100) / 1000 + (hba1c - 5.5) / 20)
                elif glucose >= 126 or hba1c >= 5.7:
                    prob = min(0.65, 0.4 + (glucose - 100) / 800)
                else:
                    # ML model
                    gender_enc = 1 if gender == "Male" else 0
                    hyp_enc = 1 if hypertension == "Yes" else 0
                    hd_enc = 1 if heart_disease == "Yes" else 0
                    smoke_map = {"Never": 0, "Former": 1, "Current": 2}
                    features = np.array([[gender_enc, age, hyp_enc, hd_enc, smoke_map.get(smoking, 0), bmi, hba1c, glucose]])
                    try:
                        features_scaled = scaler.transform(features)
                        if selected_model:
                            prob = float(selected_model.predict_proba(features_scaled)[0][1])
                        else:
                            prob = min(0.9, (hba1c - 4) / 10 + (glucose - 70) / 500)
                    except Exception:
                        prob = min(0.9, (hba1c - 4) / 10 + (glucose - 70) / 500)
            else:
                sym_score = 0
                if sym1: sym_score += 2
                if sym2: sym_score += 2
                if sym3: sym_score += 1
                if sym4: sym_score += 2
                if sym5: sym_score += 1
                if sym6: sym_score += 2
                risk_score_val = sum([age > 45, bmi > 25, bmi > 30, hypertension == "Yes", heart_disease == "Yes"])
                prob = min(0.95, (risk_score_val + sym_score) / 12.0)

            recs = []
            if bmi > 30: recs.append("📉 Calorie Deficit: 1200–1500 kcal/day")
            elif bmi > 25: recs.append("⚖️ Portion control — use smaller plates")
            else: recs.append("✅ Maintain balanced protein & fibre intake")
            if glucose > 200 or prob > 0.6: recs.append("❗ Strict Low-GI diet recommended")
            else: recs.append("🍎 Balanced whole fruits are fine")
            if prob > 0.5:
                recs.append("🏃 Aim for 30 min moderate exercise, 5×/week")
                recs.append("🩸 Schedule HbA1c test within 1 month")
            else:
                recs.append("🚶 Maintain daily 7,000+ step goal")
                recs.append("💧 Stay well hydrated — 2–3L water/day")

            st.session_state.dashboard_data.update({
                'glucose': glucose if not no_lab_data else "N/A",
                'bmi': bmi,
                'risk_label': "High" if prob > 0.5 else "Low",
                'risk_delta': "Action Needed" if prob > 0.5 else "Stable",
                'health_score': int((1 - prob) * 100),
                'risk_score': prob,
            })

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("## 📊 Results")

            res_col, feat_col = st.columns([1.1, 1.9], gap="large")

            with res_col:
                if prob > 0.5:
                    card_cls = "result-card-high"; icon = "🔴"; label = "HIGH RISK"; label_col = "#F43F5E"
                    advice = "Please consult an endocrinologist soon."
                else:
                    card_cls = "result-card-low"; icon = "🟢"; label = "LOW RISK"; label_col = "#10B981"
                    advice = "Keep up your healthy lifestyle!"

                st.markdown(f"""
                <div class="{card_cls}">
                    <div style="font-size:2.4rem">{icon}</div>
                    <div class="result-label" style="color:{label_col}">{label}</div>
                    <div class="result-pct" style="color:{label_col}">{prob*100:.1f}%</div>
                    <div class="result-sub">{advice}</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

                b1, b2, b3 = st.columns(3)
                b1.markdown(f'<div class="stat-badge"><div class="val">{glucose:.0f}</div><div class="lbl">Glucose</div></div>', unsafe_allow_html=True)
                b2.markdown(f'<div class="stat-badge"><div class="val">{hba1c:.1f}%</div><div class="lbl">HbA1c</div></div>', unsafe_allow_html=True)
                b3.markdown(f'<div class="stat-badge"><div class="val">{bmi:.1f}</div><div class="lbl">BMI</div></div>', unsafe_allow_html=True)

                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number", value=prob * 100,
                    number={"suffix": "%", "font": {"size": 28}},
                    title={"text": "Risk Score", "font": {"size": 14}},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": label_col, "thickness": 0.3},
                        "bgcolor": "white", "borderwidth": 0,
                        "steps": [
                            {"range": [0, 40], "color": "#D1FAE5"},
                            {"range": [40, 65], "color": "#FEF3C7"},
                            {"range": [65, 100], "color": "#FEE2E2"},
                        ],
                    }
                ))
                fig_gauge.update_layout(height=220, margin=dict(l=10, r=10, t=30, b=10),
                                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_gauge, use_container_width=True, key="gauge_chart")

            with feat_col:
                feat_names = ["Gender", "Age", "Hypertension", "Heart Disease", "Smoking", "BMI", "HbA1c", "Blood Glucose"]
                feat_values = [0.02, 0.08, 0.06, 0.05, 0.04, 0.14, 0.29, 0.32]
                total = sum(feat_values) or 1
                feat_pct = [v / total * 100 for v in feat_values]
                sorted_pairs = sorted(zip(feat_names, feat_pct), key=lambda x: x[1])
                s_names = [p[0] for p in sorted_pairs]
                s_vals = [p[1] for p in sorted_pairs]
                bar_colors = ["#F87171" if v >= 15 else "#FBBF24" if v >= 8 else "#34D399" for v in s_vals]
                fig_feat = go.Figure(go.Bar(
                    x=s_vals, y=s_names, orientation="h",
                    marker={"color": bar_colors, "line": {"width": 0}},
                    text=[f"{v:.1f}%" for v in s_vals], textposition="outside",
                ))
                fig_feat.update_layout(
                    title={"text": "🔬 Feature Importance", "font": {"size": 15}},
                    xaxis={"title": "Contribution (%)", "showgrid": True, "gridcolor": "#F1F5F9"},
                    yaxis={"showgrid": False},
                    height=320, margin=dict(l=10, r=60, t=40, b=30),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_feat, use_container_width=True, key="feat_chart")

                st.markdown("#### 📋 Clinical Recommendations")
                chips_html = "".join([f'<span class="rec-chip">{r}</span>' for r in recs])
                st.markdown(f'<div style="line-height:2.2">{chips_html}</div>', unsafe_allow_html=True)
                st.caption("⚕️ *This is not a medical diagnosis. Always consult a qualified healthcare provider.*")

            # PDF Download
            st.markdown("---")
            pdf_details = {
                "Patient Age": age, "Gender": gender, "BMI": f"{bmi:.1f}",
                "Blood Glucose": f"{glucose:.0f} mg/dL", "HbA1c": f"{hba1c:.1f}%",
                "Risk Score": f"{prob*100:.1f}%",
                "Classification": "High Risk" if prob > 0.5 else "Low Risk",
            }
            pdf_bytes = generate_pdf(pdf_details, prob, recs)
            dl_link = create_download_link(pdf_bytes, f"HealthAI_Report_{int(time.time())}.pdf")
            st.markdown(f'<div style="text-align:center;margin:12px 0;">{dl_link}</div>', unsafe_allow_html=True)

            # ═══════════════════════════════════════════════════════
            # PERSONALISED DIETARY RECOMMENDATIONS SECTION
            # ═══════════════════════════════════════════════════════
            diet = get_diet_recommendations(prob, age, bmi, gender)
            st.markdown("---")

            # ── Section Header & Risk Badge ─────────────────────────
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,{diet['tier_bg']},{diet['tier_border']});
                        border:2px solid {diet['tier_border']};border-radius:20px;
                        padding:22px 28px;margin-bottom:20px;">
                <div style="display:flex;align-items:flex-start;gap:16px;">
                    <div style="font-size:3rem;line-height:1;">{diet['tier_icon']}</div>
                    <div style="flex:1;">
                        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                            <span style="background:{diet['tier_color']};color:#fff;font-size:0.8rem;
                                         font-weight:800;padding:4px 16px;border-radius:30px;
                                         letter-spacing:0.05em;">
                                {diet['tier']} RISK
                            </span>
                            <span style="background:white;color:{diet['tier_color']};font-size:0.75rem;
                                         font-weight:700;padding:4px 14px;border-radius:30px;
                                         border:1.5px solid {diet['tier_border']};">
                                {prob*100:.0f}% Risk Score
                            </span>
                        </div>
                        <div style="font-size:1.15rem;font-weight:700;color:#1E293B;margin-bottom:6px;">
                            {diet['headline']}
                        </div>
                        <p style="font-size:0.87rem;color:#475569;margin:0;line-height:1.6;">
                            {diet['intro']}
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Column Layout: Foods + Hydration ───────────────────
            inc_col, av_col, hyd_col = st.columns([1.15, 1.05, 0.9], gap="medium")

            def diet_card_item(text, bg, border):
                return f'<div style="padding:9px 13px;margin:5px 0;border-radius:11px;background:{bg};border:1px solid {border};font-size:0.86rem;line-height:1.4;">{text}</div>'

            with inc_col:
                st.markdown(f'<div style="font-weight:700;font-size:0.92rem;color:{diet["tier_color"]};margin-bottom:6px;">✅ Foods to Include</div>', unsafe_allow_html=True)
                for f in diet['foods_include']:
                    st.markdown(diet_card_item(f, "rgba(255,255,255,0.85)", "rgba(0,0,0,0.07)"), unsafe_allow_html=True)

            with av_col:
                st.markdown('<div style="font-weight:700;font-size:0.92rem;color:#DC2626;margin-bottom:6px;">❌ Foods to Avoid</div>', unsafe_allow_html=True)
                for f in diet['foods_avoid']:
                    st.markdown(diet_card_item(f, "#FFF1F2", "#FECDD3"), unsafe_allow_html=True)

            with hyd_col:
                st.markdown('<div style="font-weight:700;font-size:0.92rem;color:#0284C7;margin-bottom:6px;">💧 Hydration Tips</div>', unsafe_allow_html=True)
                for h in diet['hydration']:
                    st.markdown(diet_card_item(h, "#F0F9FF", "#BAE6FD"), unsafe_allow_html=True)

            # ── Lifestyle + Portion Control ─────────────────────────
            life_col, plate_col = st.columns([1.6, 1.0], gap="medium")
            with life_col:
                st.markdown('<div style="font-weight:700;font-size:0.92rem;color:#059669;margin:14px 0 6px;">🏃 Lifestyle Recommendations</div>', unsafe_allow_html=True)
                for lt in diet['lifestyle']:
                    st.markdown(diet_card_item(lt, "#F0FDF4", "#BBF7D0"), unsafe_allow_html=True)

            with plate_col:
                st.markdown('<div style="font-weight:700;font-size:0.92rem;color:#7C3AED;margin:14px 0 6px;">📏 Portion Control Plate</div>', unsafe_allow_html=True)
                st.markdown(f"""
                <div style="background:white;border:1.5px dashed #A78BFA;border-radius:14px;
                            padding:16px;font-size:0.84rem;color:#374151;line-height:1.7;">
                    🍽️ <b>The Diabetic Plate Rule</b><br>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;margin:10px 0;">
                        <span style="background:#BBF7D0;padding:4px 10px;border-radius:20px;font-size:0.78rem;font-weight:600;">🥦 50% Vegetables</span>
                        <span style="background:#BAE6FD;padding:4px 10px;border-radius:20px;font-size:0.78rem;font-weight:600;">🍗 25% Protein</span>
                        <span style="background:#FEF3C7;padding:4px 10px;border-radius:20px;font-size:0.78rem;font-weight:600;">🌾 25% Grains</span>
                    </div>
                    <em style="color:#6B7280;font-size:0.82rem;">{diet['portion_tip']}</em>
                </div>
                """, unsafe_allow_html=True)

            # ── Sample Daily Meal Plan ──────────────────────────────
            st.markdown('<div style="font-weight:700;font-size:0.92rem;color:#1E293B;margin:18px 0 10px;">🍱 Sample Daily Meal Plan (Indian)</div>', unsafe_allow_html=True)
            import typing
            mp = typing.cast(dict, diet['meal_plan'])
            meal_cols = st.columns(5)
            meal_items = [
                (meal_cols[0], "🌅", "Breakfast",      mp["Breakfast"],      "#EFF6FF", "#BFDBFE"),  # type: ignore
                (meal_cols[1], "🍏", "Mid-Morning",    mp["Mid-Morning"],    "#F0FDF4", "#BBF7D0"),  # type: ignore
                (meal_cols[2], "☀️",  "Lunch",          mp["Lunch"],          "#FFFBEB", "#FDE68A"),  # type: ignore
                (meal_cols[3], "🌙", "Eve Snack",      mp["Evening Snack"],  "#FFF1F2", "#FECDD3"),  # type: ignore
                (meal_cols[4], "🌃", "Dinner",         mp["Dinner"],         "#FAF5FF", "#E9D5FF"),  # type: ignore
            ]
            for col, icon, label, text, bg, border in meal_items:
                with col:
                    st.markdown(f"""
                    <div style="background:{bg};border:1.5px solid {border};border-radius:14px;
                                padding:14px 12px;height:100%;min-height:140px;">
                        <div style="font-size:1.4rem;margin-bottom:4px;">{icon}</div>
                        <div style="font-size:0.73rem;font-weight:700;text-transform:uppercase;
                                    letter-spacing:0.06em;color:#64748B;margin-bottom:6px;">{label}</div>
                        <div style="font-size:0.82rem;color:#1E293B;line-height:1.5;">{text}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown(f'<div style="font-size:0.8rem;color:#64748B;text-align:center;margin-top:8px;">⚡ Estimated Daily Intake: <b>{mp["Calories"]}</b></div>', unsafe_allow_html=True) # type: ignore

            # ── Diet Plan PDF Download ──────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            diet_pdf_bytes = generate_diet_pdf(diet, prob, age, bmi, gender)
            diet_dl = create_download_link(diet_pdf_bytes, f"HealthAI_DietPlan_{diet['tier']}_Risk_{int(time.time())}.pdf")
            st.markdown(f'<div style="text-align:center;margin:4px 0 8px;">{diet_dl}</div>', unsafe_allow_html=True)

            # ── Disclaimer ──────────────────────────────────────────
            st.markdown("""
            <div style="text-align:center;font-size:0.78rem;color:#94A3B8;margin-top:10px;
                        padding:12px 16px;border-top:1px solid #E2E8F0;border-radius:0 0 12px 12px;
                        background:#F8FAFC;">
                ⚕️ <em>This is not a medical diagnosis. These dietary suggestions are for general educational
                purposes only. Please consult a qualified healthcare professional or registered dietitian
                before making any significant dietary changes.</em>
            </div>
            """, unsafe_allow_html=True)

            st.session_state.prediction_history.append({
                "date": datetime.now().strftime("%b %d, %Y"),
                "age": age, "risk_pct": float(f"{prob * 100:.1f}"),
                "result": "High Risk" if prob > 0.5 else "Low Risk",
                "model": model_choice,
            })

            # ── Save to SQLite ──────────────────────────────────────────────────
            if DB_AVAILABLE:
                try:
                    smoking_label = {0: "Never", 1: "Former", 2: "Current", 3: "No Info"}.get(
                        int(smoking if 'smoking' in locals() else 0), "Never"
                    )
                    save_health_record({
                        "age": age,
                        "gender": gender,
                        "bmi": float(f"{bmi:.2f}"),
                        "blood_glucose": float(f"{glucose:.1f}"),
                        "hba1c": float(f"{hba1c:.2f}"),
                        "hypertension": int(hypertension) if 'hypertension' in locals() else 0,
                        "heart_disease": int(heart_disease) if 'heart_disease' in locals() else 0,
                        "smoking": smoking_label,
                        "prediction_result": "High Risk" if prob > 0.5 else "Low Risk",
                        "risk_score": float(f"{prob:.4f}"),
                        "model_used": model_choice,
                    })
                    st.toast("✅ Record saved to health history", icon="💾")
                except Exception as _db_save_err:
                    logger.warning("Could not save record: %s", _db_save_err)

    # --- TAB 3: RULE-BASED DIAGNOSTIC ASSISTANT ---
    with tab3:
        chat_head_col1, chat_head_col2 = st.columns([5, 1])
        with chat_head_col1:
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 12px; padding-bottom: 6px;">
                <div style="background-color: #10B981; width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: white;">🩺</div>
                <div>
                    <h3 style="margin: 0; padding: 0; color: #1E293B; font-weight: 700; font-size: 1.4rem;">HealthGuard AI Assistant</h3>
                    <div style="font-size: 0.85rem; color: #64748B; margin-top: 4px;">Powered by Zephyr-7B - Ask anything health-related</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with chat_head_col2:
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            if st.button("🗑️ New Chat", use_container_width=True):
                for chat in st.session_state.chat_sessions:
                    if chat['id'] == st.session_state.active_chat_id:
                        # Resetting to default message
                        chat['messages'] = [{"role": "assistant", "content": "Hello! I am your rule-based clinical assistant. I can define medical terms, explain diabetes types, HbA1c, insulin, and basic symptoms."}]
                st.rerun()

        st.markdown("---")

        active_chat = None
        for chat in st.session_state.chat_sessions:
            if chat['id'] == st.session_state.active_chat_id:
                active_chat = chat
                break

        if active_chat:
            chat_container = st.container(height=550)
            
            with chat_container:
                for msg in active_chat['messages']: # type: ignore
                    if msg["role"] == "user":
                        st.markdown(f"""
<div style="display: flex; flex-direction: column; align-items: flex-end; margin-bottom: 20px;">
    <div style="font-size: 0.75rem; color: #64748B; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; font-weight: 600;">👤 You</div>
    <div style="background-color: #3B82F6; color: white; padding: 14px 20px; border-radius: 12px; max-width: 80%; font-size: 14px; font-family: 'Inter', sans-serif;">
        {msg["content"]}
    </div>
</div>
""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
<div style="display: flex; flex-direction: column; align-items: flex-start; margin-bottom: 20px;">
    <div style="font-size: 0.75rem; color: #6366F1; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; font-weight: 600;">🩺 HealthGuard AI</div>
    <div style="background-color: #F8FAFC; color: #334155; padding: 14px 20px; border-radius: 12px; max-width: 80%; font-size: 14px; font-family: 'Inter', sans-serif; border: 1px solid #E2E8F0;">
        {msg["content"]}
    </div>
</div>
""", unsafe_allow_html=True)
            
            if prompt := st.chat_input("Ask me anything about your health or otherwise..."):
                active_chat['messages'].append({"role": "user", "content": prompt}) # type: ignore
                
                with chat_container:
                    # Immediately show user input
                    st.markdown(f"""
<div style="display: flex; flex-direction: column; align-items: flex-end; margin-bottom: 20px;">
    <div style="font-size: 0.75rem; color: #64748B; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; font-weight: 600;">👤 You</div>
    <div style="background-color: #3B82F6; color: white; padding: 14px 20px; border-radius: 12px; max-width: 80%; font-size: 14px; font-family: 'Inter', sans-serif;">
        {prompt}
    </div>
</div>
""", unsafe_allow_html=True)
                    
                    with st.spinner("Thinking..."):
                        try:
                            response_text = get_ai_response(prompt)
                        except Exception as e:
                            response_text = "Server busy. Please try again later."
                            
                        active_chat['messages'].append({"role": "assistant", "content": response_text}) # type: ignore
                        st.rerun()

    # --- TAB 4: MEDICINE CABINET (Smart Reminder Engine) ---
    with tab4:
        st.markdown("## 💊 Smart Medicine Reminder")
        st.markdown(f"⏱️ **Current System Time:** `{datetime.now().strftime('%I:%M %p')}`")
        st.caption("Schedule medications, receive email & SMS alerts, track adherence.")

        # ── Credentials / Test Panel ─────────────────────────────────────────
        with st.expander("⚙️ Configure & Test Email / SMS Notifications", expanded=False):
            st.markdown("""
            **Gmail is already configured** from your `.env` file.
            Use the buttons below to send a test notification.
            """)
            cred1, cred2 = st.columns(2)
            with cred1:
                st.markdown("**📧 Email Test**")
                test_email_addr = st.text_input(
                    "Recipient email", value=os.getenv("GMAIL_ADDRESS", ""),
                    key="test_email_addr", label_visibility="collapsed",
                    placeholder="recipient@gmail.com"
                )
                if st.button("📧 Send Test Email", key="send_test_email", use_container_width=True):
                    if RE_AVAILABLE and test_email_addr:
                        ok, msg = re_eng.send_test_email(test_email_addr)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("Enter an email address.")
            with cred2:
                st.markdown("**📲 SMS Test (Twilio)**")
                test_phone = st.text_input(
                    "Phone number", key="test_phone_inp", label_visibility="collapsed",
                    placeholder="+91XXXXXXXXXX"
                )
                if st.button("📲 Send Test SMS", key="send_test_sms", use_container_width=True):
                    if RE_AVAILABLE and test_phone:
                        ok, msg = re_eng.send_test_sms(test_phone)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("Enter a phone number.")
            st.caption("Gmail: `tanujabhaskaran@gmail.com` · App Password already set ✅")

        st.markdown("---")

        # ── Add New Reminder ─────────────────────────────────────────────────
        with st.expander("➕ Add New Medication Reminder", expanded=False):
            with st.form("add_med_form_v2"):
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    new_med_name = st.text_input("Medicine Name *", placeholder="e.g. Metformin 500mg")
                    new_dosage   = st.text_input("Dosage", placeholder="e.g. 500mg")
                with fc2:
                    new_time     = st.time_input("Reminder Time *", value=datetime.now())
                    new_food_ins = st.selectbox("Food Instruction", ["After Food", "Before Food", "With Food", "Any Time"])
                with fc3:
                    new_freq     = st.selectbox("Frequency", ["Daily", "Twice Daily", "Weekly", "As Needed"])
                    new_days     = st.multiselect(
                        "Repeat on Days",
                        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                        default=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    )

                notif1, notif2 = st.columns(2)
                with notif1:
                    new_email_addr = st.text_input(
                        "📧 Email for alerts",
                        value=os.getenv("GMAIL_ADDRESS", ""),
                        placeholder="yourname@gmail.com"
                    )
                with notif2:
                    new_phone = st.text_input("📲 Phone for SMS (optional)", placeholder="+91XXXXXXXXXX")

                if st.form_submit_button("💾 Save Reminder", type="primary", use_container_width=True):
                    if new_med_name.strip():
                        if RE_AVAILABLE:
                            days_val = "Everyday" if len(new_days) == 7 else new_days
                            re_eng.add_reminder({
                                "medicine_name":   new_med_name.strip(),
                                "dosage":          new_dosage.strip(),
                                "time":            new_time.strftime("%H:%M"),
                                "frequency":       new_freq,
                                "food_instruction": new_food_ins,
                                "phone":           new_phone.strip(),
                                "email":           new_email_addr.strip(),
                                "days":            days_val,
                            })
                            st.success(f"✅ Reminder saved for {new_med_name} at {new_time.strftime('%I:%M %p')}")
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            st.error("Reminder engine not available.")
                    else:
                        st.error("Please enter a medicine name.")

        # ── Stats Row ────────────────────────────────────────────────────────
        if RE_AVAILABLE:
            stats = re_eng.get_adherence_stats()
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("💊 Total Reminders", stats["total_reminders"])
            s2.metric("✅ Taken Today",     stats["taken_today"])
            s3.metric("⚠️ Missed Today",   stats["missed_today"])
            s4.metric("📊 Adherence",      f"{stats['adherence_pct']}%")
            st.markdown("---")

        # ── Active Schedule ──────────────────────────────────────────────────
        if RE_AVAILABLE:
            reminders = re_eng.get_all_reminders()
        else:
            reminders = reminder_sys.load_reminders()

        if not reminders:
            st.info("📋 No reminders set. Add one above!")
        else:
            reminders_sorted = sorted(reminders, key=lambda x: x.get("time", ""))
            st.subheader(f"📅 Active Schedule ({len(reminders_sorted)} medications)")

            for rem in reminders_sorted:
                rem_id = rem.get("id") or rem.get("id", 0)

                # ── Edit mode ────────────────────────────────────────────────
                if 'edit_rem_id' in st.session_state and st.session_state.edit_rem_id == rem_id:
                    st.markdown(f"#### ✏️ Editing: {rem.get('medicine_name', rem.get('name', ''))}")
                    with st.form(f"edit_form_{rem_id}"):
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1:
                            e_name   = st.text_input("Medicine", value=rem.get("medicine_name", rem.get("name", "")))
                            e_dosage = st.text_input("Dosage",   value=rem.get("dosage", ""))
                        with ec2:
                            try:
                                t_obj = datetime.strptime(rem.get("time", "08:00"), "%H:%M").time()
                            except Exception:
                                t_obj = datetime.now().time()
                            e_time = st.time_input("Time", value=t_obj)
                            e_food = st.selectbox("Food Instruction",
                                                  ["After Food", "Before Food", "With Food", "Any Time"],
                                                  index=["After Food", "Before Food", "With Food", "Any Time"].index(
                                                      rem.get("food_instruction", "After Food")
                                                  ) if rem.get("food_instruction") in ["After Food", "Before Food", "With Food", "Any Time"] else 0)
                        with ec3:
                            d_list    = rem.get("days", "Everyday")
                            d_default = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] if d_list in ("Everyday", ["Everyday"]) else (d_list if isinstance(d_list, list) else [d_list])
                            e_days    = st.multiselect("Days", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], default=d_default)
                            e_email   = st.text_input("Email",  value=rem.get("email", ""))
                            e_phone   = st.text_input("Phone",  value=rem.get("phone", ""))

                        btn1, btn2 = st.columns(2)
                        if btn1.form_submit_button("✅ Update", type="primary"):
                            if RE_AVAILABLE:
                                re_eng.update_reminder(rem_id, {
                                    "medicine_name":    e_name,
                                    "dosage":           e_dosage,
                                    "time":             e_time.strftime("%H:%M"),
                                    "food_instruction": e_food,
                                    "days":             "Everyday" if len(e_days) == 7 else e_days,
                                    "email":            e_email,
                                    "phone":            e_phone,
                                })
                            del st.session_state.edit_rem_id
                            st.rerun()
                        if btn2.form_submit_button("❌ Cancel"):
                            del st.session_state.edit_rem_id
                            st.rerun()

                else:
                    # ── Display card ─────────────────────────────────────────
                    now = datetime.now()
                    time_str = rem.get("time", "")
                    try:
                        rem_dt   = datetime.strptime(time_str, "%H:%M").replace(
                                       year=now.year, month=now.month, day=now.day)
                        diff_min = (now - rem_dt).total_seconds() / 60
                        if diff_min < 0:
                            abs_diff = abs(diff_min)
                            time_left = f"In {int(abs_diff//60)}h {int(abs_diff%60)}m"
                        elif diff_min < 5:
                            time_left = "🔴 DUE NOW"
                        else:
                            time_left = f"⏰ {int(diff_min//60)}h {int(diff_min%60)}m ago"
                    except Exception:
                        time_left = time_str

                    status  = rem.get("status", "Pending")
                    badge_map = {
                        "Taken":   ("#D1FAE5", "#065F46", "✅ TAKEN"),
                        "Missed":  ("#FEE2E2", "#991B1B", "⚠️ MISSED"),
                        "Due Now": ("#FEF3C7", "#92400E", "🔔 DUE NOW"),
                        "Pending": ("#EFF6FF", "#1D4ED8", "🕐 SCHEDULED"),
                    }
                    bg, fg, badge_txt = badge_map.get(status, ("#EFF6FF", "#1D4ED8", "🕐 SCHEDULED"))

                    days_val = rem.get("days", "Everyday")
                    if isinstance(days_val, list):
                        days_val = ", ".join(days_val)

                    med_name = rem.get("medicine_name", rem.get("name", "—"))
                    dosage   = rem.get("dosage", "")
                    food_ins = rem.get("food_instruction", "")
                    has_email = bool(rem.get("email", "").strip())
                    has_phone = bool(rem.get("phone", "").strip())

                    email_bg = f'&nbsp;·&nbsp; 📧' if has_email else ''
                    phone_bg = f'&nbsp;·&nbsp; 📲' if has_phone else ''
                    with st.container():
                        html_content = f"""<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:5px solid {fg}; border-radius:14px;padding:16px 20px;margin-bottom:12px; box-shadow:0 2px 8px rgba(0,0,0,0.04);"><div style="display:flex;align-items:center;justify-content:space-between;"><div><span style="font-size:1.05rem;font-weight:700;color:#1E293B;">💊 {med_name}</span>{f'<span style="font-size:0.85rem;color:#64748B;margin-left:10px;">{dosage}</span>' if dosage else ''}</div><span style="background:{bg};color:{fg};font-size:0.75rem;font-weight:700; padding:4px 12px;border-radius:20px;">{badge_txt}</span></div><div style="margin-top:8px;font-size:0.84rem;color:#64748B;">⏰ <b>{datetime.strptime(time_str, '%H:%M').strftime('%I:%M %p') if time_str else '—'}</b>&nbsp;·&nbsp; 📅 {days_val}&nbsp;·&nbsp; 🍽️ {food_ins}&nbsp;·&nbsp; ⏳ {time_left}{email_bg}{phone_bg}</div></div>"""
                        st.markdown(html_content, unsafe_allow_html=True)

                        act1, act2, act3, act4, act5 = st.columns([2, 2, 2, 1, 1])
                        with act1:
                            if st.button("✅ Mark Taken", key=f"taken_{rem_id}", use_container_width=True):
                                if RE_AVAILABLE:
                                    re_eng.mark_taken(rem_id)
                                st.rerun()
                        with act2:
                            if st.button("💤 Snooze 5m", key=f"snooze_{rem_id}", use_container_width=True):
                                if RE_AVAILABLE:
                                    re_eng.snooze_reminder(rem_id, 5)
                                st.rerun()
                        with act3:
                            if st.button("🔔 Notify Now", key=f"notify_{rem_id}", use_container_width=True):
                                if RE_AVAILABLE:
                                    results = re_eng.notify_now(rem_id)
                                    for r in results:
                                        if r.startswith("✅"):
                                            st.success(r)
                                        elif "No " in r or "not" in r.lower():
                                            st.info(r)
                                        else:
                                            st.error(r)
                        with act4:
                            if st.button("✏️", key=f"edit_{rem_id}", help="Edit"):
                                st.session_state.edit_rem_id = rem_id
                                st.rerun()
                        with act5:
                            if st.button("🗑️", key=f"del_{rem_id}", help="Delete"):
                                if RE_AVAILABLE:
                                    re_eng.delete_reminder(rem_id)
                                st.rerun()

# -----------------------------------------------------
# EXECUTION
# -----------------------------------------------------
main_app()
