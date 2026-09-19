"""
MarketMinds - Configuration
All tunable constants for cost calculations, model paths, and Flask settings
live here so the rest of the app never hardcodes a number.
"""

import os

# Load a local .env file if python-dotenv is available, so MARKETMINDS_SECRET_KEY
# and other environment variables can be set without exporting them manually.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Flask ---
    SECRET_KEY = os.environ.get("MARKETMINDS_SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "marketminds.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Data paths ---
    DATA_DIR = os.path.join(BASE_DIR, "data")
    MANDI_PRICES_CSV = os.path.join(DATA_DIR, "mandi_prices.csv")
    BUYERS_CSV = os.path.join(DATA_DIR, "buyers.csv")
    FARMERS_CSV = os.path.join(DATA_DIR, "farmers.csv")

    # --- Model paths ---
    MODEL_DIR = os.path.join(BASE_DIR, "models")
    PRICE_MODEL_PATH = os.path.join(MODEL_DIR, "price_model.pkl")

    # --- Business logic constants (demo/prototype values) ---
    # Transport cost per km per quintal (INR)
    TRANSPORT_COST_PER_KM_PER_QUINTAL = 2.5

    # Storage cost per quintal per day (INR)
    STORAGE_COST_PER_QUINTAL_PER_DAY = 4.0

    # Flat "other charges" applied per transaction (mandi fees, loading, etc.)
    OTHER_CHARGES_FLAT = 150.0
    OTHER_CHARGES_PER_QUINTAL = 3.0

    # Default number of days a farmer would need to wait for the
    # "predicted future price" to materialize, used in Sell Now vs Wait.
    DEFAULT_WAIT_DAYS = 7

    # Perishability factor by crop: higher = spoils faster = higher effective
    # storage risk/cost multiplier. 1.0 = baseline (grains), higher for produce.
    PERISHABILITY_FACTOR = {
        "Tomato": 1.8,
        "Onion": 1.1,
        "Potato": 1.15,
        "Wheat": 1.0,
        "Rice": 1.0,
    }

    # Crops and quality grades supported by the platform
    CROPS = ["Tomato", "Onion", "Potato", "Wheat", "Rice"]
    QUALITY_GRADES = ["Grade A", "Grade B", "Grade C"]

    # Number of historical days of demo mandi price data to generate
    HISTORY_DAYS = 120

    # --- Auth / account settings ---
    MIN_PASSWORD_LENGTH = 6

    LANGUAGES = ["Hindi", "English", "Punjabi", "Marathi", "Gujarati", "Bengali",
                 "Tamil", "Telugu", "Kannada", "Bhojpuri"]

    STATES = ["Uttar Pradesh", "Delhi", "Rajasthan", "Madhya Pradesh", "Punjab",
              "Haryana", "Bihar", "Maharashtra", "Gujarat", "West Bengal"]

