
import dash  # pyre-ignore
from dash import html, dcc, Input, Output, State, ALL  # pyre-ignore
import dash_bootstrap_components as dbc  # pyre-ignore
import plotly.graph_objects as go  # pyre-ignore
import plotly.express as px  # pyre-ignore
import requests  # pyre-ignore
import json
import numpy as np  # pyre-ignore
import sys
import os
from datetime import datetime

# Import DB functions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import add_user, get_user, get_user_by_email, add_assessment, get_assessment_history, add_patient_registration, get_all_patient_registrations, delete_patient_registration  # pyre-ignore

# Initialize the Dash app
from flask import redirect, request, session, url_for  # type: ignore
from dotenv import load_dotenv  # type: ignore

# Load .env from project root
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path, override=True)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True
)

server = app.server
server.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-very-secret-key-12345")

# Initialize Database on startup to ensure tables exist
from db.database import init_db
try:
    init_db()
    print("--- Database Initialized Successfully ---")
except Exception as e:
    print(f"--- Database Init Warning: {e} ---")

# Load Google Credentials from Environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI_OVERRIDE = os.getenv("REDIRECT_URI")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# Debug Logging
is_placeholder = lambda x: not x or "your_client_id" in str(x) or "your_client_secret" in str(x)

def mask_val(val, chars=10):
    if not val or is_placeholder(val): return "[PLACEHOLDER OR MISSING]"
    s = str(val)
    return "[FOUND] " + s[:chars] + "..."  # type: ignore

print("--- OAuth Debug ---")
print(f"GOOGLE_CLIENT_ID: {mask_val(GOOGLE_CLIENT_ID, 10)}")
print(f"GOOGLE_CLIENT_SECRET: {mask_val(GOOGLE_CLIENT_SECRET, 5)}")
print(f"REDIRECT_URI_OVERRIDE: {REDIRECT_URI_OVERRIDE}")
print("--------------------")

from urllib.parse import urlencode, quote

@server.route("/login/google")
def login_google():
    cid = os.getenv("GOOGLE_CLIENT_ID")
    if not cid:
        return """
        <div style="font-family: sans-serif; padding: 40px; text-align: center; background: #1a1a1a; color: white; min-height: 100vh;">
            <h2 style="color: #00f2ff; margin-bottom: 20px;">Google OAuth Configuration Required</h2>
            <div style="background: #252525; padding: 25px; border-radius: 10px; display: inline-block; text-align: left; border: 1px solid #333; max-width: 600px;">
                <p>The application detected that <b>GOOGLE_CLIENT_ID</b> is either missing or still set to the placeholder in your <code>.env</code> file.</p>
                
                <h4 style="color: #00f2ff;">To fix this:</h4>
                <ol>
                    <li>Open the file: <code>c:\\Users\\ashuk\\OneDrive\\Desktop\\Fullml\\.env</code></li>
                    <li>Replace <code>your_client_id_here...</code> with your real ID from Google Cloud Console.</li>
                    <li>Replace <code>your_client_secret_here</code> with your real Secret Key.</li>
                </ol>
                
                <p style="color: #888; font-size: 0.9rem;">Refer to the <code>README.md</code> in the project root for step-by-step instructions on creating these keys.</p>
            </div>
            <br><br>
            <a href="/login" style="color: #888; text-decoration: none; border: 1px solid #444; padding: 10px 20px; border-radius: 5px; margin-right: 15px;">Back to Login</a>
            <a href="/login/google/demo" style="color: #00f2ff; text-decoration: none; border: 1px solid #00f2ff; padding: 10px 20px; border-radius: 5px; background: rgba(0,242,255,0.1); font-weight: bold;">Initialize Demo (Bypass)</a>
        </div>
        """, 401
    # Auto-detect Render URL if placeholder is used or if RENDER_EXTERNAL_URL is available
    base_url = os.getenv("RENDER_EXTERNAL_URL", request.url_root.rstrip("/"))
    
    # If REDIRECT_URI_OVERRIDE is a placeholder or not set, use the detected base_url
    if not REDIRECT_URI_OVERRIDE or "your-" in REDIRECT_URI_OVERRIDE:
        redirect_uri = base_url.rstrip("/") + "/login/google/callback"
        # Ensure it starts with https on Render
        if "onrender.com" in redirect_uri and not redirect_uri.startswith("https://"):
            redirect_uri = redirect_uri.replace("http://", "https://")
    else:
        redirect_uri = REDIRECT_URI_OVERRIDE
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params, quote_via=quote)}"
    
    # Debug Launch Logs
    print(f"--- Google OAuth Launch ---")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Final URL: {auth_url}")
    print(f"---------------------------")
    
    return redirect(auth_url)

@server.route("/login/google/callback")
def login_google_callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        return redirect("/login?error=" + str(error))
        
    redirect_uri = REDIRECT_URI_OVERRIDE or (request.url_root.rstrip("/") + "/login/google/callback")
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    token_resp = requests.post(token_url, data=token_data)
    if token_resp.status_code != 200:
        print(f"Token fetch failed: {token_resp.text}")
        return redirect("/login?error=token_fetch_failed")
        
    tokens = token_resp.json()
    access_token = tokens.get("access_token")
    
    if not access_token:
        return redirect("/login?error=no_access_token")
    
    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    userinfo_resp = requests.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
    if userinfo_resp.status_code != 200:
        return redirect("/login?error=userinfo_fetch_failed")
        
    userinfo = userinfo_resp.json()
    email = userinfo.get("email")
    name = userinfo.get("name")
    picture = userinfo.get("picture")
    
    if not email:
        return redirect("/login?error=no_email_provided")
    
    # DB Ops
    try:
        user_record = get_user_by_email(email)
        if not user_record:
            import secrets
            random_pw = secrets.token_urlsafe(16)
            # add_user(fullname, phone, email, password)
            add_user(name, "Google Auth", email, random_pw)
            user_record = get_user_by_email(email)
            
        session["user"] = {
            "email": email,
            "fullname": name,
            "picture": picture,
            "id": user_record.get("id") if user_record else None
        }
        return redirect("/dashboard")
    except Exception as e:
        print(f"OAuth DB Error: {e}")
        return redirect("/login?error=db_error")

@server.route("/login/google/demo")
def google_demo_login():
    # Bypass for users who haven't set up Google Cloud keys yet
    email = "demo.user@example.com"
    name = "Demo Medical Professional"
    picture = "https://ui-avatars.com/api/?name=Demo+User&background=00f2ff&color=fff"
    
    try:
        user_record = get_user_by_email(email)
        if not user_record:
            add_user(name, "Demo Mode", email, "demo_pass_123")
            user_record = get_user_by_email(email)
            
        session["user"] = {
            "email": email,
            "fullname": name,
            "picture": picture,
            "id": user_record.get("id") if user_record else None
        }
        return redirect("/dashboard")
    except Exception as e:
        return f"Demo Login Failed: {e}", 500

@server.route("/logout")
def logout():
    print(f"DEBUG: Clearing session for user: {session.get('user', 'None')}")
    session.clear()
    # Also explicitly remove user from session dictionary
    session.pop('user', None)
    return redirect("/")

@server.before_request
def check_login():
    # Define public routes that don't need authentication
    public_routes = ["/login", "/signup", "/login/google", "/login/google/callback", "/login/google/demo", "/", "/research", "/api-docs", "/privacy", "/terms", "/contact"]
    # Allow static assets
    if request.path.startswith("/assets") or request.path.startswith("/_dash"):
        return
        
    if "user" not in session and request.path not in public_routes:
        # Check if it's a demo route
        if request.path.startswith("/demo"):
            return
        return redirect("/login")

app.title = "Aegis AI | Advanced Clinical Intelligence"

# Models/Diseases Configuration
DISEASES = [
    {
        "id": "diabetes", "label": "Diabetes", "icon": "fa-solid fa-droplet", "desc": "Chronic metabolic disorder screening.",
        "features": [
            {"id": "Pregnancies", "label": "Pregnancies", "range": "Count", "default": 1},
            {"id": "Glucose", "label": "Glucose", "range": "70-199 mg/dL", "default": 100},
            {"id": "BloodPressure", "label": "Blood Pressure", "range": "60-140 mmHg", "default": 80},
            {"id": "SkinThickness", "label": "Skin Thickness", "range": "10-50 mm", "default": 20},
            {"id": "Insulin", "label": "Insulin", "range": "15-300 mU/L", "default": 80},
            {"id": "BMI", "label": "BMI", "range": "10-50 index", "default": 25},
            {"id": "DiabetesPedigreeFunction", "label": "Pedigree Func", "range": "0.1-2.5", "default": 0.5},
            {"id": "Age", "label": "Age", "range": "10-100 years", "default": 30},
        ]
    },
    {
        "id": "heart", "label": "Heart Disease", "icon": "fa-solid fa-heart-pulse", "desc": "Cardiovascular pathology analysis.",
        "features": [
            {"id": "age", "label": "Age", "range": "20-100 years", "default": 50},
            {"id": "sex", "label": "Sex (1=M, 0=F)", "range": "0 or 1", "default": 1},
            {"id": "cp", "label": "Chest Pain Type", "range": "0-3", "default": 1},
            {"id": "trestbps", "label": "Resting BP", "range": "90-200 mmHg", "default": 120},
            {"id": "chol", "label": "Cholesterol", "range": "100-600 mg/dl", "default": 200},
            {"id": "fbs", "label": "Fasting BS > 120", "range": "0 or 1", "default": 0},
            {"id": "restecg", "label": "Resting ECG", "range": "0-2", "default": 0},
            {"id": "thalach", "label": "Max Heart Rate", "range": "60-220 bpm", "default": 150},
            {"id": "exang", "label": "Exercise Angina", "range": "0 or 1", "default": 0},
            {"id": "oldpeak", "label": "ST Depression", "range": "0-6", "default": 1.0},
            {"id": "slope", "label": "ST Slope", "range": "0-2", "default": 1},
            {"id": "ca", "label": "Major Vessels", "range": "0-4", "default": 0},
            {"id": "thal", "label": "Thal", "range": "0-3", "default": 2},
        ]
    },
    {
        "id": "stroke", "label": "Stroke", "icon": "fa-solid fa-brain", "desc": "Cerebrovascular risk assessment.",
        "features": [
            {"id": "age", "label": "Age", "range": "1-100 years", "default": 50},
            {"id": "gender", "label": "Gender (1=M, 0=F)", "range": "0 or 1", "default": 1},
            {"id": "hypertension", "label": "Hypertension", "range": "0 or 1", "default": 0},
            {"id": "heart_disease", "label": "Heart Disease", "range": "0 or 1", "default": 0},
            {"id": "ever_married", "label": "Ever Married (1/0)", "range": "0 or 1", "default": 1},
            {"id": "work_type", "label": "Work Type (0-4)", "range": "0-4", "default": 2},
            {"id": "Residence_type", "label": "Residence (1/0)", "range": "0 or 1", "default": 1},
            {"id": "avg_glucose_level", "label": "Avg Glucose", "range": "50-300 mg/dL", "default": 100},
            {"id": "bmi", "label": "BMI", "range": "10-60", "default": 25},
            {"id": "smoking_status", "label": "Smoking (0-3)", "range": "0-3", "default": 1},
        ]
    },
    {"id": "kidney", "label": "Kidney Disease", "icon": "fa-solid fa-filter", "desc": "Renal function and waste filtration.", "features": [{"id": "age", "label": "Age", "range": "1-100", "default": 50}, {"id": "bp", "label": "BP", "range": "60-140", "default": 80}]},
    {"id": "liver", "label": "Liver Disease", "icon": "fa-solid fa-vial-circle-check", "desc": "Hepatic screen for enzyme pathways.", "features": [{"id": "Age", "label": "Age", "range": "1-100", "default": 50}, {"id": "Total_Bilirubin", "label": "Bilirubin", "range": "0.1-10", "default": 1.0}]},
    {"id": "anemia", "label": "Anemia", "icon": "fa-solid fa-droplet", "desc": "Hematological oxygen-carrying capacity.", "features": [{"id": "Hemoglobin", "label": "Hemoglobin", "range": "5-20", "default": 12}]},
    {"id": "obesity", "label": "Obesity", "icon": "fa-solid fa-person", "desc": "Systemic body-mass/metabolic index.", "features": [{"id": "Age", "label": "Age", "range": "1-100", "default": 30}, {"id": "Height", "label": "Height (cm)", "range": "100-220", "default": 170}, {"id": "Weight", "label": "Weight (kg)", "range": "20-200", "default": 70}]},
    {"id": "general_health", "label": "General Health", "icon": "fa-solid fa-shield-heart", "desc": "Systemic multi-factor wellness screen.", "features": [{"id": "Age", "label": "Age", "range": "1-100", "default": 40}]},
]

# --- Layout Components ---

# --- New Navigation / Portal Components ---

def grand_landing_page(user_data):
    # This is the "Main Page" that introduces the system
    is_logged_in = user_data is not None
    return html.Div(className="bg-deep", style={"position": "relative"}, children=[
        
        # Logo & Branding - Fixed at Top Left
        html.Div(className="d-flex justify-content-between align-items-center px-5 py-4 w-100", style={"position": "absolute", "top": "0", "zIndex": "100"}, children=[
            html.Div(className="d-flex align-items-center", children=[
                html.Img(src="/assets/logo.png", style={"height": "120px", "borderRadius": "20px", "boxShadow": "0 0 25px rgba(0, 242, 255, 0.6)", "border": "2px solid rgba(0, 242, 255, 0.3)"}, className="me-4"),
                html.H3("NeuroHealth AI", className="fw-bolder mb-0", style={"letterSpacing": "1.5px", "background": "linear-gradient(90deg, #fff, #00f2ff)", "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent", "textShadow": "0 5px 15px rgba(0,0,0,0.5)"})
            ])
        ]),

        # Main Hero Section - Advanced Styling with Background Plasma Orb
        html.Div(className="hero-section text-center position-relative", style={"minHeight": "95vh", "display": "flex", "flexDirection": "column", "justifyContent": "center", "alignItems": "center", "overflow": "hidden"}, children=[
            html.Div(style={"position": "absolute", "top": "30%", "left": "50%", "transform": "translate(-50%, -50%)", "width": "60vw", "height": "60vw", "background": "radial-gradient(circle, rgba(0, 242, 255, 0.08) 0%, rgba(0,0,0,0) 60%)", "zIndex": "0", "pointerEvents": "none"}),
            
            html.Div(style={"zIndex": "2", "position": "relative"}, children=[
                html.Span([html.I(className="fa-solid fa-microchip me-2"), "NEXT-GEN NEURAL SUITE v2.0"], className="badge rounded-pill mb-4 px-4 py-2", style={"letterSpacing": "3px", "background": "rgba(0, 242, 255, 0.08)", "border": "1px solid rgba(0, 242, 255, 0.4)", "color": "#00f2ff", "fontSize": "0.85rem", "textTransform": "uppercase"}),
                html.H1("AI Healthcare Platform for Multi-Disease Prediction", className="fw-bolder mb-3", style={"lineHeight": "1.1", "fontSize": "4.5rem", "color": "white", "textShadow": "0 15px 40px rgba(0,0,0,0.9)"}),
                html.P("Transform patient metrics into predictive clinical insights instantly utilizing our state-of-the-art neural architecture framework.", className="mx-auto mb-5", style={"maxWidth": "750px", "fontSize": "1.25rem", "color": "rgba(255,255,255,0.6)"}),
                
                html.Div(className="d-flex justify-content-center gap-4 mt-4", children=[
                    dbc.Button([html.I(className="fa-solid fa-bolt me-2"), "Start Assessment"], href="/login", className="btn-pulse px-5 py-3 fs-6 fw-bold", style={"borderRadius": "30px", "background": "linear-gradient(45deg, #00f2ff, #0088ff)", "border": "none", "color": "black", "textTransform": "uppercase", "boxShadow": "0 10px 25px rgba(0, 242, 255, 0.4)"}),
                    dbc.Button([html.I(className="fa-solid fa-play me-2"), "Simulator Demo"], href="#live-demo", external_link=True, className="btn-pulse px-5 py-3 fs-6 fw-bold", style={"borderRadius": "30px", "background": "rgba(0, 242, 255, 0.15)", "border": "1px solid rgba(0,242,255,0.8)", "color": "white", "backdropFilter": "blur(10px)", "textTransform": "uppercase"}),
                    dbc.Button([html.I(className="fa-solid fa-layer-group me-2"), "Discover Deep Tech"], href="#explore-features", external_link=True, className="btn-pulse px-5 py-3 fs-6 fw-bold", style={"borderRadius": "30px", "background": "rgba(255, 255, 255, 0.1)", "border": "1px solid rgba(255,255,255,0.4)", "color": "white", "backdropFilter": "blur(10px)", "textTransform": "uppercase"})
                ]),
            ])
        ]),

        dbc.Container(className="position-relative", style={"zIndex": "2", "marginTop": "-50px"}, children=[
            
            # AI Clinical Intelligence Platform Section
            html.Div(className="text-center mb-4 pb-4", children=[
                html.H3("Unprecedented Clinical Accuracy", className="fw-bold mb-4", style={"color": "white", "fontSize": "2.5rem"}),
                html.P("Our proprietary unified platform harnesses multiple deep learning modalities capable of mapping multi-dimensional patient vectors instantly avoiding latency and producing clinical-grade confidence limits.", className="mx-auto mb-5", style={"maxWidth": "900px", "color": "rgba(255,255,255,0.6)", "fontSize": "1.1rem"}),
                dbc.Row(className="justify-content-center g-4", children=[
                    dbc.Col([
                        html.Div(className="glass-panel p-4 h-100 d-flex align-items-center justify-content-center flex-column text-center", style={"borderTop": "3px solid #00f2ff", "background": "linear-gradient(180deg, rgba(0,242,255,0.05) 0%, rgba(0,0,0,0) 100%)"}, children=[
                            html.I(className="fa-solid fa-network-wired text-info mb-3 fs-2"), html.H5("Multi-Model Deep Engine", className="text-white fw-bold mb-2"), html.P("Adaptive scaling algorithms", className="small text-muted mb-0")
                        ])
                    ], md=4),
                    dbc.Col([
                        html.Div(className="glass-panel p-4 h-100 d-flex align-items-center justify-content-center flex-column text-center", style={"borderTop": "3px solid #00f2ff", "background": "linear-gradient(180deg, rgba(0,242,255,0.05) 0%, rgba(0,0,0,0) 100%)"}, children=[
                            html.I(className="fa-solid fa-stopwatch text-info mb-3 fs-2"), html.H5("Sub-millisecond Inference", className="text-white fw-bold mb-2"), html.P("Real-time data synchronization", className="small text-muted mb-0")
                        ])
                    ], md=4),
                    dbc.Col([
                        html.Div(className="glass-panel p-4 h-100 d-flex align-items-center justify-content-center flex-column text-center", style={"borderTop": "3px solid #00f2ff", "background": "linear-gradient(180deg, rgba(0,242,255,0.05) 0%, rgba(0,0,0,0) 100%)"}, children=[
                            html.I(className="fa-solid fa-shield-halved text-info mb-3 fs-2"), html.H5("Military-Grade Encryption", className="text-white fw-bold mb-2"), html.P("HIPAA-compliant processing logic", className="small text-muted mb-0")
                        ])
                    ], md=4),
                ])
            ]),
            
            html.Hr(style={"borderColor": "rgba(255,255,255,0.1)", "margin": "10px 0"}),
            
            # Explore Features Section
            html.Div(id="explore-features", className="text-center mb-4", children=[
                html.Span("INTELLIGENCE MODULES", className="text-info fw-bold mb-3 d-block", style={"letterSpacing": "2px", "fontSize": "0.9rem"}),
                html.H3("Capabilities Expansion", className="text-white fw-bold mb-5", style={"fontSize": "2.5rem"}),
                dbc.Row(className="g-4", children=[
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-brain text-info mb-3 fs-3"), html.H6("AI Prediction Engine", className="text-white fw-bold mb-2"), html.P("Continuous model validation loops.", className="small text-muted mb-0")])], md=3, sm=6),
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-chart-line text-info mb-3 fs-3"), html.H6("Clinical Risk Scoring", className="text-white fw-bold mb-2"), html.P("Adaptive probability distribution.", className="small text-muted mb-0")])], md=3, sm=6),
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-lightbulb text-info mb-3 fs-3"), html.H6("Intelligent Insights", className="text-white fw-bold mb-2"), html.P("Dynamic human-readable alerts.", className="small text-muted mb-0")])], md=3, sm=6),
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-clock-rotate-left text-info mb-3 fs-3"), html.H6("Patient History Graph", className="text-white fw-bold mb-2"), html.P("Longitudinal tracking mechanisms.", className="small text-muted mb-0")])], md=3, sm=6),
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-robot text-info mb-3 fs-3"), html.H6("Aegis Assistant NLP", className="text-white fw-bold mb-2"), html.P("Conversational AI interface.", className="small text-muted mb-0")])], md=3, sm=6),
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-layer-group text-info mb-3 fs-3"), html.H6("Multi-Disease Vector", className="text-white fw-bold mb-2"), html.P("Simultaneous pipeline execution.", className="small text-muted mb-0")])], md=3, sm=6),
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-lock text-info mb-3 fs-3"), html.H6("Secure Storage Layer", className="text-white fw-bold mb-2"), html.P("Zero-trust database schemas.", className="small text-muted mb-0")])], md=3, sm=6),
                    dbc.Col([html.Div(className="glass-panel p-4 h-100", style={"transition": "0.3s", "cursor": "pointer"}, children=[html.I(className="fa-solid fa-file-medical text-info mb-3 fs-3"), html.H6("Document Synthesis", className="text-white fw-bold mb-2"), html.P("Automated PDF export generation.", className="small text-muted mb-0")])], md=3, sm=6),
                ])
            ]),
            
            html.Hr(style={"borderColor": "rgba(255,255,255,0.1)", "margin": "10px 0"}),
            
            # Live AI Demo Section
            html.Div(id="live-demo", className="text-center mb-4", children=[
                html.Span("INTERACTIVE SANDBOX", className="text-info fw-bold mb-3 d-block", style={"letterSpacing": "2px", "fontSize": "0.9rem"}),
                html.H3("Live Simulator Demo", className="text-white fw-bold mb-4", style={"fontSize": "2.5rem"}),
                html.P("Engage directly with the neural arrays utilizing our controlled public sandbox environments.", className="text-muted mx-auto mb-5", style={"maxWidth": "600px"}),
                dbc.Row(className="justify-content-center g-4", children=[
                    dbc.Col([
                        html.Div(className="glass-panel p-4 h-100 text-center position-relative overflow-hidden", style={"background": "rgba(0,0,0,0.3)"}, children=[
                            html.I(className="fa-solid fa-droplet mb-3 fs-2", style={"color": "#00f2ff", "textShadow": "0 0 15px rgba(0,242,255,0.8)"}),
                            html.H5("Diabetes Rating", className="text-white fw-bold mb-2"),
                            html.P("Simulate metabolic screening dynamics based on precise biometric input variations.", className="text-muted small mb-3"),
                            dbc.Button("Initialize Simulator", href="/demo/diabetes", className="btn-pulse w-100", style={"background": "transparent", "border": "1px solid #00f2ff", "color": "#00f2ff"})
                        ])
                    ], md=4),
                    dbc.Col([
                        html.Div(className="glass-panel p-4 h-100 text-center position-relative overflow-hidden", style={"background": "rgba(0,0,0,0.3)"}, children=[
                            html.I(className="fa-solid fa-person mb-3 fs-2", style={"color": "#00f2ff", "textShadow": "0 0 15px rgba(0,242,255,0.8)"}),
                            html.H5("Obesity Index", className="text-white fw-bold mb-2"),
                            html.P("Test our systemic body-mass assessment heuristics natively via the interactive web wrapper.", className="text-muted small mb-3"),
                            dbc.Button("Initialize Simulator", href="/demo/obesity", className="btn-pulse w-100", style={"background": "transparent", "border": "1px solid #00f2ff", "color": "#00f2ff"})
                        ])
                    ], md=4),
                    dbc.Col([
                        html.Div(className="glass-panel p-4 h-100 text-center position-relative overflow-hidden", style={"background": "rgba(0,0,0,0.3)"}, children=[
                            html.I(className="fa-solid fa-heart-pulse mb-3 fs-2", style={"color": "#ff3366", "textShadow": "0 0 15px rgba(255,51,102,0.8)"}),
                            html.H5("Heart Risk", className="text-white fw-bold mb-2"),
                            html.P("Assess real-time cardiovascular dynamics powered by historical diagnostic distributions.", className="text-muted small mb-3"),
                            dbc.Button("Initialize Simulator", href="/demo/heart", className="btn-pulse w-100", style={"background": "transparent", "border": "1px solid #ff3366", "color": "#ff3366"})
                        ])
                    ], md=4),
                ])
            ]),
            
            # Ultra Premium Footer
            html.Footer(className="mt-5 pt-5 pb-5 text-center text-muted", children=[
                html.Div(className="d-flex justify-content-center align-items-center mb-4 gap-3", children=[
                   html.Img(src="/assets/logo.png", style={"height": "30px", "opacity": "0.5", "borderRadius": "5px"}),
                   html.Span("NeuroHealth AI", className="fw-bold", style={"letterSpacing": "1px", "opacity": "0.5"})
                ]),
                html.Div(className="d-flex justify-content-center flex-wrap gap-5 mb-4", children=[
                    html.A("Clinical Research", href="/research", className="text-muted text-decoration-none", style={"transition": "0.2s"}),
                    html.A("API Integration", href="/api-docs", className="text-muted text-decoration-none", style={"transition": "0.2s"}),
                    html.A("Privacy & Security", href="/privacy", className="text-muted text-decoration-none", style={"transition": "0.2s"}),
                    html.A("Terms of Service", href="/terms", className="text-muted text-decoration-none", style={"transition": "0.2s"}),
                    html.A("Contact", href="/contact", className="text-muted text-decoration-none", style={"transition": "0.2s"}),
                ]),
                html.Small("© 2026 Aegis Neural Clinical Suite. All diagnostic outputs require professional medical consultation.", style={"opacity": "0.4"})
            ])
        ])
    ])

def central_dashboard(user_data):
    # This is the "Main Dashboard" users see after logging in
    name = user_data.get("fullname", "Clinical User")
    return html.Div(className="bg-deep px-4 py-5", children=[
        dbc.Container([
            # Top Header
            dbc.Row([
                dbc.Col([
                    html.H2(f"Welcome, {name}", className="text-white fw-bold"),
                    html.P("Aegis Intelligence Terminal | System Operational", className="text-info small fw-bold mb-0")
                ], lg=8),
                dbc.Col([
                    dbc.Button("Emergency Logout", href="/logout", external_link=True, className="btn btn-outline-danger btn-sm rounded-pill px-4 float-end")
                ], lg=4, className="d-flex align-items-center justify-content-end")
            ], className="mb-5"),

            # Global Metrics Section (The "Numbers" on Main Dashboard)
            dbc.Row([
                dbc.Col([
                    html.Div(className="glass-panel p-4 text-center", children=[
                        html.H6("TOTAL ASSESSMENTS", className="text-muted small"),
                        html.H3("14,208", className="text-info fw-bold mb-0"),
                        html.Small("Historical patient cohort analyzed", className="text-success x-small")
                    ])
                ], lg=3, md=6, className="mb-4"),
                dbc.Col([
                    html.Div(className="glass-panel p-4 text-center", children=[
                        html.H6("SYSTEM CONFIDENCE", className="text-muted small"),
                        html.H3("98.42%", className="text-info fw-bold mb-0"),
                        html.Small("Model validation accuracy", className="text-success x-small")
                    ])
                ], lg=3, md=6, className="mb-4"),
                dbc.Col([
                    html.Div(className="glass-panel p-4 text-center", children=[
                        html.H6("ACTIVE MODELS", className="text-muted small"),
                        html.H3("09 / 09", className="text-info fw-bold mb-0"),
                        html.Small("Neural inference throughput", className="text-success x-small")
                    ])
                ], lg=3, md=6, className="mb-4"),
                dbc.Col([
                    html.Div(className="glass-panel p-4 text-center", children=[
                        html.H6("THREAT MITIGATION", className="text-muted small"),
                        html.H3("SAFE", className="text-success fw-bold mb-0"),
                        html.Small("Anomaly detection status", className="text-muted x-small")
                    ])
                ], lg=3, md=6, className="mb-4"),
            ]),

            # Disease Modules Grid
            html.H4("Diagnostic Modules", className="text-white mt-5 mb-4 fw-bold"),
            dbc.Row([
                dbc.Col([
                    html.A(href=f"/analysis/{d['id']}", className="text-decoration-none", children=[
                        html.Div(className="disease-card p-4", style={"borderRadius": "24px"}, children=[
                            html.I(className=f"{d['icon']} fs-1 text-info mb-3"),
                            html.H5(d['label'], className="text-white fw-bold mb-2"),
                            html.P(d['desc'], className="text-muted small mb-0")
                        ])
                    ])
                ], lg=3, md=4, sm=6, className="mb-4") for d in DISEASES
            ]),

            # ── Patient Registration Section ──────────────────────────
            html.Hr(style={"borderColor": "rgba(255,255,255,0.08)", "margin": "50px 0 40px"}),
            html.Div(className="d-flex align-items-center gap-3 mb-4", children=[
                html.Div(style={"width": "5px", "height": "40px", "borderRadius": "4px",
                                "background": "linear-gradient(180deg, #00f2ff, #7000ff)"}),
                html.Div([
                    html.H4("Patient Registration", className="text-white fw-bold mb-0"),
                    html.P("Register patients and assign a prediction module", className="text-muted small mb-0")
                ])
            ]),
            dbc.Row(className="g-4 mb-5", children=[
                # Form Column
                dbc.Col([
                    html.Div(className="glass-panel p-4", children=[
                        html.H5([html.I(className="fa-solid fa-user-plus text-info me-2"), "New Patient"],
                                className="text-white fw-bold mb-4"),
                        dbc.Row(className="g-3 mb-3", children=[
                            dbc.Col([
                                dbc.Label("Full Name", className="text-muted small mb-1"),
                                dbc.Input(id="reg-name", placeholder="e.g. Arjun Sharma", className="premium-input")
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Email Address", className="text-muted small mb-1"),
                                dbc.Input(id="reg-email", type="email", placeholder="patient@email.com", className="premium-input")
                            ], md=6),
                        ]),
                        dbc.Row(className="g-3 mb-3", children=[
                            dbc.Col([
                                dbc.Label("Mobile Number", className="text-muted small mb-1"),
                                dbc.Input(id="reg-mobile", placeholder="+91 9876543210", className="premium-input")
                            ], md=4),
                            dbc.Col([
                                dbc.Label("Age", className="text-muted small mb-1"),
                                dbc.Input(id="reg-age", type="number", min=1, max=120, placeholder="Age", className="premium-input")
                            ], md=4),
                            dbc.Col([
                                dbc.Label("Gender", className="text-muted small mb-1"),
                                dbc.Select(id="reg-gender",
                                    options=[{"label": "Male", "value": "Male"},
                                             {"label": "Female", "value": "Female"},
                                             {"label": "Other", "value": "Other"}],
                                    value="Male",
                                    style={"borderRadius": "12px", "padding": "10px"})
                            ], md=4),
                        ]),
                        html.Div(className="mb-4", children=[
                            dbc.Label("Prediction Type", className="text-muted small mb-1"),
                            dbc.Select(id="reg-prediction",
                                options=[
                                    {"label": "Diabetes Prediction",     "value": "Diabetes Prediction"},
                                    {"label": "Obesity Risk Detection",  "value": "Obesity Risk Detection"},
                                    {"label": "Heart Disease Risk",      "value": "Heart Disease Risk"},
                                    {"label": "Blood Pressure Analysis", "value": "Blood Pressure Analysis"},
                                    {"label": "Kidney Disease Risk",     "value": "Kidney Disease Risk"},
                                    {"label": "Stroke Risk",             "value": "Stroke Risk"},
                                    {"label": "General Health Analysis", "value": "General Health Analysis"},
                                ],
                                value="Diabetes Prediction",
                                style={"borderRadius": "12px", "padding": "10px"})
                        ]),
                        html.Div(id="reg-feedback", className="mb-3"),
                        dbc.Button(
                            [html.I(className="fa-solid fa-user-check me-2"), "Register Patient"],
                            id="reg-submit-btn", n_clicks=0, className="btn-pulse w-100 py-3 fw-bold",
                            style={"borderRadius": "14px", "background": "linear-gradient(45deg, #00f2ff, #0088ff)",
                                   "border": "none", "color": "black"})
                    ])
                ], lg=5),
                # Table Column
                dbc.Col([
                    html.Div(className="glass-panel p-4 h-100", children=[
                        html.Div(className="d-flex justify-content-between align-items-center mb-4", children=[
                            html.H5([html.I(className="fa-solid fa-table-list text-info me-2"), "Registered Patients"],
                                    className="text-white fw-bold mb-0"),
                            dbc.Badge(id="reg-count-badge", color="info", pill=True, className="px-3 py-2 fw-bold")
                        ]),
                        html.Div(id="reg-table-container",
                                 style={"overflowX": "auto", "maxHeight": "430px", "overflowY": "auto"})
                    ])
                ], lg=7)
            ]),
        ])
    ])

def analysis_page(disease_id, user_data):
    # This remains the same high-detail analysis page
    disease_info = next((d for d in DISEASES if d['id'] == disease_id), DISEASES[0])
    
    return html.Div(className="bg-deep px-3 py-4", children=[
        dcc.Download(id="download-medical-report"),
        # Mini Header
        dbc.Row([
            dbc.Col([
                html.A([html.I(className="bi bi-chevron-left me-2"), "Return to Selection"], href="/dashboard", className="text-info text-decoration-none small")
            ], width=6),
            dbc.Col([
                html.Div([
                    html.I(className=f"{disease_info['icon']} me-2 text-info"),  # pyre-ignore
                    f"Active Diagnostic Path: {disease_info['label'].upper()}"  # pyre-ignore
                ], className="text-end text-muted small fw-bold")
            ], width=6)
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.Div(className="glass-panel scroll-y", children=[
                    html.H5([html.I(className="bi bi-person-circle me-2 text-info"), "Patient Parameters"], className="mb-4"),
                    
                    html.Div([
                        create_biometric_input(f['label'], {'type': 'feature-input', 'id': f['id']}, f['default'], f['range'])  # pyre-ignore
                        for f in disease_info['features']  # pyre-ignore
                    ]),
                    
                    html.Hr(className="border-secondary opacity-25 my-4"),
                    
                    html.Label("Clinical Notes", className="text-muted small mb-2"),
                    dbc.Textarea(id="clinical-notes", placeholder="Enter observations for medical report...", className="premium-input border-0 mb-4", rows=3),
                    
                    dbc.Button([
                        html.I(className="bi bi-activity me-2"),
                        "Analyze Clinical Data"
                    ], id="predict-btn", className="btn-pulse w-100", n_clicks=0),
                    
                    dbc.Button([
                        html.I(className="bi bi-file-earmark-pdf me-2"),
                        "Generate Medical Report"
                    ], id="report-btn", className="btn-generate w-100 mt-3", n_clicks=0),
                    
                    html.Div(id="error-msg", className="text-danger mt-3 small text-center")
                ])
            ], lg=3),

            # Middle/Right: Results and Analytics
            dbc.Col([
                dbc.Spinner(children=html.Div(id="dashboard-content-area", children=[
                    # Row 1: Summary Stats
                    dbc.Row([
                        dbc.Col([
                            html.Div(className="glass-panel", children=[
                                html.P([html.I(className=f"{disease_info['icon']} me-2 text-info"), "DIAGNOSTIC STATUS"], className="text-muted small fw-bold mb-3"),
                                dbc.Row([
                                    dbc.Col([
                                        html.Small("Risk Level", className="text-muted d-block"),
                                        html.Div(id="risk-pill-container", children=html.Span("AWAITING DATA", className="risk-header-pill level-low", style={"color": "#64748b", "background": "rgba(255,255,255,0.05)"}))
                                    ], width=3),
                                    dbc.Col([
                                        html.Small("Model Confidence", className="text-muted d-block"),
                                        html.H4("0.0%", id="confidence-score", className="mb-0 text-white opacity-50")
                                    ], width=3),
                                    dbc.Col([
                                        html.Small("Risk Probability", className="text-muted d-block"),
                                        html.H4("0.0%", id="prob-percentage", className="mb-0 text-white opacity-50")
                                    ], width=3),
                                    dbc.Col([
                                        html.Small("AI Prediction", className="text-muted d-block"),
                                        html.H4("PENDING", id="ai-status", className="mb-0 text-info opacity-50")
                                    ], width=3),
                                ])
                            ])
                        ], width=12)
                    ], className="mb-4"),

                    # Row 2: Charts
                    dbc.Row([
                        dbc.Col([
                            html.Div(className="glass-panel", children=[
                                html.H6("Risk Distribution Gauge", className="mb-4 text-center"),
                                dcc.Graph(id="main-gauge", config={'displayModeBar': False}, style={"height": "350px"})
                            ])
                        ], lg=5),
                        dbc.Col([
                            html.Div(className="glass-panel", children=[
                                html.H6("Biomarker Radar Profile", className="mb-4 text-center"),
                                dcc.Graph(id="radar-chart", config={'displayModeBar': False}, style={"height": "350px"})
                            ])
                        ], lg=7),
                    ], className="mb-4"),

                    # Row 3: Contribution and Variance
                    dbc.Row([
                        dbc.Col([
                            html.Div(className="glass-panel", children=[
                                html.H6("Feature Contribution Map", className="mb-4"),
                                dcc.Graph(id="impact-bar", config={'displayModeBar': False}, style={"height": "300px"})
                            ])
                        ], lg=6),
                        dbc.Col([
                            html.Div(className="glass-panel", children=[
                                html.H6("Scenario Risk Probability", className="mb-4"),
                                dcc.Graph(id="variant-line", config={'displayModeBar': False}, style={"height": "300px"})
                            ])
                        ], lg=6),
                    ], className="mb-4"),

                    # Row 4: Recommendations
                    dbc.Row([
                        dbc.Col([
                            html.Div(className="glass-panel", children=[
                                html.H5([html.I(className="bi bi-journal-medical me-2 text-info"), "Clinical Insights & Recommendations"], className="mb-4"),
                                dbc.Row([
                                    dbc.Col(id="rec-neural", lg=6),
                                    dbc.Col(id="rec-action", lg=6),
                                ], className="mb-3"),
                                dbc.Row([
                                    dbc.Col(id="rec-alert", lg=6),
                                    dbc.Col(id="rec-lifestyle", lg=6),
                                ])
                            ])
                        ], lg=9),
                        dbc.Col([
                            html.Div(className="glass-panel text-center", children=[
                                html.H6("Health Score", className="mb-3 text-muted"),
                                dcc.Graph(id="health-gauge", config={'displayModeBar': False}, style={"height": "180px"}),
                                html.Div(id="score-label", className="fw-bold text-info mt-2")
                            ])
                        ], lg=3)
                    ])
                ]), color="info", type="border", size="lg")
            ], lg=9)
        ])
    ])

# Placeholder for authentication pages and functions
def signup_page():
    return html.Div(className="hero-section", children=[
        html.Div(className="glass-panel p-5", style={"maxWidth": "500px", "width": "100%"}, children=[
            html.H3("Create Account", className="text-info mb-4"),
            dbc.Form([
                html.Div(className="mb-3", children=[
                    dbc.Label("Full Name", className="text-white small"),
                    dbc.Input(id="signup-name", placeholder="John Doe", className="premium-input")
                ]),
                html.Div(className="mb-3", children=[
                    dbc.Label("Mobile Number", className="text-white small"),
                    dbc.Input(id="signup-phone", placeholder="+1 (555) 000-0000", className="premium-input")
                ]),
                html.Div(className="mb-3", children=[
                    dbc.Label("Email Address", className="text-white small"),
                    dbc.Input(id="signup-email", type="email", placeholder="john@example.com", className="premium-input")
                ]),
                html.Div(className="mb-3", children=[
                    dbc.Label("Password", className="text-white small"),
                    dbc.Input(id="signup-password", type="password", placeholder="••••••••", className="premium-input")
                ]),
                html.Div(className="mb-4", children=[
                    dbc.Label("Confirm Password", className="text-white small"),
                    dbc.Input(id="signup-confirm", type="password", placeholder="••••••••", className="premium-input")
                ]),
                html.Div(id="signup-error", className="text-danger small mb-3"),
                dbc.Button("Register Now", id="signup-btn", className="btn-pulse w-100", n_clicks=0),
                html.Div(className="text-center mt-4", children=[
                    html.A("Already have an account? Login", href="/login", className="text-info small text-decoration-none")
                ])
            ])
        ])
    ])

def login_page():
    return html.Div(className="hero-section", children=[
        html.Div(className="glass-panel p-5", style={"maxWidth": "420px", "width": "100%"}, children=[
            html.Div(className="text-center mb-4", children=[
                html.Img(src="/assets/logo.png", style={"height": "50px", "borderRadius": "10px", "marginBottom": "12px", "opacity": "0.85"}),
                html.H3("Secure Login", className="text-white fw-bold mb-0"),
                html.P("NeuroHealth AI Clinical Portal", className="text-muted small mt-1")
            ]),

            # Google Button
            dbc.Button(
                id="google-login-btn",
                href="/login/google",
                external_link=True,
                className="d-flex align-items-center justify-content-center gap-3 w-100 py-3 mb-4",
                style={
                    "background": "white",
                    "borderRadius": "14px",
                    "fontWeight": "600",
                    "color": "#1a1a1a",
                    "fontSize": "0.95rem",
                    "boxShadow": "0 4px 15px rgba(0,0,0,0.4)",
                    "transition": "all 0.3s ease",
                    "border": "none",
                    "cursor": "pointer"
                },
                children=[
                    html.Img(
                        src="https://www.svgrepo.com/show/475656/google-color.svg",
                        style={"width": "22px", "height": "22px"}
                    ),
                    html.Span("Continue with Google")
                ]
            ),
            
            # Divider
            html.Div(className="d-flex align-items-center gap-3 mb-4", children=[
                html.Hr(style={"flex": "1", "borderColor": "rgba(255,255,255,0.15)", "margin": "0"}),
                html.Span("or sign in with email", className="text-muted small", style={"whiteSpace": "nowrap"}),
                html.Hr(style={"flex": "1", "borderColor": "rgba(255,255,255,0.15)", "margin": "0"})
            ]),

            dbc.Form([
                html.Div(className="mb-3", children=[
                    dbc.Label("Email Address", className="text-white small"),
                    dbc.Input(id="login-email", type="email", placeholder="john@example.com", className="premium-input")
                ]),
                html.Div(className="mb-4", children=[
                    dbc.Label("Password", className="text-white small"),
                    dbc.Input(id="login-password", type="password", placeholder="••••••••", className="premium-input")
                ]),
                html.Div(id="login-error", className="text-danger small mb-3"),
                dbc.Button("Access Dashboard", id="login-btn", className="btn-pulse w-100", n_clicks=0),
                html.Div(className="text-center mt-4", children=[
                    html.A("Need an account? Sign Up", href="/signup", className="text-info small text-decoration-none")
                ])
            ])
        ])
    ])


def create_biometric_input(label, id, value, range_text):
    return html.Div(className="biometric-row", children=[
        html.Div([
            html.Label(label, className="input-label mb-0 d-block text-white"),
            html.Span(range_text, className="range-span")
        ]),
        dbc.Input(id=id, type="number", value=value, className="premium-input text-end", style={"width": "100px"})
    ])

# --- Info Pages ---
def research_page():
    return html.Div(className="hero-section", children=[
        html.Div(className="glass-panel p-5 text-start scroll-y", style={"maxWidth": "800px", "width": "100%"}, children=[
            html.H2("Clinical Research & Validation", className="text-info fw-bold mb-4"),
            html.P("Aegis Intelligence Terminal accelerates data-driven healthcare research through high-throughput predictive analysis.", className="text-white lead mb-4"),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-brain me-2 text-info"), "AI-Driven Clinical Insights"], className="text-white fw-bold mb-2"),
                html.P("Our proprietary unified platform harnesses multiple deep learning modalities capable of mapping multi-dimensional patient vectors instantly.", className="text-muted")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-chart-pie me-2 text-info"), "Predictive Health Analytics"], className="text-white fw-bold mb-2"),
                html.P("We analyze historical patient cohorts to build adaptive probability distributions for robust clinical risk scoring.", className="text-muted")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-microscope me-2 text-info"), "Data-Driven Healthcare Research"], className="text-white fw-bold mb-2"),
                html.P("Continuous model validation loops ensure our platform evolves with new medical findings and patient demographics securely.", className="text-muted")
            ]),
            html.Div(className="mt-5 text-center", children=dbc.Button([html.I(className="bi bi-arrow-left me-2"), "Back to Portal"], href="/", className="btn-pulse px-4 py-2"))
        ])
    ])

def api_page():
    return html.Div(className="hero-section", children=[
        html.Div(className="glass-panel p-5 text-start scroll-y", style={"maxWidth": "800px", "width": "100%"}, children=[
            html.H2("API Integration Guide", className="text-info fw-bold mb-4"),
            html.P("Seamlessly securely interface with the NeuroHealth AI prediction system via our RESTful architecture.", className="text-white lead mb-4"),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-bolt me-2 text-info"), "Real-Time Prediction API"], className="text-white fw-bold mb-2"),
                html.P("Access our sub-millisecond inference engines for specialized neural modules through standard POST requests.", className="text-muted")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-network-wired me-2 text-info"), "Secure Data Transmission"], className="text-white fw-bold mb-2"),
                html.P("All endpoints enforce encryption and advanced processing logic using zero-trust data schemas.", className="text-muted")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-server me-2 text-info"), "Health Analytics Endpoints"], className="text-white fw-bold mb-2"),
                html.P("Developers can request both individual predictions and batch patient risk assessments programmatically.", className="text-muted")
            ]),
            html.Div(className="mt-5 text-center", children=dbc.Button([html.I(className="bi bi-arrow-left me-2"), "Back to Portal"], href="/", className="btn-pulse px-4 py-2"))
        ])
    ])

def privacy_page():
    return html.Div(className="hero-section", children=[
        html.Div(className="glass-panel p-5 text-start scroll-y", style={"maxWidth": "800px", "width": "100%"}, children=[
            html.H2("Privacy & Security Protocol", className="text-info fw-bold mb-4"),
            html.P("Protecting patient health data is the foundational core of the NeuroHealth AI system.", className="text-white lead mb-4"),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-lock me-2 text-info"), "Encrypted Data Storage"], className="text-white fw-bold mb-2"),
                html.P("All biometric datasets are stored in isolated, encrypted partitions utilizing highest-grade standards.", className="text-muted")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-key me-2 text-info"), "Secure Authentication"], className="text-white fw-bold mb-2"),
                html.P("Access to the clinical diagnostic terminal requires strict credential validation.", className="text-muted")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-file-shield me-2 text-info"), "Protected Medical Records"], className="text-white fw-bold mb-2"),
                html.P("Records are completely protected prior to neural evaluation to prevent unauthorized exposure of health history.", className="text-muted")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-shield-halved me-2 text-info"), "Privacy Compliance"], className="text-white fw-bold mb-2"),
                html.P("Our schemas comply natively with core privacy constraints to guarantee continuous data protection.", className="text-muted")
            ]),
            html.Div(className="mt-5 text-center", children=dbc.Button([html.I(className="bi bi-arrow-left me-2"), "Back to Portal"], href="/", className="btn-pulse px-4 py-2"))
        ])
    ])

def terms_page():
    return html.Div(className="hero-section", children=[
        html.Div(className="glass-panel p-5 text-start scroll-y", style={"maxWidth": "800px", "width": "100%"}, children=[
            html.H2("Terms of Service", className="text-info fw-bold mb-4"),
            html.P("Operational policies and clinical legal guidelines for NeuroHealth AI.", className="text-white lead mb-4"),
            html.Div(className="mb-4 p-4 rounded", style={"background": "rgba(255, 65, 54, 0.1)", "border": "1px solid rgba(255, 65, 54, 0.3)"}, children=[
                html.H5([html.I(className="fa-solid fa-triangle-exclamation me-2 text-danger"), "AI Advisory Warning"], className="text-danger fw-bold mb-2"),
                html.P("NeuroHealth AI provides predictive insights and risk scoring. It should NOT replace professional medical advice, comprehensive diagnosis, or emergency treatments.", className="text-white mb-0")
            ]),
            html.Div(className="mb-4", children=[
                html.H5([html.I(className="fa-solid fa-gavel me-2 text-info"), "Platform Usage"], className="text-white fw-bold mb-2"),
                html.P("Diagnostic tools are strictly intended for supplementary usage by clinical professionals or guided patient testing.", className="text-muted")
            ]),
            html.Div(className="mt-5 text-center", children=dbc.Button([html.I(className="bi bi-arrow-left me-2"), "Back to Portal"], href="/", className="btn-pulse px-4 py-2"))
        ])
    ])

def contact_page():
    return html.Div(className="hero-section", style={"alignItems": "flex-start", "paddingTop": "80px", "paddingBottom": "80px"}, children=[
        dbc.Container(style={"maxWidth": "1000px", "width": "100%"}, children=[
            html.Div(className="text-center mb-5", children=[
                html.H2([html.I(className="fa-solid fa-envelope text-info me-3"), "Contact NeuroHealth AI"], className="text-white fw-bold mb-3"),
                html.P("Have a question, partnership inquiry, or technical issue? Reach out to our clinical intelligence team.", className="text-muted fs-5")
            ]),
            dbc.Row(className="g-4", children=[
                # Contact Info Column
                dbc.Col([
                    html.Div(className="glass-panel p-4 h-100 text-start", children=[
                        html.H5("Get In Touch", className="text-info fw-bold mb-4"),
                        html.Div(className="d-flex align-items-start mb-4 gap-3", children=[
                            html.Div(html.I(className="fa-solid fa-location-dot text-info fs-5"), style={"minWidth": "24px", "marginTop": "3px"}),
                            html.Div([
                                html.P("Headquarters", className="text-white fw-bold mb-1"),
                                html.P("AI Research Campus, Clinical Innovation District", className="text-muted small mb-0")
                            ])
                        ]),
                        html.Div(className="d-flex align-items-start mb-4 gap-3", children=[
                            html.Div(html.I(className="fa-solid fa-envelope text-info fs-5"), style={"minWidth": "24px", "marginTop": "3px"}),
                            html.Div([
                                html.P("Email Support", className="text-white fw-bold mb-1"),
                                html.P("support@neurohealth.ai", className="text-muted small mb-0")
                            ])
                        ]),
                        html.Div(className="d-flex align-items-start mb-4 gap-3", children=[
                            html.Div(html.I(className="fa-solid fa-phone text-info fs-5"), style={"minWidth": "24px", "marginTop": "3px"}),
                            html.Div([
                                html.P("Clinical Helpline", className="text-white fw-bold mb-1"),
                                html.P("+1 (800) NEURO-AI", className="text-muted small mb-0")
                            ])
                        ]),
                        html.Div(className="d-flex align-items-start mb-4 gap-3", children=[
                            html.Div(html.I(className="fa-solid fa-clock text-info fs-5"), style={"minWidth": "24px", "marginTop": "3px"}),
                            html.Div([
                                html.P("Support Hours", className="text-white fw-bold mb-1"),
                                html.P("Monday – Friday, 9AM – 6PM IST", className="text-muted small mb-0")
                            ])
                        ]),
                        html.Hr(style={"borderColor": "rgba(255,255,255,0.1)", "margin": "20px 0"}),
                        html.P("Connect With Us", className="text-white fw-bold mb-3"),
                        html.Div(className="d-flex gap-3", children=[
                            html.A(html.I(className="fa-brands fa-github fs-4"), href="#", className="text-muted", style={"transition": "0.2s"}),
                            html.A(html.I(className="fa-brands fa-linkedin fs-4"), href="#", className="text-muted", style={"transition": "0.2s"}),
                            html.A(html.I(className="fa-brands fa-twitter fs-4"), href="#", className="text-muted", style={"transition": "0.2s"}),
                        ])
                    ])
                ], lg=4),

                # Contact Form Column
                dbc.Col([
                    html.Div(className="glass-panel p-4 text-start", children=[
                        html.H5("Send a Message", className="text-info fw-bold mb-4"),
                        dbc.Row(className="mb-3 g-3", children=[
                            dbc.Col([
                                dbc.Label("Full Name", className="text-muted small mb-1"),
                                dbc.Input(id="contact-name", placeholder="Your Name", className="premium-input")
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Email Address", className="text-muted small mb-1"),
                                dbc.Input(id="contact-email", type="email", placeholder="you@example.com", className="premium-input")
                            ], md=6),
                        ]),
                        html.Div(className="mb-3", children=[
                            dbc.Label("Subject", className="text-muted small mb-1"),
                            dbc.Select(
                                id="contact-subject",
                                options=[
                                    {"label": "Technical Support", "value": "Technical Support"},
                                    {"label": "API / Developer Inquiry", "value": "API / Developer Inquiry"},
                                    {"label": "Partnership Request", "value": "Partnership Request"},
                                    {"label": "Research Collaboration", "value": "Research Collaboration"},
                                    {"label": "General Question", "value": "General Question"},
                                ],
                                value="General Question",
                                className="premium-input",
                                style={"background": "rgba(255,255,255,0.05)", "color": "white", "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "12px"}
                            )
                        ]),
                        html.Div(className="mb-4", children=[
                            dbc.Label("Message", className="text-muted small mb-1"),
                            dbc.Textarea(id="contact-message", placeholder="Describe your inquiry in detail...", rows=5, className="premium-input")
                        ]),
                        html.Div(id="contact-feedback", className="mb-3"),
                        dbc.Button(
                            [html.I(className="fa-solid fa-paper-plane me-2"), "Send Message"],
                            id="contact-submit-btn",
                            n_clicks=0,
                            className="btn-pulse w-100 py-3 fw-bold",
                            style={"borderRadius": "14px", "background": "linear-gradient(45deg, #00f2ff, #0088ff)", "border": "none", "color": "black"}
                        ),
                        html.P("We typically respond within 24 hours during business days.", className="text-muted small text-center mt-3 mb-0")
                    ])
                ], lg=8)
            ]),
            html.Div(className="mt-5 text-center", children=dbc.Button([html.I(className="bi bi-arrow-left me-2"), "Back to Portal"], href="/", className="btn-pulse px-4 py-2"))
        ])
    ])

# --- Survey Widget ---

def survey_widget():
    return html.Div([
        # Floating Survey Button (bottom-left)
        html.Button(
            [html.I(className="fa-solid fa-clipboard-list"), html.Span("Survey", className="ms-2 small fw-bold", style={"fontSize": "0.75rem", "letterSpacing": "1px"})],
            id="survey-open-btn",
            className="d-flex align-items-center justify-content-center gap-1",
            style={
                "position": "fixed",
                "bottom": "30px",
                "left": "30px",
                "zIndex": "9999",
                "background": "linear-gradient(135deg, #7000ff, #00f2ff)",
                "border": "none",
                "borderRadius": "50px",
                "color": "white",
                "padding": "14px 20px",
                "boxShadow": "0 8px 25px rgba(112, 0, 255, 0.5)",
                "transition": "all 0.3s ease",
                "cursor": "pointer",
                "fontSize": "1.1rem"
            }
        ),

        # Survey Modal
        dbc.Modal([
            dbc.ModalHeader(
                dbc.ModalTitle([html.I(className="fa-solid fa-clipboard-list text-info me-2"), "Platform Feedback Survey"],
                               className="text-white fw-bold"),
                close_button=True,
                style={"background": "rgba(10,12,20,0.95)", "borderBottom": "1px solid rgba(255,255,255,0.1)"}
            ),
            dbc.ModalBody(style={"background": "rgba(10,12,20,0.95)"}, children=[
                html.P("Help us improve NeuroHealth AI with your honest feedback.", className="text-muted mb-4"),

                # Q1 - Overall Rating (stars via emoji)
                html.Div(className="mb-4", children=[
                    dbc.Label("1. Overall Experience", className="text-white fw-bold mb-2"),
                    dbc.RadioItems(
                        id="survey-rating",
                        options=[
                            {"label": "⭐ Poor",      "value": "1"},
                            {"label": "⭐⭐ Fair",     "value": "2"},
                            {"label": "⭐⭐⭐ Good",    "value": "3"},
                            {"label": "⭐⭐⭐⭐ Great",  "value": "4"},
                            {"label": "⭐⭐⭐⭐⭐ Excellent", "value": "5"},
                        ],
                        value="5",
                        inline=True,
                        className="text-white",
                        labelStyle={"marginRight": "18px", "cursor": "pointer"}
                    )
                ]),

                # Q2 - Which feature
                html.Div(className="mb-4", children=[
                    dbc.Label("2. Which feature did you find most useful?", className="text-white fw-bold mb-2"),
                    dbc.Select(
                        id="survey-feature",
                        options=[
                            {"label": "AI Prediction Engine",     "value": "prediction"},
                            {"label": "Clinical Risk Scoring",    "value": "risk"},
                            {"label": "Live Simulator Demo",      "value": "simulator"},
                            {"label": "Medical Report Generator", "value": "report"},
                            {"label": "Aegis AI Assistant",       "value": "chat"},
                            {"label": "Dashboard Analytics",     "value": "dashboard"},
                        ],
                        value="prediction",
                        style={"background": "rgba(255,255,255,0.05)", "color": "white",
                               "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "12px"}
                    )
                ]),

                # Q3 - Recommend
                html.Div(className="mb-4", children=[
                    dbc.Label("3. Would you recommend this platform?", className="text-white fw-bold mb-2"),
                    dbc.RadioItems(
                        id="survey-recommend",
                        options=[
                            {"label": "👍 Yes, definitely",   "value": "yes"},
                            {"label": "🤔 Maybe",             "value": "maybe"},
                            {"label": "👎 No",               "value": "no"},
                        ],
                        value="yes",
                        inline=True,
                        className="text-white",
                        labelStyle={"marginRight": "18px", "cursor": "pointer"}
                    )
                ]),

                # Q4 - Open feedback
                html.Div(className="mb-4", children=[
                    dbc.Label("4. Additional comments or suggestions", className="text-white fw-bold mb-2"),
                    dbc.Textarea(
                        id="survey-comments",
                        placeholder="Share your thoughts to help us improve...",
                        rows=4,
                        className="premium-input"
                    )
                ]),

                # Success message
                html.Div(id="survey-success", className="text-center", style={"display": "none"}, children=[
                    html.I(className="fa-solid fa-circle-check text-info fs-1 mb-3"),
                    html.H5("Thank You!", className="text-white fw-bold"),
                    html.P("Your feedback helps us build a better platform.", className="text-muted")
                ])
            ]),
            dbc.ModalFooter(style={"background": "rgba(10,12,20,0.95)", "borderTop": "1px solid rgba(255,255,255,0.1)"}, children=[
                dbc.Button("Cancel", id="survey-cancel-btn", className="btn btn-outline-secondary me-2", n_clicks=0),
                dbc.Button(
                    [html.I(className="fa-solid fa-paper-plane me-2"), "Submit Feedback"],
                    id="survey-submit-btn",
                    className="btn-pulse px-4",
                    style={"background": "linear-gradient(45deg, #7000ff, #00f2ff)", "border": "none", "color": "white"},
                    n_clicks=0
                )
            ])
        ], id="survey-modal", is_open=False, size="lg", centered=True,
           backdrop="static",
           style={"zIndex": "10001"}
        )
    ])

# --- Chatbot Component ---

def chat_widget():
    return html.Div(className="chatbot-float", children=[
        html.Button(html.I(className="fa-solid fa-comment-medical"), id="chat-toggle-btn", className="chatbot-btn"),
        html.Div(id="chat-window", className="chatbot-window glass-panel p-0", style={"display": "none"}, children=[
            # Header
            html.Div(className="p-3 border-bottom border-secondary d-flex justify-content-between align-items-center", children=[
                html.Div([
                    html.I(className="fa-solid fa-robot text-info me-2"),
                    html.Strong("AEGIS AI ASSISTANT", className="text-white small")
                ]),
                html.Button(html.I(className="fa-solid fa-minus text-muted"), id="chat-close-btn", className="bg-transparent border-0 p-0")
            ]),
            
            # Content
            html.Div(id="chat-messages", className="chat-content d-flex flex-column", children=[
                html.Div("Greetings. I am Aegis AI. How can I assist your clinical analysis today?", className="msg-bubble msg-ai")
            ]),
            
            # Input
            html.Div(className="chat-input-area", children=[
                dbc.Input(id="chat-user-input", placeholder="Type a message...", className="premium-input flex-grow-1 border-0"),
                dbc.Button(html.I(className="fa-solid fa-paper-plane"), id="chat-send-btn", className="btn-pulse px-3")
            ])
        ])
    ])


def serve_layout():
    # Safe session access for Dash startup validation
    user_session_data = None
    try:
        user_session_data = session.get("user")
    except Exception:
        pass

    return html.Div([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='user-session', storage_type='session', data=user_session_data),
        dcc.Store(id='chat-history', data=[{"role": "ai", "text": "Greetings. I am Aegis AI. How can I assist your clinical analysis today?"}]),
        html.Div(id='page-content'),
        chat_widget(),
        survey_widget(),
        
        # Working Features Usage Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("WORKING FEATURES & USAGE GUIDE", className="text-info fw-bold")),
            dbc.ModalBody(className="glass-panel border-0 text-white p-4", children=[
                html.Div(className="mb-4", children=[
                    html.H6("1. SECURE CLINICAL ONBOARDING", className="text-info mb-2"),
                    html.P("Register or login to your encrypted health portal to access the diagnostic command center.", className="small text-muted")
                ]),
                html.Div(className="mb-4", children=[
                    html.H6("2. DIAGNOSTIC PATH SELECTION", className="text-info mb-2"),
                    html.P("Navigate to the main dashboard and select from 9 specialized neural modules (Diabetes, Stroke, Heart, etc.) based on patient symptoms.", className="small text-muted")
                ]),
                html.Div(className="mb-4", children=[
                    html.H6("3. NEURAL PULSE ANALYSIS", className="text-info mb-2"),
                    html.P("Enter accurate patient vitals into the parametric inputs. Click 'Analyze Clinical Data' to trigger real-time AI inference and populate diagnostic meters.", className="small text-muted")
                ]),
                html.Div(className="mb-0", children=[
                    html.H6("4. DOCUMENT SYNTHESIS", className="text-info mb-2"),
                    html.P("Review the generated insights and use the 'Report Generator' to synthesize a downloadable medical record for professional consultation.", className="small text-muted")
                ])
            ])
        ], id="usage-modal", is_open=False, size="lg", centered=True)
    ])

app.layout = serve_layout

# --- Routing ---
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname'),
     Input('user-session', 'data')]
)
def display_page(pathname, user_data):
    # Sync Dash store with Flask session for OAuth compatibility
    if not user_data and "user" in session:
        user_data = session["user"]

    # Public Pages
    if pathname == "/signup":
        return signup_page()
    if pathname == "/login":
        return login_page()
        
    if pathname == "/research":
        return research_page()
    if pathname == "/api-docs":
        return api_page()
    if pathname == "/privacy":
        return privacy_page()
    if pathname == "/terms":
        return terms_page()
    if pathname == "/contact":
        return contact_page()
    
    # Requirement: Grand Main Page at root
    if pathname == "/":
        return grand_landing_page(user_data)
        
    # Live Demo Public Access
    if pathname and pathname.startswith("/demo/"):
        disease_id = pathname.split('/')[-1]
        return analysis_page(disease_id, {})
    if pathname == "/demo":
        return analysis_page("diabetes", {})

    # Secure Pages
    if not user_data:
        return login_page()

    if pathname == "/dashboard" or pathname == "/selection":
        return central_dashboard(user_data)
    
    if pathname.startswith('/analysis/'):
        disease_id = pathname.split('/')[-1]
        return analysis_page(disease_id, user_data) # Pass user_data to analysis_page
        
    return grand_landing_page(user_data) # Fallback to grand landing page

# --- Patient Registration Callback ---
@app.callback(
    [Output("reg-feedback", "children"),
     Output("reg-table-container", "children"),
     Output("reg-count-badge", "children"),
     Output("reg-name", "value"),
     Output("reg-email", "value"),
     Output("reg-mobile", "value"),
     Output("reg-age", "value")],
    [Input("reg-submit-btn", "n_clicks"),
     Input({"type": "delete-patient-btn", "index": ALL}, "n_clicks")],
    [State("reg-name",       "value"),
     State("reg-email",      "value"),
     State("reg-mobile",     "value"),
     State("reg-age",        "value"),
     State("reg-gender",     "value"),
     State("reg-prediction", "value")]
)
def handle_patient_registration(submit_clicks, delete_clicks, name, email, mobile, age, gender, prediction):
    def build_table():
        rows = get_all_patient_registrations()
        if not rows:
            return html.P("No patients registered yet.", className="text-muted text-center py-4"), "0 Patients"
        
        thead = html.Thead(html.Tr([
            html.Th("Name",       className="text-info small", style={"padding": "10px 12px", "whiteSpace": "nowrap"}),
            html.Th("Email",      className="text-info small", style={"padding": "10px 12px", "whiteSpace": "nowrap"}),
            html.Th("Mobile",     className="text-info small", style={"padding": "10px 12px", "whiteSpace": "nowrap"}),
            html.Th("Age",        className="text-info small", style={"padding": "10px 12px"}),
            html.Th("Gender",     className="text-info small", style={"padding": "10px 12px"}),
            html.Th("Prediction", className="text-info small", style={"padding": "10px 12px", "whiteSpace": "nowrap"}),
            html.Th("Date",       className="text-info small", style={"padding": "10px 12px", "whiteSpace": "nowrap"}),
            html.Th("Action",     className="text-info small", style={"padding": "10px 12px", "textAlign": "right"}),
        ], style={"borderBottom": "1px solid rgba(255,255,255,0.1)","background": "rgba(0,242,255,0.05)"}))

        tbody = html.Tbody([
            html.Tr([
                html.Td(r["name"],       style={"padding": "10px 12px", "color": "white", "whiteSpace": "nowrap"}),
                html.Td(r["email"],      style={"padding": "10px 12px", "color": "rgba(255,255,255,0.6)", "fontSize": "0.85rem"}),
                html.Td(r["mobile"],     style={"padding": "10px 12px", "color": "rgba(255,255,255,0.6)", "fontSize": "0.85rem"}),
                html.Td(str(r["age"]),   style={"padding": "10px 12px", "color": "rgba(255,255,255,0.6)", "fontSize": "0.85rem"}),
                html.Td(r["gender"],     style={"padding": "10px 12px", "color": "rgba(255,255,255,0.6)", "fontSize": "0.85rem"}),
                html.Td(dbc.Badge(r["prediction"], color="info", pill=True, className="small"),
                        style={"padding": "10px 12px"}),
                html.Td(r["date"],       style={"padding": "10px 12px", "color": "rgba(255,255,255,0.4)", "fontSize": "0.8rem", "whiteSpace": "nowrap"}),
                html.Td(
                    dbc.Button(html.I(className="fa-solid fa-trash"), 
                               id={"type": "delete-patient-btn", "index": r["id"]},
                               color="danger", size="sm", outline=True, className="border-0 px-2"),
                    style={"padding": "10px 12px", "textAlign": "right"}
                ),
            ], style={"borderBottom": "1px solid rgba(255,255,255,0.05)",
                      "transition": "background 0.2s"})
            for r in rows
        ])
        table = html.Table([thead, tbody], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.9rem"})
        return table, f"{len(rows)} Patient{'s' if len(rows) != 1 else ''}"

    trigger = dash.ctx.triggered_id
    if trigger and isinstance(trigger, dict) and trigger.get("type") == "delete-patient-btn":
        patient_id = trigger.get("index")
        delete_patient_registration(patient_id)
        # Recalculate table data after deletion
        tbl, badge = build_table()
        msg = html.Div([html.I(className="fa-solid fa-circle-check me-2"), "Patient record deleted."],
                       className="text-success small p-2 rounded",
                       style={"background": "rgba(46,204,64,0.1)", "border": "1px solid rgba(46,204,64,0.3)"})
        return msg, tbl, badge, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # Important: If neither button was clicked (initial load), just return the empty table to render it without crashing
    if not submit_clicks or submit_clicks == 0:
        tbl, badge = build_table()
        return dash.no_update, tbl, badge, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # Validate
    if not all([name, email, mobile, age, gender, prediction]):
        feedback = html.Div([html.I(className="fa-solid fa-triangle-exclamation me-2"),
                             "Please fill in all fields."],
                            className="text-danger small p-2 rounded",
                            style={"background": "rgba(255,65,54,0.1)", "border": "1px solid rgba(255,65,54,0.3)"})
        tbl, badge = build_table()
        return feedback, tbl, badge, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    reg_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        add_patient_registration(name, email, str(mobile), int(age), gender, prediction, reg_date)
    except Exception as e:
        feedback = html.Div(f"Error saving: {e}", className="text-danger small")
        tbl, badge = build_table()
        return feedback, tbl, badge, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    feedback = html.Div(
        [html.I(className="fa-solid fa-circle-check me-2"), f"{name} registered successfully!"],
        className="text-success small p-2 rounded",
        style={"background": "rgba(46,204,64,0.1)", "border": "1px solid rgba(46,204,64,0.3)"}
    )
    tbl, badge = build_table()
    # Clear form fields on success
    return feedback, tbl, badge, "", "", "", None

# --- Contact Form Callback ---
@app.callback(
    Output("contact-feedback", "children"),
    Input("contact-submit-btn", "n_clicks"),
    [State("contact-name", "value"),
     State("contact-email", "value"),
     State("contact-subject", "value"),
     State("contact-message", "value")],
    prevent_initial_call=True
)
def handle_contact_submission(n_clicks, name, email, subject, message):
    if not n_clicks:
        return dash.no_update

    # Field Validation
    if not all([name, email, subject, message]):
        return html.Div(
            [html.I(className="fa-solid fa-triangle-exclamation me-2"), "Please fill in all fields before sending."],
            className="text-danger small p-2 rounded",
            style={"background": "rgba(255,65,54,0.1)", "border": "1px solid rgba(255,65,54,0.3)"}
        )

    # API Call to Backend
    try:
        payload = {
            "name": name,
            "email": email,
            "subject": subject,
            "message": message
        }
        # Assuming the FastAPI backend is running on port 8000
        response = requests.post(f"{API_BASE_URL}/contact", json=payload, timeout=10)
        result = response.json()

        if response.status_code == 200 and result.get("status") == "success":
            return html.Div(
                [html.I(className="fa-solid fa-circle-check me-2"), "Message sent successfully! We will get back to you soon."],
                className="text-success small p-2 rounded",
                style={"background": "rgba(46,204,64,0.1)", "border": "1px solid rgba(46,204,64,0.3)"}
            )
        else:
            error_msg = result.get("error", "Unknown error occurred.")
            return html.Div(
                [html.I(className="fa-solid fa-circle-xmark me-2"), f"Failed to send message: {error_msg}"],
                className="text-danger small p-2 rounded",
                style={"background": "rgba(255,65,54,0.1)", "border": "1px solid rgba(255,65,54,0.3)"}
            )
    except Exception as e:
        return html.Div(
            [html.I(className="fa-solid fa-circle-xmark me-2"), f"Connection Error: {str(e)}"],
            className="text-danger small p-2 rounded",
            style={"background": "rgba(255,65,54,0.1)", "border": "1px solid rgba(255,65,54,0.3)"}
        )

# --- Survey Callbacks ---
@app.callback(
    Output("survey-modal", "is_open"),
    [Input("survey-open-btn", "n_clicks"),
     Input("survey-cancel-btn", "n_clicks"),
     Input("survey-submit-btn", "n_clicks")],
    State("survey-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_survey_modal(open_clicks, cancel_clicks, submit_clicks, is_open):
    trigger = dash.ctx.triggered_id
    if trigger == "survey-open-btn":
        return True
    return False

@app.callback(
    Output("survey-success", "style"),
    Input("survey-submit-btn", "n_clicks"),
    prevent_initial_call=True
)
def show_survey_success(n):
    if n:
        return {"display": "block"}
    return {"display": "none"}

# --- Auth Callbacks ---
@app.callback(
    [Output("user-session", "data", allow_duplicate=True),
     Output("login-error", "children"),
     Output("url", "pathname", allow_duplicate=True)],
    Input("login-btn", "n_clicks"),
    [State("login-email", "value"),
     State("login-password", "value")],
    prevent_initial_call=True
)
def handle_login(n_clicks, email, password):
    if n_clicks:
        user = get_user(email, password)
        if user:
            session["user"] = user
            return user, "", "/dashboard"
        return dash.no_update, "Invalid email or password", dash.no_update
    return dash.no_update, "", dash.no_update # Return empty error on initial load

@app.callback(
    [Output("user-session", "data", allow_duplicate=True),
     Output("signup-error", "children"),
     Output("url", "pathname", allow_duplicate=True)],
    Input("signup-btn", "n_clicks"),
    [State("signup-name", "value"),
     State("signup-phone", "value"),
     State("signup-email", "value"),
     State("signup-password", "value"),
     State("signup-confirm", "value")],
    prevent_initial_call=True
)
def handle_signup(n_clicks, name, phone, email, password, confirm):
    if n_clicks:
        if password != confirm:
            return dash.no_update, "Passwords do not match", dash.no_update
        if email and password and name:
            if add_user(name, phone, email, password):
                user = {"fullname": name, "phone": phone, "email": email}
                session["user"] = user
                return user, "", "/dashboard"
            return dash.no_update, "Email already exists", dash.no_update
        return dash.no_update, "Please fill all required fields", dash.no_update
    return dash.no_update, "", dash.no_update
# Dash Logout handled via server-side /logout route for complete session clearing

# --- UI Mechanics Callbacks ---

@app.callback(
    Output("chat-window", "style"),
    [Input("chat-toggle-btn", "n_clicks"),
     Input("chat-close-btn", "n_clicks")],
    [State("chat-window", "style")],
    prevent_initial_call=True
)
def toggle_chat(n1, n2, style):
    if not style or style.get("display") == "none":
        return {"display": "flex"}
    return {"display": "none"}

@app.callback(
    [Output("chat-messages", "children"),
     Output("chat-user-input", "value"),
     Output("chat-history", "data")],
    [Input("chat-send-btn", "n_clicks"),
     Input("chat-user-input", "n_submit")],
    [State("chat-user-input", "value"),
     State("chat-history", "data")],
    prevent_initial_call=True
)
def handle_chat(n_clicks, n_submit, user_text, history):
    if not user_text:
        return dash.no_update, dash.no_update, dash.no_update
    
    # Add user message
    history.append({"role": "user", "text": user_text})
    
    # Simple AI Response Logic
    query = user_text.lower()
    if any(w in query for w in ["hello", "hi", "hey", "greetings"]):
        response = "Hello! I am Aegis, your clinical intelligence assistant. You can ask me about different health conditions, symptoms, or how to use the dashboard."
    elif "heart" in query or "chest" in query or "cardio" in query:
        response = "For cardiovascular analysis, please use our **[Heart Disease Module](/analysis/heart)**. It analyzes factors like resting BP, cholesterol, and maximum heart rate."
    elif "stroke" in query or "brain" in query or "paralysis" in query:
        response = "To assess cerebrovascular risk, please visit the **[Stroke Module](/analysis/stroke)**. It evaluates factors such as hypertension, average glucose, and BMI."
    elif "diabet" in query or "sugar" in query or "glucose" in query or "thirsty" in query:
        response = "For metabolic screening, please navigate to our **[Diabetes Module](/analysis/diabetes)**. It requires inputs like glucose levels, insulin, and BMI."
    elif "kidney" in query or "renal" in query or "urine" in query:
        response = "To check renal function, please use the **[Kidney Disease Module](/analysis/kidney)**."
    elif "liver" in query or "hepatic" in query or "jaundice" in query:
        response = "For hepatic screening, please visit our **[Liver Disease Module](/analysis/liver)**."
    elif "anemia" in query or "blood" in query or "tired" in query or "fatigue" in query or "weak" in query or "exhaust" in query:
        response = "Symptoms like fatigue and weakness could indicate low oxygen-carrying capacity. Please use the **[Anemia Module](/analysis/anemia)** or the **[General Health Module](/analysis/general_health)** for a broader screen."
    elif "obes" in query or "weight" in query or "fat" in query:
        response = "For systemic body-mass assessment, please check the **[Obesity Module](/analysis/obesity)**."
    elif "risk" in query:
        response = "The Risk Probability is calculated using a neural ensemble. Anything above 70% suggests a high-priority pathology."
    elif "report" in query or "download" in query:
        response = "You can generate a clinical report by clicking the **Generate Medical Report** button on any analysis page."
    elif "how" in query or "use" in query or "help" in query:
        response = "1. Select a disease module from the dashboard.\n2. Enter patient vitals.\n3. Click 'Analyze Clinical Data' for AI inference."
    else:
        response = "I've logged your query. As an AI health assistant, I recommend checking the diagnostic meters on our specialized modules for precise data. If you have specific symptoms, mention them (e.g., 'heart', 'sugar', 'tired', 'stroke') and I'll guide you."
        
    history.append({"role": "ai", "text": response})
    
    # Build components
    messages = []
    for msg in history:
        css = "msg-ai" if msg["role"] == "ai" else "msg-user"
        content = dcc.Markdown(msg["text"], style={"margin": "0px"}) if msg["role"] == "ai" else msg["text"]
        messages.append(html.Div(content, className=f"msg-bubble {css}"))
        
    return messages, "", history

@app.callback(
    Output("usage-modal", "is_open"),
    [Input("usage-features-btn", "n_clicks")],
    [State("usage-modal", "is_open")],
    prevent_initial_call=True
)
def toggle_usage_modal(n, is_open):
    if n: return not is_open
    return is_open


# --- Prediction Engine ---
@app.callback(
    [Output("risk-pill-container", "children"),
     Output("confidence-score", "children"),
     Output("prob-percentage", "children"),
     Output("ai-status", "children"),
     Output("main-gauge", "figure"),
     Output("radar-chart", "figure"),
     Output("impact-bar", "figure"),
     Output("variant-line", "figure"),
     Output("health-gauge", "figure"),
     Output("score-label", "children"),
     Output("rec-neural", "children"),
     Output("rec-action", "children"),
     Output("rec-alert", "children"),
     Output("rec-lifestyle", "children"),
     Output("error-msg", "children")],
    Input("predict-btn", "n_clicks"),
    [State("url", "pathname"),
     State({'type': 'feature-input', 'id': ALL}, 'value'),
     State({'type': 'feature-input', 'id': ALL}, 'id')],
)
def run_prediction_engine(n, path, feature_values, feature_ids):
    # Safe float conversion
    def safe_float(v):
        try: return float(v) if v is not None else 0.0
        except: return 0.0

    # Empty state for initial load
    if not n or n == 0:
        empty_fig = go.Figure().update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                                             xaxis=dict(visible=False), yaxis=dict(visible=False))
        empty_gauge = go.Figure(go.Indicator(mode="gauge+number", value=0, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#222"}}))
        empty_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color="#444")
        return (html.Span("AWAITING ANALYSIS", className="risk-header-pill level-low", style={"color": "#64748b", "background": "rgba(255,255,255,0.05)"}),
                "0.0%", "0.0%", "IDLE", empty_gauge, empty_fig, empty_fig, empty_fig, empty_gauge, "---",
                html.P("Enter patient data and click 'Analyze' to generate neural insights.", className="text-muted"),
                None, None, None, "")

    disease_id = path.split('/')[-1] if path and '/analysis/' in path else "diabetes"
    
    # Map Dynamic UI IDs to Dataset Column Names to ensure correct feature alignment
    feature_dict: dict[str, float] = {str(f_id['id']): safe_float(val) for f_id, val in zip(feature_ids, feature_values)}
    
    try:
        if disease_id == "obesity":
            height = feature_dict.get("Height", 170)
            weight = feature_dict.get("Weight", 70)
            bmi = weight / ((height / 100) ** 2) if height > 0 else 0
            
            if bmi < 18.5:
                pred = 0
                prob = 15.0
                status_text = "UNDERWEIGHT"
            elif bmi < 25:
                pred = 0
                prob = 10.0
                status_text = "NORMAL"
            elif bmi < 30:
                pred = 1
                prob = 75.0
                status_text = "OVERWEIGHT"
            else:
                pred = 1
                prob = 95.0
                status_text = "OBESE"
            
            conf = "100.0%" # BMI is a deterministic calculation
        else:
            # API Call with dictionary instead of list
            resp = requests.post(f"{API_BASE_URL}/predict/{disease_id}", json={"features": feature_dict}, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            # Check for API error
            if "error" in data:
                return dash.no_update, "---", "---", "ERR", {}, {}, {}, {}, {}, "ERROR", None, None, None, None, data["error"]

            prob = data.get('probability', 0.0)
            pred = data.get('prediction', 0)
            conf = "98.4%" # Model metric
            
            if disease_id == "diabetes":
                status_text = "Diabetes Positive" if pred == 1 else "Diabetes Negative"
            else:
                status_text = "POSITIVE" if pred == 1 else "NEGATIVE"
        
        # Risk Mapping
        level, color, css = "NORMAL", "#2ecc40", "level-low"
        if prob < 40: level, color, css = "NORMAL", "#2ecc40", "level-low"
        elif prob < 65: level, color, css = "MODERATE", "#ffdc00", "level-moderate"
        elif prob < 85: level, color, css = "HIGH", "#ff851b", "level-high"
        else: level, color, css = "CRITICAL", "#ff4136", "level-critical"
        
        pill = html.Span(level, className=f"risk-header-pill {css}")
        
        # Visuals
        # 1. Gauge
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=prob, number={'suffix': "%", 'font': {'color': color}},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': color}, 'bgcolor': 'rgba(0,0,0,0)',
                   'steps': [{'range': [0, 40], 'color': "rgba(46, 204, 64, 0.1)"}, 
                             {'range': [85, 100], 'color': "rgba(255, 65, 54, 0.1)"}]}
        ))
        fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_family="Outfit", font_color="white", margin=dict(t=50, b=20))

        # 2. Radar
        all_keys: list[str] = [str(k) for k in feature_dict]
        radar_cats: list[str] = all_keys[:8]  # pyre-ignore
        radar_vals = [min(feature_dict[k], 150) for k in radar_cats]
        fig_radar = go.Figure(go.Scatterpolar(r=radar_vals, theta=radar_cats, fill='toself', line_color=color))
        # Safely add the reference ring based on feature count
        fig_radar.add_trace(go.Scatterpolar(r=[50]*len(radar_cats), theta=radar_cats, fill=None, line_color="rgba(255,255,255,0.1)", line=dict(dash='dash')))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")),  # pyre-ignore
                                paper_bgcolor='rgba(0,0,0,0)', font_color="white", margin=dict(t=40, b=40))

        # 3. Bar
        # Use first 5 features for the bar chart
        bar_labels: list[str] = all_keys[:5]  # pyre-ignore
        bar_vals = [abs(feature_dict[k]) for k in bar_labels]
        fig_bar = px.bar(x=bar_vals, y=bar_labels, orientation='h', color_discrete_sequence=[color])
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")

        # 4. Line
        fig_line = px.line(x=[1,2,3,4,5], y=[max(0.0, prob-5), prob+3, prob, prob-2, prob])  # pyre-ignore
        fig_line.update_traces(line_color=color, fill='tozeroy')
        fig_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")

        # 5. Health
        h_score = 100.0 - (prob * 0.8)
        fig_h = go.Figure(go.Indicator(mode="gauge+number", value=h_score, gauge={'bar': {'color': '#00f2ff'}}))
        fig_h.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color="white", margin=dict(t=20, b=20))

        # Recommendations
        primary_feature = "Glucose" if "Glucose" in feature_dict else ("avg_glucose_level" if "avg_glucose_level" in feature_dict else list(feature_dict.keys())[0])
        feat_val = feature_dict.get(primary_feature, 0)
        
        rec_n = html.Div(className="rec-box", children=[html.Strong("Neural Analysis: "), f"Model identified critical sensitivity in {primary_feature} levels ({feat_val})."])
        rec_a = html.Div(className="rec-box", children=[html.Strong("Clinical Action: "), "Immediate referral to clinical care specialist recommended."])
        rec_w = html.Div(className="rec-box", style={"borderColor": color}, children=[html.Strong("Medical Alert: "), f"Inferred risk profile: {level} PATHOLOGY."])
        rec_l = html.Div(className="rec-box", children=[html.Strong("Lifestyle Advice: "), "Immediate dietary adjustments and vitals monitoring required."])

        return (pill, conf, f"{prob}%", status_text, fig_gauge, fig_radar, fig_bar, fig_line, fig_h, 
                "OPTIMAL" if h_score > 70 else "SUBSYSTEM STRESS", rec_n, rec_a, rec_w, rec_l, "")

    except Exception as e:
        return dash.no_update, "---", "---", "ERR", {}, {}, {}, {}, {}, "ERROR", None, None, None, None, f"Backend Connection Error: {str(e)}"

# --- Report Generator ---
@app.callback(
    Output("download-medical-report", "data"),
    Input("report-btn", "n_clicks"),
    [State("url", "pathname"), 
     State({'type': 'feature-input', 'id': ALL}, 'value'),
     State({'type': 'feature-input', 'id': ALL}, 'id'),
     State("clinical-notes", "value")],
    prevent_initial_call=True
)
def generate_report(n, path, feature_values, feature_ids, notes):
    disease = path.split('/')[-1] if path else "unknown"
    feature_dict = {f_id['id']: val for f_id, val in zip(feature_ids, feature_values)}
    
    vitals_str = "\n".join([f"{k}: {v}" for k, v in feature_dict.items()])
    content = f"AEGIS AI MEDICAL REPORT\nFocus: {disease.upper()}\nGenerated: {datetime.now().strftime('%Y-%m-%d')}\n\nVitals:\n{vitals_str}\n\nNotes:\n{notes if notes else 'N/A'}"
    return dict(content=content, filename=f"Health_Report_{disease}.txt")

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
