import os
import sys

# Add root folder to sys.path to enable relative imports to function correctly
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import the dash app and expose its server for Gunicorn
from dashboard.app import server

if __name__ == "__main__":
    from dashboard.app import app
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
