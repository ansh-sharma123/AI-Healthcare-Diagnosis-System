import os
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import pickle
from sklearn.model_selection import train_test_split  # type: ignore
from sklearn.preprocessing import StandardScaler  # type: ignore
from sklearn.pipeline import Pipeline  # type: ignore
from sklearn.linear_model import LogisticRegression  # type: ignore
from sklearn.ensemble import RandomForestRegressor  # type: ignore
from sklearn.metrics import accuracy_score, recall_score, mean_squared_error  # type: ignore

print("Diabetes pipeline started...")

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
df = pd.read_csv(os.path.join(BASE_DIR, "diabetes.csv"))

print("Dataset loaded:", df.shape)

X = df.drop("Outcome", axis=1)
y_class = df["Outcome"]
# Note: Training a regressor on binary targets (0/1) causes convergence to the mean.
# In a real scenario, y_reg should be a continuous risk score (e.g., 0-100).
# Since we only have binary labels, we will use the classifier's probability 
# as the primary risk indicator in the API instead.
y_reg = df["Outcome"].astype(float) 

X_train, X_test, y_class_train, y_class_test, y_reg_train, y_reg_test = train_test_split(
    X, y_class, y_reg, test_size=0.2, random_state=42
)

classifier_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(max_iter=1000, class_weight='balanced'))
])

classifier_pipeline.fit(X_train, y_class_train)

class_preds = classifier_pipeline.predict(X_test)
accuracy = accuracy_score(y_class_test, class_preds)
recall = recall_score(y_class_test, class_preds)

print("Classification Accuracy:", accuracy)
print("Classification Recall:", recall)

# If a Regressor is truly needed, it should be trained on a continuous metric.
# For now, we fix the Random Forest hyperparameters to prevent over-smoothing.
regressor_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42))
])

regressor_pipeline.fit(X_train, y_reg_train)

reg_preds = regressor_pipeline.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_reg_test, reg_preds))

print("Regression RMSE:", rmse)


MODELS_DIR = os.path.join(BASE_DIR, "..", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

with open(os.path.join(MODELS_DIR, "diabetes_classifier.pkl"), "wb") as f:
    pickle.dump(classifier_pipeline, f)

with open(os.path.join(MODELS_DIR, "diabetes_regressor.pkl"), "wb") as f:
    pickle.dump(regressor_pipeline, f)

print("Models saved successfully.")
