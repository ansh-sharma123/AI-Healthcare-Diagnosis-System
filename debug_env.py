import os
from dotenv import load_dotenv  # type: ignore

project_root = r"c:\Users\ashuk\OneDrive\Desktop\Fullml"
dotenv_path = os.path.join(project_root, ".env")

print(f"Checking path: {dotenv_path}")
print(f"File exists: {os.path.exists(dotenv_path)}")

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID')}")
    print(f"GOOGLE_CLIENT_SECRET: {os.getenv('GOOGLE_CLIENT_SECRET')}")
    print(f"FLASK_SECRET_KEY: {os.getenv('FLASK_SECRET_KEY')}")
else:
    print("DOTENV NOT FOUND")
