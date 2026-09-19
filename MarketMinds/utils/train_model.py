"""
MarketMinds - Price Forecasting Model Trainer
-----------------------------------------------
Trains a RandomForestRegressor to predict Modal_Price for a given
crop/market/date, using only features that would be known in advance
(no leakage from future prices).

Features:
    - Month
    - Day
    - Day_Of_Week
    - Previous_Price (previous available Modal_Price for that crop+market)
    - Market (label-encoded)
    - Commodity (label-encoded)

Target:
    - Modal_Price

Data is sorted chronologically and split with a TIME-BASED split
(train = earlier dates, test = most recent dates) to avoid leakage.

Run directly:  python utils/train_model.py
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build leakage-safe features from the raw mandi price dataframe."""
    df = df.copy()
    df["Arrival_Date"] = pd.to_datetime(df["Arrival_Date"])
    df = df.sort_values(["Commodity", "Market", "Arrival_Date"]).reset_index(drop=True)

    df["Month"] = df["Arrival_Date"].dt.month
    df["Day"] = df["Arrival_Date"].dt.day
    df["Day_Of_Week"] = df["Arrival_Date"].dt.dayofweek

    # Previous_Price = the prior day's Modal_Price for the SAME crop+market
    # (shift(1) within each group -> no leakage from the current/future row)
    df["Previous_Price"] = (
        df.groupby(["Commodity", "Market"])["Modal_Price"].shift(1)
    )

    # Drop the first row of every crop+market group (no previous price available)
    df = df.dropna(subset=["Previous_Price"]).reset_index(drop=True)

    return df


def train():
    if not os.path.exists(Config.MANDI_PRICES_CSV):
        raise FileNotFoundError(
            f"Mandi price dataset not found at {Config.MANDI_PRICES_CSV}. "
            "Run utils/generate_data.py first (or provide a real dataset)."
        )

    raw = pd.read_csv(Config.MANDI_PRICES_CSV)
    df = build_features(raw)

    # Label-encode categorical columns
    market_encoder = LabelEncoder()
    commodity_encoder = LabelEncoder()
    df["Market_Encoded"] = market_encoder.fit_transform(df["Market"])
    df["Commodity_Encoded"] = commodity_encoder.fit_transform(df["Commodity"])

    feature_cols = [
        "Month", "Day", "Day_Of_Week", "Previous_Price",
        "Market_Encoded", "Commodity_Encoded",
    ]
    target_col = "Modal_Price"

    # TIME-BASED split: sort by date, last 20% (most recent) is the test set.
    df = df.sort_values("Arrival_Date").reset_index(drop=True)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    X_train, y_train = train_df[feature_cols], train_df[target_col]
    X_test, y_test = test_df[feature_cols], test_df[target_col]

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    if len(X_test) > 0:
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        print(f"Time-based holdout evaluation: MAE = {mae:.2f} INR, R2 = {r2:.3f}")

    os.makedirs(Config.MODEL_DIR, exist_ok=True)

    bundle = {
        "model": model,
        "market_encoder": market_encoder,
        "commodity_encoder": commodity_encoder,
        "feature_cols": feature_cols,
    }
    joblib.dump(bundle, Config.PRICE_MODEL_PATH)
    print(f"Model saved to {Config.PRICE_MODEL_PATH}")
    return bundle


if __name__ == "__main__":
    train()
