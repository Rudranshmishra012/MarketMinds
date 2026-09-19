"""
MarketMinds - Sell Now vs Wait Decision Algorithm
-----------------------------------------------------
Compares the profit of selling today against the expected profit of
waiting Config.DEFAULT_WAIT_DAYS days for a (hopefully) better price,
after accounting for the extra storage cost and the crop's perishability.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config


def sell_now_vs_wait(commodity: str, current_price: float, predicted_price: float,
                      quantity: float, waiting_days: int = None) -> dict:
    if waiting_days is None:
        waiting_days = Config.DEFAULT_WAIT_DAYS

    perishability = Config.PERISHABILITY_FACTOR.get(commodity, 1.0)

    profit_if_sold_now = round(current_price * quantity, 2)

    # Waiting means paying storage for the crop while hoping for a better price.
    # Perishable crops incur a higher effective storage cost (risk of spoilage/quality loss).
    storage_cost = round(
        quantity * Config.STORAGE_COST_PER_QUINTAL_PER_DAY * waiting_days * perishability, 2
    )
    expected_revenue_if_waiting = round(predicted_price * quantity, 2)
    expected_profit_if_waiting = round(expected_revenue_if_waiting - storage_cost, 2)

    expected_additional_benefit = round(expected_profit_if_waiting - profit_if_sold_now, 2)

    if expected_profit_if_waiting > profit_if_sold_now:
        decision = "WAIT"
        reason = (
            f"Waiting {waiting_days} day(s) is expected to yield ₹{expected_additional_benefit:,.2f} "
            f"more profit than selling today, even after accounting for ₹{storage_cost:,.2f} in "
            f"storage costs (perishability factor: {perishability}x)."
        )
    else:
        decision = "SELL NOW"
        reason = (
            f"Selling now yields ₹{abs(expected_additional_benefit):,.2f} more (or avoids losing that much) "
            f"compared to waiting {waiting_days} day(s), once storage cost (₹{storage_cost:,.2f}) and "
            f"perishability (factor: {perishability}x) are factored in."
        )

    return {
        "decision": decision,
        "reason": reason,
        "profit_if_sold_now": profit_if_sold_now,
        "expected_profit_if_waiting": expected_profit_if_waiting,
        "storage_cost": storage_cost,
        "waiting_days": waiting_days,
        "perishability_factor": perishability,
        "expected_additional_benefit": expected_additional_benefit,
    }
