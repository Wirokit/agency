import os
from app import create_app

# --- Environment - Only needed when running locally ---
""" from dotenv import load_dotenv

load_dotenv() """
# ---

if __name__ == "__main__":
    # Run the app.
    # 'debug=True' is great for development as it auto-reloads.
    application = create_app()
    application.run(debug=os.environ.get("DEBUG_MODE") == "TRUE", host="0.0.0.0")
