
# Aegis AI Healthcare Dashboard

This is a professional AI-powered healthcare risk prediction system. It uses medical-grade machine learning models to analyze patient vitals and predict disease risks.

## Features
- **Modern Landing Page**: High-end healthcare UI with disease selection.
- **Precision Diagnostics**: Numeric input forms for clinical accuracy (no sliders).
- **Advanced Visualizations**:
  - **Risk Gauge**: Real-time risk scoring.
  - **Biomarker Radar**: Visual map of patient health across multiple vitals.
  - **Feature contribution**: Understand which factors drive the risk.
  - **Scenario Analysis**: Line chart showing variance in risk.
- **Clinical Recommendations**: AI-generated health advice based on results.

## Requirements
- Python 3.8+
- FastAPI
- Dash
- Dash Bootstrap Components
- Scikit-Learn
- Uvicorn

## How to Run

### 1. Start the FastAPI Backend
Open a terminal and run:
```bash
python api/main.py
```
The API will be available at `http://127.0.0.1:8000`.

### 2. Start the Dash Dashboard
Open a new terminal and run:
```bash
python dashboard/app.py
```
Navigate to `http://127.0.0.1:8050` in your browser.

## Tech Stack
- **Backend**: FastAPI
- **Frontend**: Dash / Dash Bootstrap
- **Charts**: Plotly
- **ML**: Scikit-Learn (Logistic Regression & Random Forest)
- **Styling**: Premium Custom CSS (Glassmorphism + Dark Mode)
