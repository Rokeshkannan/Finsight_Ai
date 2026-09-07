"""
Downloadable PDF report generator using fpdf2 (pure Python, no system deps).
"""

from fpdf import FPDF


class _ReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "FinSight AI -- Financial Analysis Report", ln=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "AI-Powered Financial Statement Intelligence", ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(235, 235, 245)
        self.cell(0, 9, title, ln=True, fill=True)
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, text)
        self.ln(1)


def _clean(text):
    """fpdf's core fonts are latin-1 only; drop characters they can't encode."""
    return text.encode("latin-1", "ignore").decode("latin-1")


def generate_report(extracted_data, ratios_df, health_score, risk_flags,
                     variance_highlights, ai_summary=None, validation=None):
    """
    Returns raw PDF bytes.
    """
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    company = extracted_data.get("company_name", "Company")
    periods = extracted_data.get("periods", [])
    pdf.body_text(_clean(f"Company: {company}"))
    pdf.body_text(_clean(f"Periods analyzed: {', '.join(periods)}"))
    pdf.ln(2)

    # Executive summary
    if ai_summary:
        pdf.section_title("Executive Summary")
        pdf.body_text(_clean(ai_summary))

    # Financial Health Score
    pdf.section_title("Financial Health Score")
    overall = health_score.get("overall")
    pdf.body_text(_clean(f"Overall: {overall}/100" if overall is not None else "Overall: N/A"))
    for cat, info in health_score.get("categories", {}).items():
        score = info.get("score")
        detail = info.get("detail", "")
        line = f"- {cat}: {score if score is not None else 'N/A'}/100 -- {detail}"
        pdf.body_text(_clean(line))

    # KPI table
    pdf.section_title("Key Financial Ratios")
    if not ratios_df.empty:
        col_width = 190 / (len(ratios_df.columns) + 1)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_width, 6, "Ratio", border=1)
        for col in ratios_df.columns:
            pdf.cell(col_width, 6, _clean(str(col)), border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        for idx, row in ratios_df.iterrows():
            pdf.cell(col_width, 6, _clean(str(idx))[:28], border=1)
            for col in ratios_df.columns:
                val = row[col]
                pdf.cell(col_width, 6, _clean(str(val)) if val is not None else "N/A", border=1)
            pdf.ln()
    pdf.ln(2)

    # Variance highlights
    if variance_highlights:
        pdf.section_title("Variance Analysis -- Highlights")
        for h in variance_highlights:
            pdf.body_text(_clean(f"- {h}"))

    # Risk flags
    pdf.section_title("Risk Assessment")
    if risk_flags:
        for label, detail in risk_flags:
            pdf.body_text(_clean(f"{label}: {detail}"))
    else:
        pdf.body_text("No rule-based risk flags triggered on the latest period.")

    # Data quality
    if validation:
        pdf.section_title("Data Quality")
        pdf.body_text(_clean(f"Status: {'Good' if validation['status'] == 'good' else 'Issues Found'}"))
        for c in validation.get("checks", []):
            mark = "OK" if c["passed"] else "FLAG"
            pdf.body_text(_clean(f"[{mark}] {c['name']}: {c['detail']}"))

    return bytes(pdf.output())
