"""
Ratio calculation engine.

Takes the normalized dict produced by claude_client.extract_financials()
(schema: income_statement / balance_sheet / cash_flow, each a dict of
{line_item: {period: value}}) and computes standard financial ratios
per period. Pure Python/pandas -- no LLM calls -- so the numbers are
always exact and reproducible.
"""

import pandas as pd


def _get(section, item, period):
    try:
        return section.get(item, {}).get(period)
    except AttributeError:
        return None


def _safe_div(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def compute_ratios(extracted_data):
    """
    Returns a pandas DataFrame: rows = ratio names, columns = periods.
    Silently skips a ratio/period combination if required inputs are missing.
    """
    periods = extracted_data.get("periods", [])
    inc = extracted_data.get("income_statement", {})
    bs = extracted_data.get("balance_sheet", {})
    cf = extracted_data.get("cash_flow", {})

    rows = {}

    def add(name, fn):
        values = {}
        for p in periods:
            try:
                values[p] = fn(p)
            except Exception:
                values[p] = None
        rows[name] = values

    # Profitability
    add("Gross Margin %", lambda p: _pct(_safe_div(
        _get(inc, "gross_profit", p), _get(inc, "revenue", p))))
    add("Operating Margin %", lambda p: _pct(_safe_div(
        _get(inc, "operating_income", p), _get(inc, "revenue", p))))
    add("Net Margin %", lambda p: _pct(_safe_div(
        _get(inc, "net_income", p), _get(inc, "revenue", p))))
    add("Return on Equity %", lambda p: _pct(_safe_div(
        _get(inc, "net_income", p), _get(bs, "total_equity", p))))
    add("Return on Assets %", lambda p: _pct(_safe_div(
        _get(inc, "net_income", p), _get(bs, "total_assets", p))))

    # Liquidity
    add("Current Ratio", lambda p: _round(_safe_div(
        _get(bs, "current_assets", p), _get(bs, "current_liabilities", p))))
    add("Quick Ratio", lambda p: _round(_safe_div(
        _sub(_get(bs, "current_assets", p), _get(bs, "inventory", p)),
        _get(bs, "current_liabilities", p))))
    add("Cash Ratio", lambda p: _round(_safe_div(
        _get(bs, "cash_and_equivalents", p), _get(bs, "current_liabilities", p))))
    add("Working Capital", lambda p: _sub(
        _get(bs, "current_assets", p), _get(bs, "current_liabilities", p)))

    # Leverage
    add("Debt to Equity", lambda p: _round(_safe_div(
        _get(bs, "total_liabilities", p), _get(bs, "total_equity", p))))
    add("Debt to Assets", lambda p: _round(_safe_div(
        _get(bs, "total_liabilities", p), _get(bs, "total_assets", p))))

    # Efficiency / cash
    add("Operating Cash Flow Margin %", lambda p: _pct(_safe_div(
        _get(cf, "operating_cash_flow", p), _get(inc, "revenue", p))))

    df = pd.DataFrame(rows).T
    df = df[periods] if periods else df
    return df


def yoy_growth(extracted_data, line_item, section="income_statement"):
    """Returns a dict {period: pct_change_from_prior_period or None}."""
    periods = extracted_data.get("periods", [])
    sec = extracted_data.get(section, {})
    series = [sec.get(line_item, {}).get(p) for p in periods]

    growth = {}
    for i, p in enumerate(periods):
        if i == 0 or series[i] is None or series[i - 1] in (None, 0):
            growth[p] = None
        else:
            growth[p] = round(((series[i] - series[i - 1]) / abs(series[i - 1])) * 100, 1)
    return growth


def variance_analysis(extracted_data):
    """
    Year-over-year variance across key line items, in one table.
    Returns a pandas DataFrame: rows = metrics, columns = periods,
    values = % change from the prior period (None for the first period).
    """
    periods = extracted_data.get("periods", [])
    metrics = [
        ("Revenue", "income_statement", "revenue"),
        ("Net Income", "income_statement", "net_income"),
        ("Total Assets", "balance_sheet", "total_assets"),
        ("Total Liabilities", "balance_sheet", "total_liabilities"),
        ("Total Equity", "balance_sheet", "total_equity"),
        ("Total Debt", "balance_sheet", "total_liabilities"),  # alias if no separate debt field
    ]
    rows = {}
    for label, section, item in metrics:
        growth = yoy_growth(extracted_data, item, section=section)
        rows[label] = growth
    df = pd.DataFrame(rows).T
    df = df[periods] if periods else df
    return df


def highlight_variance(variance_df):
    """
    Scans a variance_analysis() table and returns a list of plain-English
    highlights for the largest moves (growth and decline) in the latest period.
    """
    if variance_df.empty or len(variance_df.columns) == 0:
        return []
    latest = variance_df.columns[-1]
    latest_col = variance_df[latest].dropna()
    if latest_col.empty:
        return []

    highlights = []
    top_growth = latest_col.idxmax()
    top_decline = latest_col.idxmin()

    if latest_col[top_growth] > 0:
        highlights.append(f"Highest growth: {top_growth} ({latest_col[top_growth]:+.1f}%) in {latest}.")
    if latest_col[top_decline] < 0:
        highlights.append(f"Largest decline: {top_decline} ({latest_col[top_decline]:+.1f}%) in {latest}.")

    if "Total Liabilities" in latest_col and "Total Assets" in latest_col:
        if latest_col["Total Liabilities"] > latest_col["Total Assets"] + 5:
            highlights.append(
                f"Liabilities grew faster than assets in {latest} "
                f"({latest_col['Total Liabilities']:+.1f}% vs {latest_col['Total Assets']:+.1f}%)."
            )
    if "Total Equity" in latest_col and latest_col["Total Equity"] < 0:
        highlights.append(f"Equity declined {latest_col['Total Equity']:.1f}% in {latest}.")

    return highlights


def flag_risks(ratios_df, variance_df=None):
    """Rule-based flags from the computed ratio table (and optionally variance data)."""
    flags = []
    if ratios_df.empty:
        return flags

    latest_period = ratios_df.columns[-1]

    def latest(name):
        return ratios_df.loc[name, latest_period] if name in ratios_df.index else None

    cr = latest("Current Ratio")
    if cr is not None and cr < 1:
        flags.append(("⚠️ Liquidity Risk", f"Current ratio is {cr} (below 1) — potential short-term liquidity risk."))

    de = latest("Debt to Equity")
    if de is not None and de > 1.5:
        flags.append(("⚠️ High Leverage Risk", f"Debt-to-equity is {de} — elevated leverage relative to equity."))

    nm = latest("Net Margin %")
    if nm is not None and nm < 0:
        flags.append(("🔴 Profitability Risk", f"Net margin is {nm}% — the company is operating at a net loss."))

    ocf = latest("Operating Cash Flow Margin %")
    if ocf is not None and ocf < 0:
        flags.append(("🔴 Cash Flow Risk", f"Operating cash flow margin is {ocf}% — cash burn from core operations."))

    if variance_df is not None and not variance_df.empty:
        latest_v = variance_df.columns[-1]
        if "Total Liabilities" in variance_df.index and "Total Assets" in variance_df.index:
            liab_g = variance_df.loc["Total Liabilities", latest_v]
            asset_g = variance_df.loc["Total Assets", latest_v]
            if liab_g is not None and asset_g is not None and liab_g > asset_g + 5:
                flags.append(("⚠️ Liability Growth Risk",
                               f"Liabilities grew {liab_g:+.1f}% vs assets {asset_g:+.1f}% — "
                               f"liabilities outpacing asset growth."))
        if "Total Equity" in variance_df.index:
            eq_g = variance_df.loc["Total Equity", latest_v]
            if eq_g is not None and eq_g < 0:
                flags.append(("⚠️ Equity Deterioration", f"Equity declined {eq_g:.1f}% in {latest_v}."))

    return flags


def _pct(x):
    return round(x * 100, 1) if x is not None else None


def _round(x):
    return round(x, 2) if x is not None else None


def _sub(a, b):
    if a is None or b is None:
        return None
    return a - b
