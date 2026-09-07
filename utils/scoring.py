"""
Financial Health Score engine.

Fully rule-based (0-100), broken into 4 category sub-scores: Liquidity,
Leverage, Asset Growth, Equity Strength. No LLM involved -- Claude only
narrates the score afterward, never generates it.

Each scoring function returns (score_0_to_100, explanation_str).
Thresholds are simple, documented, and easy to tune.
"""


def _score_current_ratio(cr):
    if cr is None:
        return None, "Current ratio unavailable."
    if cr >= 2.0:
        return 100, f"Current ratio {cr} is strong (>=2.0)."
    if cr >= 1.5:
        return 85, f"Current ratio {cr} is healthy (1.5-2.0)."
    if cr >= 1.0:
        return 65, f"Current ratio {cr} is adequate but not strong (1.0-1.5)."
    if cr >= 0.75:
        return 40, f"Current ratio {cr} indicates liquidity pressure (0.75-1.0)."
    return 15, f"Current ratio {cr} indicates significant liquidity risk (<0.75)."


def _score_debt_to_equity(de):
    if de is None:
        return None, "Debt-to-equity unavailable."
    if de <= 0.5:
        return 100, f"Debt-to-equity {de} is conservative (<=0.5)."
    if de <= 1.0:
        return 80, f"Debt-to-equity {de} is moderate (0.5-1.0)."
    if de <= 1.5:
        return 60, f"Debt-to-equity {de} is elevated (1.0-1.5)."
    if de <= 2.5:
        return 35, f"Debt-to-equity {de} indicates high leverage (1.5-2.5)."
    return 10, f"Debt-to-equity {de} indicates excessive leverage (>2.5)."


def _score_growth(pct, positive_good=True):
    """Generic scorer for a YoY growth percentage."""
    if pct is None:
        return None, "Growth data unavailable."
    if not positive_good:
        pct = -pct
    if pct >= 15:
        return 100, f"Growth of {pct:+.1f}% is strong."
    if pct >= 5:
        return 80, f"Growth of {pct:+.1f}% is healthy."
    if pct >= 0:
        return 60, f"Growth of {pct:+.1f}% is flat-to-slightly-positive."
    if pct >= -10:
        return 35, f"Decline of {pct:.1f}% is a mild concern."
    return 10, f"Decline of {pct:.1f}% is a significant concern."


def compute_health_score(extracted_data, ratios_df):
    """
    Returns:
        {
            "overall": int (0-100),
            "categories": {
                "Liquidity": {"score": int, "detail": str},
                "Leverage": {"score": int, "detail": str},
                "Asset Growth": {"score": int, "detail": str},
                "Equity Strength": {"score": int, "detail": str},
            }
        }
    Category scores that can't be computed (missing data) are excluded
    from the overall average rather than penalized.
    """
    from utils.ratios import yoy_growth

    periods = extracted_data.get("periods", [])
    latest = periods[-1] if periods else None

    categories = {}

    # Liquidity: latest Current Ratio
    cr = ratios_df.loc["Current Ratio", latest] if latest and "Current Ratio" in ratios_df.index else None
    score, detail = _score_current_ratio(cr)
    categories["Liquidity"] = {"score": score, "detail": detail}

    # Leverage: latest Debt to Equity
    de = ratios_df.loc["Debt to Equity", latest] if latest and "Debt to Equity" in ratios_df.index else None
    score, detail = _score_debt_to_equity(de)
    categories["Leverage"] = {"score": score, "detail": detail}

    # Asset Growth: latest YoY growth in total_assets
    asset_growth = yoy_growth(extracted_data, "total_assets", section="balance_sheet")
    latest_growth = asset_growth.get(latest) if latest else None
    score, detail = _score_growth(latest_growth, positive_good=True)
    categories["Asset Growth"] = {"score": score, "detail": detail}

    # Equity Strength: latest YoY growth in total_equity
    equity_growth = yoy_growth(extracted_data, "total_equity", section="balance_sheet")
    latest_eq_growth = equity_growth.get(latest) if latest else None
    score, detail = _score_growth(latest_eq_growth, positive_good=True)
    categories["Equity Strength"] = {"score": score, "detail": detail}

    valid_scores = [c["score"] for c in categories.values() if c["score"] is not None]
    overall = round(sum(valid_scores) / len(valid_scores)) if valid_scores else None

    return {"overall": overall, "categories": categories}


def score_label(score):
    if score is None:
        return "N/A"
    if score >= 75:
        return "🟢 Healthy"
    if score >= 50:
        return "🟡 Moderate"
    return "🔴 Risk"
