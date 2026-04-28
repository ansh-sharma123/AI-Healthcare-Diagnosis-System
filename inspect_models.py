import pickle
import os

MODEL_PATHS = {
    "diabetes": "diabetes_classifier.pkl",
    "heart": "heart_classifier.pkl",
    "liver": "liver_classifier.pkl",
    "kidney": "kidney_classifier.pkl",
    "stroke": "stroke_classifier.pkl",
    "anemia": "anemia_classifier.pkl",
    "obesity": "obesity_classifier.pkl",
}

from typing import Any

results: dict[str, Any] = {}
BASE_DIR = os.path.join("ml", "models")

for key, filename in MODEL_PATHS.items():
    path = os.path.join(BASE_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                model = pickle.load(f)
                if hasattr(model, 'feature_names_in_'):
                    results[key] = list(model.feature_names_in_)
                elif hasattr(model, 'named_steps') and 'scaler' in model.named_steps and hasattr(model.named_steps['scaler'], 'feature_names_in_'):
                     results[key] = list(model.named_steps['scaler'].feature_names_in_)
                else:
                    results[key] = "No feature names found"
        except Exception as e:
            results[key] = f"Error: {str(e)}"
    else:
        results[key] = "File not found"

for k, v in results.items():
    print(f"{k}: {v}")
