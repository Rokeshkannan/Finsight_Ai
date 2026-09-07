"""
Thin wrapper around the Anthropic API for FinSight AI.

Three jobs:
  1. extract_financials()  -> pull key line items out of raw statement text as JSON
  2. generate_summary()    -> a plain-English narrative summary of the statement
  3. chat_answer()         -> answer a free-form question about the statement
"""

import json
import re
import anthropic

MODEL = "claude-sonnet-4-5"  # swap for whichever Claude model your API key has access to

EXTRACTION_SYSTEM_PROMPT = """You are a financial analyst assistant. You will be given raw text \
extracted from a company's financial statement (income statement, balance sheet, and/or cash \
flow statement). Extract the key line items you can find and return ONLY a JSON object, with no \
preamble, no markdown fences, and no commentary.

If the statement covers multiple periods/years, include all of them. If a figure isn't present, \
omit that key rather than guessing. Use this schema (all values are numbers in the statement's \
original currency/units, keys omitted if not found):

{
  "company_name": "string or null",
  "currency_or_units": "string or null, e.g. 'USD millions'",
  "periods": ["2023", "2022"],
  "income_statement": {
    "revenue": {"2023": 0, "2022": 0},
    "cost_of_goods_sold": {},
    "gross_profit": {},
    "operating_expenses": {},
    "operating_income": {},
    "net_income": {}
  },
  "balance_sheet": {
    "total_assets": {},
    "current_assets": {},
    "current_liabilities": {},
    "total_liabilities": {},
    "total_equity": {},
    "cash_and_equivalents": {},
    "inventory": {}
  },
  "cash_flow": {
    "operating_cash_flow": {},
    "investing_cash_flow": {},
    "financing_cash_flow": {}
  }
}
"""

SUMMARY_SYSTEM_PROMPT = """You are FinSight AI, a financial analysis assistant.

You are provided with financial statement data, KPIs, a financial health score, risk flags, and \
variance analysis that have already been calculated by a Python-based financial analysis engine.

Do not invent financial figures. Do not recalculate numerical values unless necessary for \
explanation. Base every insight only on the provided data.

Explain financial concepts in simple business language. Cover, where the data supports it:
1. Overall financial position
2. Liquidity position
3. Leverage/debt position
4. Asset growth
5. Liability growth
6. Equity strength
7. Major positive trends
8. Major risks
9. Areas management should monitor
10. Overall interpretation

Clearly distinguish between observed facts, interpretation, and potential risks. If required data \
is missing, explicitly state that the conclusion cannot be determined from the available \
information. Write 250-350 words, avoid jargon where possible, and do not repeat raw numbers \
exhaustively -- focus on what they mean."""

CHAT_SYSTEM_PROMPT = """You are FinSight AI, a financial statement analysis assistant. Answer the \
user's question using ONLY the financial statement context and computed ratios provided below. \
If the answer isn't in the data, say so plainly rather than guessing. Keep answers concise and \
grounded in the numbers -- cite specific figures when relevant."""


def _get_client(api_key):
    return anthropic.Anthropic(api_key=api_key)


def _strip_json_fences(text):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def extract_financials(api_key, raw_text):
    """Returns a parsed dict of extracted financial line items, or {} on failure."""
    client = _get_client(api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": raw_text}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(_strip_json_fences(text))
    except json.JSONDecodeError:
        return {}


def generate_summary(api_key, extracted_data, ratios, health_score=None, risk_flags=None,
                      variance_highlights=None):
    client = _get_client(api_key)
    context = f"Extracted financial data:\n{json.dumps(extracted_data, indent=2)}\n\n" \
              f"Computed ratios:\n{json.dumps(ratios, indent=2)}"
    if health_score:
        context += f"\n\nFinancial health score:\n{json.dumps(health_score, indent=2)}"
    if risk_flags:
        flags_text = "\n".join(f"- {label}: {detail}" for label, detail in risk_flags)
        context += f"\n\nRisk flags:\n{flags_text}"
    if variance_highlights:
        context += "\n\nVariance highlights:\n" + "\n".join(f"- {h}" for h in variance_highlights)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def chat_answer(api_key, question, raw_text, extracted_data, ratios, chat_history):
    """
    chat_history: list of {"role": "user"|"assistant", "content": str} from prior turns
    """
    client = _get_client(api_key)
    context = (
        f"STATEMENT TEXT (may be truncated):\n{raw_text}\n\n"
        f"EXTRACTED FIGURES:\n{json.dumps(extracted_data, indent=2)}\n\n"
        f"COMPUTED RATIOS:\n{json.dumps(ratios, indent=2)}"
    )
    messages = [{"role": "user", "content": f"Context:\n{context}"}]
    messages.append({"role": "assistant", "content": "Understood, I have the statement context."})
    messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=CHAT_SYSTEM_PROMPT,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")
