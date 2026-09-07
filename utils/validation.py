"""
Data validation.

Runs before any KPI/scoring calculation. Pure rule-based checks -- no LLM.
Returns a structured report the UI can render as pass/fail with explanations.
"""


def validate_data(extracted_data):
    """
    Returns:
        {
            "status": "good" | "issues",
            "checks": [{"name": str, "passed": bool, "detail": str}, ...]
        }
    """
    checks = []
    periods = extracted_data.get("periods", [])
    bs = extracted_data.get("balance_sheet", {})
    inc = extracted_data.get("income_statement", {})

    if not periods:
        checks.append({"name": "Periods detected", "passed": False,
                        "detail": "No financial periods (years/quarters) were found in the data."})
        return {"status": "issues", "checks": checks}
    else:
        checks.append({"name": "Periods detected", "passed": True,
                        "detail": f"Found {len(periods)} period(s): {', '.join(periods)}."})

    # Accounting equation: Assets = Liabilities + Equity
    for p in periods:
        assets = bs.get("total_assets", {}).get(p)
        liabilities = bs.get("total_liabilities", {}).get(p)
        equity = bs.get("total_equity", {}).get(p)

        if assets is None or liabilities is None or equity is None:
            checks.append({"name": f"Accounting equation ({p})", "passed": False,
                            "detail": "Total assets, liabilities, or equity is missing for this period."})
            continue

        diff = abs(assets - (liabilities + equity))
        tolerance = max(abs(assets) * 0.01, 1)  # 1% tolerance or 1 unit, whichever is larger
        if diff <= tolerance:
            checks.append({"name": f"Accounting equation ({p})", "passed": True,
                            "detail": f"Assets ({assets:,.0f}) ≈ Liabilities + Equity ({liabilities + equity:,.0f})."})
        else:
            checks.append({"name": f"Accounting equation ({p})", "passed": False,
                            "detail": f"Assets ({assets:,.0f}) does not match Liabilities + Equity "
                                      f"({liabilities + equity:,.0f}) -- off by {diff:,.0f}."})

    # Missing core line items
    core_items = {
        "balance_sheet": ["total_assets", "total_liabilities", "total_equity",
                           "current_assets", "current_liabilities"],
        "income_statement": ["revenue", "net_income"],
    }
    for section_name, items in core_items.items():
        section = extracted_data.get(section_name, {})
        missing = [item for item in items if item not in section or not section.get(item)]
        if missing:
            checks.append({"name": f"Core fields present ({section_name})", "passed": False,
                            "detail": f"Missing: {', '.join(missing)}."})
        else:
            checks.append({"name": f"Core fields present ({section_name})", "passed": True,
                            "detail": "All core fields found."})

    # Unexpected negative values on fields that should be non-negative
    should_be_nonneg = {
        "balance_sheet": ["total_assets", "current_assets", "inventory",
                           "cash_and_equivalents", "total_equity"],
        "income_statement": ["revenue"],
    }
    negative_flags = []
    for section_name, items in should_be_nonneg.items():
        section = extracted_data.get(section_name, {})
        for item in items:
            for p in periods:
                v = section.get(item, {}).get(p)
                if v is not None and v < 0:
                    negative_flags.append(f"{item} in {p} is negative ({v:,.0f}).")
    if negative_flags:
        checks.append({"name": "No unexpected negatives", "passed": False,
                        "detail": " ".join(negative_flags)})
    else:
        checks.append({"name": "No unexpected negatives", "passed": True,
                        "detail": "No negative values found where none were expected."})

    # Duplicate-looking metrics (same value across all periods -- often a sign of bad extraction)
    suspicious = []
    for section_name in ["balance_sheet", "income_statement", "cash_flow"]:
        section = extracted_data.get(section_name, {})
        for item, values in section.items():
            vals = [values.get(p) for p in periods if values.get(p) is not None]
            if len(vals) >= 2 and len(set(vals)) == 1:
                suspicious.append(f"{item} is identical across all periods.")
    if suspicious:
        checks.append({"name": "No suspiciously static values", "passed": False,
                        "detail": " ".join(suspicious) + " Verify this wasn't an extraction error."})
    else:
        checks.append({"name": "No suspiciously static values", "passed": True,
                        "detail": "Values vary across periods as expected."})

    overall_status = "good" if all(c["passed"] for c in checks) else "issues"
    return {"status": overall_status, "checks": checks}
