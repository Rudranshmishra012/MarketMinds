"""
MarketMinds - Smart Market Recommendation Engine
---------------------------------------------------
Evaluates every market that trades the farmer's crop and ranks them by
EXPECTED NET PROFIT (not raw price):

    Expected Revenue    = Predicted Price x Quantity
    Transport Cost      = Distance x Cost_Per_KM_Per_Quintal x Quantity
    Storage Cost        = Quantity x Storage_Cost_Per_Quintal x Waiting_Days
    Other Charges       = Flat_Fee + (Per_Quintal_Fee x Quantity)
    Expected Net Profit = Expected Revenue - Transport Cost - Storage Cost - Other Charges
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config
from utils.data_processor import load_mandi_prices, predict_price, get_markets_for_commodity


def calculate_costs(distance_km: float, quantity_quintals: float, waiting_days: int = 0) -> dict:
    transport_cost = distance_km * Config.TRANSPORT_COST_PER_KM_PER_QUINTAL * quantity_quintals / 10
    # (Dividing by 10 keeps demo transport costs realistic for typical
    #  distances/quantities -- i.e. cost scales with tonne-km, not raw km*qty.)
    storage_cost = quantity_quintals * Config.STORAGE_COST_PER_QUINTAL_PER_DAY * waiting_days
    other_charges = Config.OTHER_CHARGES_FLAT + (Config.OTHER_CHARGES_PER_QUINTAL * quantity_quintals)
    return {
        "transport_cost": round(transport_cost, 2),
        "storage_cost": round(storage_cost, 2),
        "other_charges": round(other_charges, 2),
    }


def evaluate_market(commodity: str, market_row, quantity: float, mandi_df, waiting_days: int = 0) -> dict:
    """Evaluate a single market and return full financial breakdown."""
    market_name = market_row["Market"]
    distance = float(market_row["Distance_KM"])

    price_info = predict_price(commodity, market_name, mandi_df=mandi_df)
    predicted_price = price_info["predicted_price"]
    current_price = price_info["current_price"]

    expected_revenue = round(predicted_price * quantity, 2)
    costs = calculate_costs(distance, quantity, waiting_days)
    total_costs = round(costs["transport_cost"] + costs["storage_cost"] + costs["other_charges"], 2)
    expected_net_profit = round(expected_revenue - total_costs, 2)

    return {
        "market": market_name,
        "state": market_row.get("State", ""),
        "district": market_row.get("District", ""),
        "distance_km": distance,
        "current_price": current_price,
        "predicted_price": predicted_price,
        "price_source": price_info["source"],
        "quantity": quantity,
        "expected_revenue": expected_revenue,
        "transport_cost": costs["transport_cost"],
        "storage_cost": costs["storage_cost"],
        "other_charges": costs["other_charges"],
        "total_costs": total_costs,
        "expected_net_profit": expected_net_profit,
        "price_history": price_info["history"],
    }


def rank_markets(commodity: str, quantity: float, waiting_days: int = 0) -> list:
    """Evaluate every market that trades this commodity, ranked by
    expected net profit (descending). This is the single source of truth
    used by both the Market Intelligence and AI Recommendation screens."""
    mandi_df = load_mandi_prices()
    markets = get_markets_for_commodity(commodity, mandi_df=mandi_df)

    if markets.empty:
        return []

    results = []
    for _, market_row in markets.iterrows():
        result = evaluate_market(commodity, market_row, quantity, mandi_df, waiting_days)
        results.append(result)

    results.sort(key=lambda r: r["expected_net_profit"], reverse=True)
    return results


def get_best_market_with_reasons(commodity: str, quantity: float, waiting_days: int = 0) -> dict:
    """Return the top-ranked market plus a human-readable, calculation-backed
    explanation of WHY it was chosen (never a random/canned reason)."""
    ranked = rank_markets(commodity, quantity, waiting_days)
    if not ranked:
        return None

    best = ranked[0]
    reasons = []

    if len(ranked) > 1:
        runner_up = ranked[1]
        profit_gap = round(best["expected_net_profit"] - runner_up["expected_net_profit"], 2)
        reasons.append(
            f"Highest expected net profit of all {len(ranked)} markets evaluated "
            f"(₹{best['expected_net_profit']:,.2f}, ₹{profit_gap:,.2f} more than the next best option)."
        )
        if best["transport_cost"] < runner_up["transport_cost"]:
            reasons.append(
                f"Lower transport cost (₹{best['transport_cost']:,.2f}) compared to the next best "
                f"option (₹{runner_up['transport_cost']:,.2f})."
            )
    else:
        reasons.append(f"Only market currently trading this commodity, with an expected net profit of "
                        f"₹{best['expected_net_profit']:,.2f}.")

    if best["predicted_price"] > best["current_price"]:
        reasons.append(
            f"Positive price trend: predicted price (₹{best['predicted_price']:,.2f}) is higher than the "
            f"current price (₹{best['current_price']:,.2f})."
        )

    if best["distance_km"] <= 60:
        reasons.append(f"Suitable distance from farm location ({best['distance_km']:.0f} km).")

    best["reasons"] = reasons
    best["all_ranked_markets"] = ranked
    return best
