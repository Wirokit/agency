import os
from app import create_app
from config import getConfig

if __name__ == "__main__":
    # Run the app.
    # 'debug=True' is great for development as it auto-reloads.
    application = create_app(config=getConfig())
    application.run(debug=os.environ.get("DEBUG_MODE") == "TRUE", host="0.0.0.0")
