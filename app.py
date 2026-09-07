"""
FinSight AI -- main entry point.

Handles: API key input, choosing a data source (upload a statement or use
sample data), running extraction, and stashing the result in session_state
so the Dashboard and Chat Q&A pages can use it.
"""

import json
import streamlit as st

from utils.parser import parse_file, truncate_for_context
from utils.claude_client import extract_financials
from utils.ratios import compute_ratios
from utils.session_limit import get_api_key, render_key_sidebar, check_and_consume_quota

st.set_page_config(page_title="FinSight AI", page_icon="\U0001F4CA", layout="wide")

st.title("\U0001F4CA FinSight AI")
st.caption("Upload a financial statement (PDF / Excel / CSV) or explore sample data. "
           "Get an instant ratio dashboard and ask questions in plain English.")

# ---- API key ----
with st.sidebar:
    st.header("Setup")
    render_key_sidebar()

    st.divider()
    st.header("Data source")
    source_mode = st.radio("Choose a source", ["Use sample data", "Upload a statement"])

# ---- Data source handling ----
if source_mode == "Use sample data":
    with open("sample_data/sample_company.json") as f:
        extracted = json.load(f)
    st.session_state["extracted_data"] = extracted
    st.session_state["raw_text"] = f"[Sample data for {extracted['company_name']}]"
    st.session_state["chat_history"] = st.session_state.get("chat_history", [])
    st.success(f"Loaded sample data: **{extracted['company_name']}**")

else:
    uploaded_files = st.file_uploader(
        "Upload one or more statements (e.g. balance sheet, income statement, cash flow)",
        type=["pdf", "xlsx", "xls", "csv"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        api_key, _ = get_api_key()
        if not api_key:
            st.warning("Add an Anthropic API key in the sidebar first -- "
                       "extraction from PDFs/Excel uses Claude to structure the data.")
        elif not check_and_consume_quota():
            pass  # message already shown by check_and_consume_quota
        else:
            combined_chunks = []
            parse_errors = []
            with st.spinner(f"Parsing {len(uploaded_files)} file(s)..."):
                for f in uploaded_files:
                    try:
                        parsed = parse_file(f)
                        combined_chunks.append(f"===== {f.name} =====\n{parsed['raw_text']}")
                    except Exception as e:
                        parse_errors.append(f"{f.name}: {e}")

            for err in parse_errors:
                st.error(f"Couldn't parse {err}")

            if combined_chunks:
                raw_text = truncate_for_context("\n\n".join(combined_chunks), max_chars=30000)

                with st.spinner("Extracting financial figures with Claude..."):
                    try:
                        extracted = extract_financials(api_key, raw_text)
                    except Exception as e:
                        st.error(f"Claude API error while extracting data: {e}\n\n"
                                 "Common causes: invalid/expired API key, no billing set up, "
                                 "or a workspace-scoped key issue. Check your key in "
                                 "platform.claude.com \u2192 Settings \u2192 API keys.")
                        extracted = None

                if extracted is None:
                    pass
                elif not extracted or not extracted.get("periods"):
                    st.error("Couldn't confidently extract structured figures from these files. "
                              "Try cleaner exports, or use sample data to explore the app.")
                else:
                    st.session_state["extracted_data"] = extracted
                    st.session_state["raw_text"] = raw_text
                    st.session_state["chat_history"] = []
                    names = ", ".join(f.name for f in uploaded_files)
                    st.success(f"Extracted data for **{extracted.get('company_name', names)}** "
                               f"from {len(uploaded_files)} file(s): {names}")

# ---- Landing content ----
if "extracted_data" in st.session_state:
    st.info("Head to **Dashboard** for ratios and trends, or **Chat Q&A** to ask questions "
            "about this statement -- use the page menu in the sidebar.")

    with st.expander("Preview extracted data"):
        st.json(st.session_state["extracted_data"])
else:
    st.info("Choose a data source in the sidebar to get started.")
