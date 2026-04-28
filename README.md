# Aegis AI Healthcare Dashboard

Advanced Multi-Disease Diagnostic Platform using Deep Neural Ensembles.

## 🚀 Google OAuth Configuration

To enable the "Continue with Google" login feature, you must configure your Google Cloud Credentials.

### 1. Create Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Navigate to **APIs & Services > Credentials**.
4. Click **Create Credentials > OAuth client ID**.
5. Configure the Consent Screen (Internal or External).
6. Select **Web Application**.
7. Add **Authorized redirect URIs**:
   - Local: `http://127.0.0.1:8050/login/google/callback`
   - Production: `https://your-dashboard-url.onrender.com/login/google/callback`

### 2. Configure Environment Variables
Create a file named `.env` in the root directory and add your keys:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-secret-key

# Flask Security
FLASK_SECRET_KEY=any-random-long-string

# API URL (Optional, defaults to localhost)
API_BASE_URL=https://your-api-url.onrender.com
```

### 3. Run the Application Locally
1. Install dependencies: `pip install -r requirements.txt`
2. Start the FastAPI backend: `python api/main.py`
3. Start the Dash dashboard: `python dashboard/app.py`
4. Open `http://127.0.0.1:8050` in your browser.

## 🌐 Deployment to Render

This project is structured to be deployed as two separate Web Services on Render.

### Service 1: ML Backend (FastAPI)
- **Environment**: Python
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Add Environment Variables**:
  - `GMAIL_USER`: Your Gmail address
  - `GMAIL_APP_PASSWORD`: Your Gmail App Password (for contact form)

### Service 2: Frontend Dashboard (Dash)
- **Environment**: Python
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn dashboard.app:server --bind 0.0.0.0:$PORT`
- **Add Environment Variables**:
  - `API_BASE_URL`: The URL of your deployed ML Backend Service 1.
  - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FLASK_SECRET_KEY`
  - `REDIRECT_URI`: `https://your-dashboard-url.onrender.com/login/google/callback`

## 🛠 Features
- **Multi-Disease Analysis**: Diabetes, Heart, Stroke, Kidney, Liver, and more.
- **Neural Pulse Engine**: Real-time AI inference powered by specialized ML models.
- **Clinical Reports**: Automated report synthesis.
- **Aegis AI Assistant**: Natural language medical guidance.
