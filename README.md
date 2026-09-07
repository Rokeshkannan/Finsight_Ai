# 📊 FinSight AI — AI-Powered Financial Statement Analyzer

FinSight AI turns a raw financial statement (balance sheet, income statement, cash flow — PDF,
Excel, or CSV) into an instant ratio dashboard, a transparent financial health score, and a
plain-English chat interface — while keeping every number Python-calculated and reproducible.

---

## Why I built this

Coming from an FMCG sales & analytics background (ITC Limited), I spent a lot of time working
with distributor and outlet numbers, but not with formal financial statement analysis. This
project was my way of learning that domain hands-on — balance sheets, P&L, cash flow, and the
ratios analysts use to judge a company's health — while also building something that shows how
Generative AI should actually be used in an analytics product: **not as a black box that "does
everything," but as a narrator sitting on top of a deterministic calculation engine.**

That distinction is the core design decision in this project, and it's deliberate:

- **Python calculates.** Every ratio, growth rate, and health-score sub-score comes from a
  transparent, rule-based formula in plain Python/pandas. Nothing here is an LLM guessing at
  arithmetic.
- **Claude explains.** The Claude API is only used for (1) turning messy uploaded text into
  structured numbers, and (2) writing a narrative summary and answering follow-up questions —
  always grounded in the numbers Python already computed, never inventing its own.

I think this separation matters in an interview: it's the difference between "I called an LLM
API" and "I designed a system where AI and deterministic logic each do the job they're actually
good at."

---

## What it does

1. **Upload** a balance sheet, income statement, and/or cash flow statement (PDF / Excel / CSV,
   multiple files at once) — or use the built-in sample company to explore without uploading
   anything.
2. **Extract** — Claude reads the raw text and returns a structured JSON schema (revenue, assets,
   liabilities, equity, cash flows, per period).
3. **Validate** — before any calculation, the data is checked: does Assets = Liabilities + Equity?
   Are core fields present? Any unexpected negatives or suspiciously static values?
4. **Calculate** — a pure-Python engine computes liquidity, leverage, and profitability ratios,
   working capital, and year-over-year variance across every period.
5. **Score** — a transparent 0–100 Financial Health Score, broken into four rule-based
   sub-scores (Liquidity, Leverage, Asset Growth, Equity Strength), with the exact threshold
   logic visible in code.
6. **Flag risks** — rule-based checks surface liquidity risk, high leverage, negative margins,
   negative cash flow, liabilities outpacing assets, and equity deterioration.
7. **Explain** — Claude writes a narrative summary of what the numbers mean, and answers
   follow-up questions in a chat interface, using only the already-calculated data as context.
8. **Export** — download a PDF report with everything above in one document.

---

## Architecture

```
finsight-ai/
├── app.py                        # Landing page: API key setup, data source selection
├── pages/
│   ├── 1_Dashboard.py            # Health score, ratios, trends, variance, risks, AI summary
│   ├── 2_Chat_QA.py              # Chat interface grounded in extracted data
│   └── 3_Data_Quality.py         # Validation checks (accounting equation, missing data, etc.)
├── utils/
│   ├── parser.py                 # PDF / Excel / CSV → raw text
│   ├── claude_client.py          # All Claude API calls: extraction, summary, chat
│   ├── validation.py             # Rule-based data quality checks
│   ├── ratios.py                 # Ratio engine + YoY variance analysis + risk flags
│   ├── scoring.py                # Financial Health Score engine (rule-based, 0–100)
│   ├── report_generator.py       # PDF report generation (fpdf2)
│   └── session_limit.py          # API key resolution (BYOK vs. shared key) + usage cap
├── sample_data/                  # Sample company + test statement files
├── .streamlit/secrets.toml.example
└── requirements.txt
```

**Data flow:** Upload → `parser.py` (raw text) → `claude_client.extract_financials()`
(structured JSON) → `validation.py` (quality checks) → `ratios.py` + `scoring.py` (all numbers)
→ Dashboard renders charts/tables directly from those numbers → `claude_client.generate_summary()`
/ `chat_answer()` receive the *already-computed* numbers as context and only add narrative.

---

## Financial formulas used

| Category | Ratio | Formula |
|---|---|---|
| Liquidity | Current Ratio | Current Assets ÷ Current Liabilities |
| Liquidity | Quick Ratio | (Current Assets − Inventory) ÷ Current Liabilities |
| Liquidity | Cash Ratio | Cash & Equivalents ÷ Current Liabilities |
| Liquidity | Working Capital | Current Assets − Current Liabilities |
| Leverage | Debt-to-Equity | Total Liabilities ÷ Total Equity |
| Leverage | Debt-to-Assets | Total Liabilities ÷ Total Assets |
| Profitability | Gross / Operating / Net Margin | Respective profit line ÷ Revenue |
| Profitability | Return on Equity | Net Income ÷ Total Equity |
| Profitability | Return on Assets | Net Income ÷ Total Assets |
| Efficiency | Operating Cash Flow Margin | Operating Cash Flow ÷ Revenue |
| Growth | YoY Variance | (Current Period − Prior Period) ÷ \|Prior Period\| × 100 |

---

## Financial Health Score methodology

The overall score (0–100) is the average of four category sub-scores, each computed from a
documented threshold table (see `utils/scoring.py` for exact cutoffs):

- **Liquidity** — based on latest Current Ratio (e.g. ≥2.0 → 100, <0.75 → 15)
- **Leverage** — based on latest Debt-to-Equity (e.g. ≤0.5 → 100, >2.5 → 10)
- **Asset Growth** — based on latest YoY growth in Total Assets
- **Equity Strength** — based on latest YoY growth in Total Equity

A category is excluded from the average (not penalized) if its underlying data is missing —
so a statement without cash flow data still gets a fair score from what is available. **This
score is never generated by the AI model** — Claude only narrates it afterward.

---

## Why AI insights might not appear for an uploaded file

This is the most common thing to hit when testing, so worth explaining clearly:

**Extraction from an uploaded PDF/Excel/CSV, the AI narrative summary, and the chat Q&A all
require a live Claude API call** — because turning inconsistent real-world statement formats
into clean structured numbers isn't reliably done with fixed parsing rules, so the app asks
Claude to do that step. That means:

1. **You need an Anthropic API key.** Get one at [platform.claude.com](https://platform.claude.com)
   → Settings → API Keys.
2. **The key's workspace needs a positive credit balance.** The Claude API is billed separately
   from any claude.ai subscription — a key with ₹0/$0 credit will fail with a
   `credit balance too low` error even though the key itself is valid.
3. **If nothing is uploaded — or you choose "Use sample data"** — none of this applies. The
   dashboard, ratios, health score, and risk flags all run entirely offline on the bundled
   sample dataset, since those are pure Python calculations with zero API dependency.

**In short:** if AI insights aren't showing for an uploaded file, check (in order) — is a valid
key entered, does that key's workspace have credit, and does the sidebar confirm which mode
(shared key vs. your own key) is active. The **Data Quality** page and the ratio-only parts of
the **Dashboard** will work regardless, since they don't touch the API at all.

This repo ships in **BYOK (Bring Your Own Key) mode** — each user supplies their own API key —
specifically so it can be shared publicly on GitHub without any cost or liability to me as the
project owner. See `utils/session_limit.py` if you want to run your own hosted demo with an
embedded key and a session-level usage cap instead.

---

## Tech stack

- **Frontend:** Streamlit + Plotly
- **AI:** Claude API (Anthropic) — extraction, narrative summary, chat
- **Data processing:** pandas, pdfplumber, openpyxl
- **Report export:** fpdf2

---

## Installation & running locally

```bash
git clone <your-repo-url>
cd finsight-ai
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Choose **"Use sample data"** in the sidebar to explore
immediately with zero setup, or **"Upload a statement"** and paste your own Anthropic API key
in the sidebar to test extraction on a real file.

### Environment variables / secrets (optional)

To run your own hosted demo where visitors don't need to supply a key, copy
`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add:

```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

This file is gitignored — never commit a real key. When present, the app uses it automatically
for all visitors with a per-session request cap (`MAX_REQUESTS_PER_SESSION` in
`utils/session_limit.py`).

---

## Future improvements

- Support for more statement formats (XBRL, scanned/OCR PDFs)
- Multi-company comparison view
- Additional ratios (inventory turnover, receivables days, interest coverage)
- Editable extracted data (manual correction before ratio calculation)
- Persistent history of analyzed companies

---

## Author

Rokeshkannan P — Data/Business Analyst transitioning from FMCG Sales & Analytics
(ITC Limited) into data analytics.
[GitHub](https://github.com/Rokeshkannan) · [LinkedIn](https://linkedin.com/in/rokeshkannan) ·
[Portfolio](https://rokeshkannanportfolio.lovable.app)
