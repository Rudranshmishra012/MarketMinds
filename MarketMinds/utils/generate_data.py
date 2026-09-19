"""
MarketMinds - Demo Data Generator
----------------------------------
Generates realistic-looking DEMO/PROTOTYPE datasets:
  - data/mandi_prices.csv
  - data/buyers.csv
  - data/farmers.csv

IMPORTANT: This data is synthetically generated for prototype/demo purposes.
It is NOT sourced from AGMARKNET or data.gov.in. The CSV schema is designed
so a real AGMARKNET/data.gov.in export can be dropped in as a replacement
without changing any application code (see README.md).

Run directly:  python utils/generate_data.py
"""

import os
import re
import sys
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

random.seed(42)
np.random.seed(42)

# ---------------------------------------------------------------------------
# 1. MANDI PRICE DATASET
# ---------------------------------------------------------------------------

MARKETS = [
    {"name": "Greater Noida Mandi", "state": "Uttar Pradesh", "district": "Gautam Buddh Nagar", "distance_km": 45},
    {"name": "Azadpur Mandi", "state": "Delhi", "district": "North Delhi", "distance_km": 60},
    {"name": "Agra Mandi", "state": "Uttar Pradesh", "district": "Agra", "distance_km": 15},
    {"name": "Mathura Mandi", "state": "Uttar Pradesh", "district": "Mathura", "distance_km": 55},
    {"name": "Kanpur Mandi", "state": "Uttar Pradesh", "district": "Kanpur Nagar", "distance_km": 130},
    {"name": "Lucknow Mandi", "state": "Uttar Pradesh", "district": "Lucknow", "distance_km": 210},
    {"name": "Jaipur Mandi", "state": "Rajasthan", "district": "Jaipur", "distance_km": 240},
    {"name": "Bhopal Mandi", "state": "Madhya Pradesh", "district": "Bhopal", "distance_km": 480},
]

# Base modal price (INR per quintal) and volatility per crop
CROP_BASE_PRICE = {
    "Tomato": {"base": 1400, "volatility": 0.18, "trend": 0.15},
    "Onion": {"base": 1800, "volatility": 0.15, "trend": 0.05},
    "Potato": {"base": 1200, "volatility": 0.10, "trend": -0.05},
    "Wheat": {"base": 2200, "volatility": 0.04, "trend": 0.02},
    "Rice": {"base": 2800, "volatility": 0.05, "trend": 0.03},
}

VARIETIES = {
    "Tomato": ["Hybrid", "Local", "Desi"],
    "Onion": ["Nashik Red", "Bangalore Rose", "Local"],
    "Potato": ["Jyoti", "Kufri Chandramukhi", "Local"],
    "Wheat": ["Lokwan", "Sharbati", "HD-2967"],
    "Rice": ["Basmati", "Sona Masoori", "Common"],
}


def generate_mandi_prices():
    rows = []
    start_date = datetime.today() - timedelta(days=Config.HISTORY_DAYS)

    for crop, params in CROP_BASE_PRICE.items():
        for market in MARKETS:
            # Each market has a slight structural price offset vs base
            market_offset = np.random.uniform(-0.08, 0.08)
            base = params["base"] * (1 + market_offset)
            variety = random.choice(VARIETIES[crop])

            price = base
            for day in range(Config.HISTORY_DAYS):
                date = start_date + timedelta(days=day)

                # Seasonal-ish trend + noise (random walk with slight drift)
                drift = params["trend"] * (base * 0.001)
                noise = np.random.normal(0, params["volatility"] * base * 0.05)
                price = max(price + drift + noise, base * 0.5)

                modal_price = round(price, 2)
                spread = modal_price * 0.06
                min_price = round(max(modal_price - spread, 1), 2)
                max_price = round(modal_price + spread, 2)

                rows.append({
                    "Arrival_Date": date.strftime("%Y-%m-%d"),
                    "State": market["state"],
                    "District": market["district"],
                    "Market": market["name"],
                    "Commodity": crop,
                    "Variety": variety,
                    "Min_Price": min_price,
                    "Max_Price": max_price,
                    "Modal_Price": modal_price,
                    "Distance_KM": market["distance_km"],
                })

    df = pd.DataFrame(rows)
    df = df.sort_values(["Commodity", "Market", "Arrival_Date"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 2. BUYER DATASET
# ---------------------------------------------------------------------------

BUYER_NAME_POOL = [
    "AgroFresh Traders", "Bharat Wholesale Foods", "Green Valley Exports",
    "National Vegetable Suppliers", "Sunrise Agro Mart", "Delhi Fresh Produce Co.",
    "Farm2City Buyers", "UP Grain Merchants", "Golden Harvest Trading",
    "Metro Mandi Buyers", "Rajasthan Foodgrains Ltd.", "Kisan Mitra Procurement",
    "City Retail Chain Buyers", "Northern Spice & Veg Co.", "Fresh Route Logistics",
    "Annapurna Agro Foods", "Rural Link Traders", "Highway Mandi Buyers",
    "Prime Produce Exporters", "Local Bazaar Aggregators", "Agri Bridge Buyers",
    "Wholesome Grains Pvt Ltd", "Vegex India", "Mandi Direct Buyers",
]

LOCATIONS = [
    "Greater Noida", "Delhi", "Agra", "Mathura", "Kanpur", "Lucknow", "Jaipur",
    "Bhopal", "Ghaziabad", "Meerut", "Aligarh", "Noida",
]


def _demo_contact(index: int, buyer_name: str):
    """Deterministic placeholder phone + email for a demo buyer.

    Uses its own seeded Random instance so it never disturbs the global
    random stream (the rest of the generated data stays identical). Emails
    use the reserved example.com domain so nothing points at a real inbox.
    """
    rng = random.Random(f"buyer-contact-{index}")
    digits = rng.choice("6789") + "".join(rng.choice("0123456789") for _ in range(9))
    phone = f"+91 {digits[:5]} {digits[5:]}"
    slug = re.sub(r"[^a-z0-9]", "", buyer_name.lower())
    return phone, f"sales@{slug}.example.com"


def generate_buyers(n=24):
    rows = []
    for i in range(1, n + 1):
        crop = random.choice(Config.CROPS)
        base_price = CROP_BASE_PRICE[crop]["base"]
        buyer_name = BUYER_NAME_POOL[(i - 1) % len(BUYER_NAME_POOL)]
        phone, email = _demo_contact(i, buyer_name)
        rows.append({
            "Buyer_ID": f"B{i:03d}",
            "Buyer_Name": buyer_name,
            "Crop": crop,
            "Quantity_Required": random.choice([50, 80, 100, 120, 150, 200, 250, 300]),
            "Quality": random.choice(Config.QUALITY_GRADES),
            "Price_Offered": round(base_price * np.random.uniform(0.9, 1.15), 2),
            "Location": random.choice(LOCATIONS),
            "Distance_KM": random.choice([10, 20, 35, 45, 60, 90, 130, 180, 240]),
            "Payment_Score": random.randint(55, 100),
            "Dispute_Score": random.randint(0, 30),
            "Verified": random.choice([1, 1, 1, 0]),  # ~75% verified
            "Contact_Phone": phone,
            "Contact_Email": email,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. FARMER DATASET (for FPO aggregation)
# ---------------------------------------------------------------------------

FARMER_NAME_POOL = [
    "Ram Kumar", "Suresh Yadav", "Meena Devi", "Anil Sharma", "Vijay Singh",
    "Kavita Rani", "Rakesh Chaudhary", "Sunita Kumari", "Mahesh Prajapati",
    "Geeta Devi", "Ramesh Verma", "Pooja Sharma", "Ashok Kumar", "Radha Rani",
    "Sanjay Tiwari", "Lakshmi Devi", "Naresh Gupta", "Kamla Devi",
    "Deepak Rathore", "Sarita Devi", "Manoj Kumar", "Usha Rani",
    "Vinod Singh", "Rekha Devi",
]


def generate_farmers(n=24):
    rows = []
    for i in range(1, n + 1):
        crop = random.choice(Config.CROPS)
        rows.append({
            "Farmer_ID": f"F{i:03d}",
            "Farmer_Name": FARMER_NAME_POOL[(i - 1) % len(FARMER_NAME_POOL)],
            "Crop": crop,
            "Quantity": random.choice([10, 15, 20, 25, 30, 40, 50]),
            "Quality": random.choice(Config.QUALITY_GRADES),
            "Location": random.choice(LOCATIONS),
        })
    return pd.DataFrame(rows)


def main():
    os.makedirs(Config.DATA_DIR, exist_ok=True)

    print("Generating demo mandi price dataset...")
    mandi_df = generate_mandi_prices()
    mandi_df.to_csv(Config.MANDI_PRICES_CSV, index=False)
    print(f"  -> {len(mandi_df)} rows written to {Config.MANDI_PRICES_CSV}")

    print("Generating demo buyers dataset...")
    buyers_df = generate_buyers()
    buyers_df.to_csv(Config.BUYERS_CSV, index=False)
    print(f"  -> {len(buyers_df)} rows written to {Config.BUYERS_CSV}")

    print("Generating demo farmers dataset...")
    farmers_df = generate_farmers()
    farmers_df.to_csv(Config.FARMERS_CSV, index=False)
    print(f"  -> {len(farmers_df)} rows written to {Config.FARMERS_CSV}")

    print("\nAll demo datasets generated successfully.")
    print("NOTE: These are synthetic prototype datasets, not official government data.")


if __name__ == "__main__":
    main()
