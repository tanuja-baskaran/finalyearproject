# DiabetesGuard Pro 🩺

DiabetesGuard Pro is a comprehensive, AI-powered web application designed to help users manage and predict diabetes. Built with a modern **Streamlit** interface, this platform integrates machine learning predictions with an intelligent medicine reminder system.

## 🚀 Features

- **Secure User Authentication**: A robust login and role-based access system to keep user health data secure.
- **AI Diabetes Prediction**: Uses advanced Machine Learning models (Random Forest, XGBoost) to assess diabetes risk based on user-provided health metrics (Age, Glucose Level, BMI, Blood Pressure, and HbA1c).
- **Smart Medicine Reminders**: A background reminder engine backed by SQLite that allows users to schedule, manage, and receive timely alerts for their medications.
- **Health Records Management**: Safely stores patient history and prediction results in a local database for future reference.
- **Modern User Interface**: A clean, responsive, and aesthetically pleasing UI designed for an optimal user experience.

## 🛠️ Technology Stack

- **Frontend / UI**: [Streamlit](https://streamlit.io/)
- **Backend Language**: Python 3
- **Machine Learning**: Scikit-Learn, XGBoost, Pandas, NumPy
- **Database**: SQLite
- **Environment Management**: `python-dotenv`

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tanuja-baskaran/finalyearproject.git
   cd finalyearproject
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   streamlit run app.py
   ```

## 📂 Project Structure

- `app.py`: The main entry point of the Streamlit application.
- `database.py`: Handles all SQLite database interactions and schema management.
- `reminder_engine.py`: The backend engine responsible for processing and triggering medicine reminders.
- `models/`: Contains the pre-trained machine learning models (`.pkl` files) used for diabetes prediction.
- `requirements.txt`: Lists all Python dependencies required to run the project.

## 🤝 Contributing

Feel free to fork this project, submit pull requests, or open an issue if you find any bugs or have suggestions for new features!

---
*Built as a Final Year Project by Tanuja Baskaran.*
