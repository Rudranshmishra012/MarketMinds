"""
MarketMinds - Buyer Matching Algorithm
------------------------------------------
Deterministic, explainable weighted scoring system (0-100):

    Crop Match             : 25 points
    Quality Match          : 15 points
    Quantity Compatibility : 15 points
    Price Score            : 20 points
    Distance Score         : 10 points
    Reliability Score      : 15 points
                              ---------
                              100 points
"""

import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config
from utils.data_processor import load_buyers

QUALITY_RANK = {"Grade A": 3, "Grade B": 2, "Grade C": 1}

WEIGHTS = {
    "crop_match": 25,
    "quality_match": 15,
    "quantity_compat": 15,
    "price_score": 20,
    "distance_score": 10,
    "reliability_score": 15,
}


def calculate_reliability_score(payment_score: float, dispute_score: float, verified: bool) -> float:
    """Reliability out of 100, built from payment history, disputes, and
    verification status. Always clamped to [0, 100]."""
    payment_component = max(0, min(payment_score, 100)) * 0.6          # up to 60 pts
    dispute_penalty = max(0, min(dispute_score, 100)) * 0.4            # up to 40 pt penalty
    verification_bonus = 15 if verified else 0

    score = payment_component - dispute_penalty + verification_bonus
    return round(max(0, min(score, 100)), 2)


def _quantity_compatibility(offered_qty: float, required_qty: float) -> float:
    """1.0 if the farmer can fully meet (or exceed) the buyer's requirement;
    otherwise scaled down by how much of the requirement can be met."""
    if required_qty <= 0:
        return 0.0
    ratio = offered_qty / required_qty
    if ratio >= 1:
        return 1.0
    return max(0.0, ratio)


def _price_score(price_offered: float, market_reference_price: float) -> float:
    """Higher offered price relative to the market reference price scores higher.
    Capped at 1.0 so a very high outlier offer doesn't break the scale."""
    price_offered = float(price_offered)
    market_reference_price = float(market_reference_price)
    if market_reference_price <= 0:
        return 0.5
    ratio = price_offered / market_reference_price
    return round(max(0.0, min(ratio, 1.2)) / 1.2, 4)


def _distance_score(distance_km: float, max_reasonable_km: float = 300.0) -> float:
    """Closer buyers score higher. Linearly decays to 0 at max_reasonable_km."""
    if distance_km <= 0:
        return 1.0
    score = 1 - (distance_km / max_reasonable_km)
    return round(max(0.0, min(score, 1.0)), 4)


def match_buyers(commodity: str, quantity: float, quality: str,
                  market_reference_price: float = None) -> list:
    """Score every buyer requiring this commodity, return ranked list with
    a transparent per-buyer score breakdown."""
    buyers_df = load_buyers()
    subset = buyers_df[buyers_df["Crop"] == commodity].copy()

    if subset.empty:
        return []

    if market_reference_price is None:
        market_reference_price = subset["Price_Offered"].mean()

    results = []
    for _, buyer in subset.iterrows():
        crop_match = 1.0  # already filtered to matching crop

        buyer_quality_rank = QUALITY_RANK.get(buyer["Quality"], 1)
        farmer_quality_rank = QUALITY_RANK.get(quality, 1)
        # Full credit if farmer's quality meets or exceeds requirement, partial otherwise
        quality_match = 1.0 if farmer_quality_rank >= buyer_quality_rank else farmer_quality_rank / buyer_quality_rank

        quantity_compat = _quantity_compatibility(quantity, buyer["Quantity_Required"])
        price_score = _price_score(buyer["Price_Offered"], market_reference_price)
        distance_score = _distance_score(buyer["Distance_KM"])

        reliability_raw = calculate_reliability_score(
            buyer["Payment_Score"], buyer["Dispute_Score"], bool(buyer["Verified"])
        )
        reliability_score_normalized = reliability_raw / 100.0

        breakdown = {
            "crop_match": round(crop_match * WEIGHTS["crop_match"], 2),
            "quality_match": round(quality_match * WEIGHTS["quality_match"], 2),
            "quantity_compat": round(quantity_compat * WEIGHTS["quantity_compat"], 2),
            "price_score": round(price_score * WEIGHTS["price_score"], 2),
            "distance_score": round(distance_score * WEIGHTS["distance_score"], 2),
            "reliability_score": round(reliability_score_normalized * WEIGHTS["reliability_score"], 2),
        }
        total_score = round(sum(breakdown.values()), 2)

        results.append({
            "buyer_id": str(buyer["Buyer_ID"]),
            "buyer_name": str(buyer["Buyer_Name"]),
            "crop": str(buyer["Crop"]),
            "quantity_required": int(buyer["Quantity_Required"]),
            "quality_required": str(buyer["Quality"]),
            "price_offered": float(buyer["Price_Offered"]),
            "location": str(buyer["Location"]),
            "distance_km": float(buyer["Distance_KM"]),
            "payment_score": float(buyer["Payment_Score"]),
            "dispute_score": float(buyer["Dispute_Score"]),
            "verified": bool(buyer["Verified"]),
            "reliability_score": float(reliability_raw),
            "match_score": float(total_score),
            "score_breakdown": {k: float(v) for k, v in breakdown.items()},
        })

    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results
