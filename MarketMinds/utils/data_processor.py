"""
MarketMinds - Data Processor
------------------------------
Central place for loading CSV datasets and producing price predictions.
Handles the "ML model missing" case gracefully with a historical-trend
fallback, per the functional requirements.
"""

import os
import sys
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config

_model_bundle = None
_model_load_attempted = False


def load_mandi_prices() -> pd.DataFrame:
    df = pd.read_csv(Config.MANDI_PRICES_CSV)
    df["Arrival_Date"] = pd.to_datetime(df["Arrival_Date"])
    return df


def load_buyers() -> pd.DataFrame:
    return pd.read_csv(Config.BUYERS_CSV)


def load_farmers() -> pd.DataFrame:
    return pd.read_csv(Config.FARMERS_CSV)


def get_model_bundle():
    """Lazily load the trained model bundle. Returns None if unavailable
    (the app must keep working without it -- see predict_price fallback)."""
    global _model_bundle, _model_load_attempted
    if _model_bundle is not None:
        return _model_bundle
    if _model_load_attempted:
        return None

    _model_load_attempted = True
    if os.path.exists(Config.PRICE_MODEL_PATH):
        try:
            _model_bundle = joblib.load(Config.PRICE_MODEL_PATH)
        except Exception as exc:  # noqa: BLE001 - defensive: never crash the app
            print(f"[MarketMinds] Warning: failed to load price model ({exc}). "
                  f"Falling back to historical-trend prediction.")
            _model_bundle = None
    return _model_bundle


def _historical_fallback_prediction(market_df: pd.DataFrame) -> float:
    """Simple, transparent fallback: average of the last 5 recorded prices,
    nudged by the recent linear trend. Used when the ML model is unavailable
    or when a crop/market combination wasn't seen during training."""
    recent = market_df.sort_values("Arrival_Date").tail(5)
    if recent.empty:
        return 0.0
    avg_price = recent["Modal_Price"].mean()
    if len(recent) >= 2:
        trend = (recent["Modal_Price"].iloc[-1] - recent["Modal_Price"].iloc[0]) / len(recent)
    else:
        trend = 0.0
    return round(float(avg_price + trend), 2)


def predict_price(commodity: str, market: str, mandi_df: pd.DataFrame = None,
                   target_date: datetime = None) -> dict:
    """
    Predict the price for a given crop+market.

    Returns a dict:
      {
        "current_price": float,   # most recent known modal price
        "predicted_price": float, # model or fallback prediction
        "source": "model" | "fallback",
        "history": [ {date, price}, ... ]  # for charting
      }
    """
    if mandi_df is None:
        mandi_df = load_mandi_prices()

    subset = mandi_df[(mandi_df["Commodity"] == commodity) & (mandi_df["Market"] == market)]
    subset = subset.sort_values("Arrival_Date")

    if subset.empty:
        return {
            "current_price": 0.0,
            "predicted_price": 0.0,
            "source": "fallback",
            "history": [],
        }

    current_price = float(subset["Modal_Price"].iloc[-1])
    if target_date is None:
        target_date = subset["Arrival_Date"].iloc[-1] + timedelta(days=1)

    bundle = get_model_bundle()
    predicted_price = None
    source = "fallback"

    if bundle is not None:
        try:
            market_encoder = bundle["market_encoder"]
            commodity_encoder = bundle["commodity_encoder"]
            model = bundle["model"]

            if market in market_encoder.classes_ and commodity in commodity_encoder.classes_:
                features = pd.DataFrame([{
                    "Month": target_date.month,
                    "Day": target_date.day,
                    "Day_Of_Week": target_date.dayofweek if hasattr(target_date, "dayofweek") else target_date.weekday(),
                    "Previous_Price": current_price,
                    "Market_Encoded": market_encoder.transform([market])[0],
                    "Commodity_Encoded": commodity_encoder.transform([commodity])[0],
                }])[bundle["feature_cols"]]
                predicted_price = float(model.predict(features)[0])
                source = "model"
        except Exception as exc:  # noqa: BLE001 - never let prediction crash the app
            print(f"[MarketMinds] Model prediction failed ({exc}); using fallback.")
            predicted_price = None

    if predicted_price is None:
        predicted_price = _historical_fallback_prediction(subset)
        source = "fallback"

    history = [
        {"date": row["Arrival_Date"].strftime("%Y-%m-%d"), "price": round(float(row["Modal_Price"]), 2)}
        for _, row in subset.tail(30).iterrows()
    ]

    return {
        "current_price": round(current_price, 2),
        "predicted_price": round(predicted_price, 2),
        "source": source,
        "history": history,
    }


def get_markets_for_commodity(commodity: str, mandi_df: pd.DataFrame = None) -> pd.DataFrame:
    """Return one row per distinct market for a commodity, with distance info."""
    if mandi_df is None:
        mandi_df = load_mandi_prices()
    subset = mandi_df[mandi_df["Commodity"] == commodity]
    markets = subset.drop_duplicates(subset=["Market"])[["Market", "State", "District", "Distance_KM"]]
    return markets.reset_index(drop=True)
