"""
File parsing utilities.

Turns an uploaded PDF, Excel, or CSV financial statement into:
  1. raw_text  -> a plain-text rendering used as context for Claude (summary + chat)
  2. tables    -> a list of pandas DataFrames, used to look for numeric line items
"""

import io
import pandas as pd
import pdfplumber


def parse_file(uploaded_file):
    """
    uploaded_file: a Streamlit UploadedFile (has .name and read()-able bytes)
    Returns: dict with keys "raw_text" (str) and "tables" (list[pd.DataFrame])
    """
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return _parse_pdf(uploaded_file)
    elif name.endswith((".xlsx", ".xls")):
        return _parse_excel(uploaded_file)
    elif name.endswith(".csv"):
        return _parse_csv(uploaded_file)
    else:
        raise ValueError(f"Unsupported file type: {uploaded_file.name}")


def _parse_pdf(uploaded_file):
    text_chunks = []
    tables = []

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)

            for raw_table in page.extract_tables():
                if not raw_table or len(raw_table) < 2:
                    continue
                try:
                    df = pd.DataFrame(raw_table[1:], columns=raw_table[0])
                    tables.append(df)
                except Exception:
                    continue

    return {"raw_text": "\n".join(text_chunks), "tables": tables}


def _parse_excel(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    tables = []
    text_chunks = []

    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)
        if df.empty:
            continue
        tables.append(df)
        text_chunks.append(f"--- Sheet: {sheet_name} ---\n{df.to_string(index=False)}")

    return {"raw_text": "\n\n".join(text_chunks), "tables": tables}


def _parse_csv(uploaded_file):
    df = pd.read_csv(uploaded_file)
    return {"raw_text": df.to_string(index=False), "tables": [df]}


def truncate_for_context(raw_text, max_chars=15000):
    """Keep the Claude prompt a sane size. Simple char-based truncation."""
    if len(raw_text) <= max_chars:
        return raw_text
    return raw_text[:max_chars] + "\n...[truncated]..."
