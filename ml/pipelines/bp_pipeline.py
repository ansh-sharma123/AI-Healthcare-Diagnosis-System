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

print("BP pipeline started...")

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
df = pd.read_csv(os.path.join(BASE_DIR, "bp.csv"))

print("Dataset loaded:", df.shape)

X = df.drop("label", axis=1)
y_class = df["label"]
y_reg = df["label"]

X_train, X_test, y_class_train, y_class_test, y_reg_train, y_reg_test = train_test_split(
    X, y_class, y_reg, test_size=0.2, random_state=42
)

classifier_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(max_iter=1000))
])

classifier_pipeline.fit(X_train, y_class_train)

class_preds = classifier_pipeline.predict(X_test)

print("Accuracy:", accuracy_score(y_class_test, class_preds))
print("Recall:", recall_score(y_class_test, class_preds))

regressor_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", RandomForestRegressor())
])

regressor_pipeline.fit(X_train, y_reg_train)

reg_preds = regressor_pipeline.predict(X_test)

rmse = np.sqrt(mean_squared_error(y_reg_test, reg_preds))

print("RMSE:", rmse)

MODELS_DIR = os.path.join(BASE_DIR, "..", "models")

pickle.dump(classifier_pipeline, open(os.path.join(MODELS_DIR, "bp_classifier.pkl"), "wb"))
pickle.dump(regressor_pipeline, open(os.path.join(MODELS_DIR, "bp_regressor.pkl"), "wb"))

print("Models saved successfully.")