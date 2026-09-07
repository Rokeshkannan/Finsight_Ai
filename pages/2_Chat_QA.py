import streamlit as st

from utils.claude_client import chat_answer
from utils.ratios import compute_ratios
from utils.session_limit import get_api_key, check_and_consume_quota

st.set_page_config(page_title="Chat Q&A | FinSight AI", page_icon="\U0001F4AC", layout="wide")
st.title("Chat Q&A")

if "extracted_data" not in st.session_state:
    st.warning("No data loaded yet -- go to the main page and choose a data source.")
    st.stop()

api_key, _ = get_api_key()
if not api_key:
    st.warning("Add an Anthropic API key on the main page to use chat.")
    st.stop()

data = st.session_state["extracted_data"]
raw_text = st.session_state.get("raw_text", "")
ratios_df = compute_ratios(data)
st.session_state.setdefault("chat_history", [])

st.caption(f"Ask questions about **{data.get('company_name', 'this company')}**'s statement. "
           "Answers are grounded in the extracted figures and computed ratios.")

for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("e.g. How did profitability change over the last two periods?")
if question:
    st.session_state["chat_history"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if not check_and_consume_quota():
            answer = None
        else:
            with st.spinner("Thinking..."):
                try:
                    answer = chat_answer(
                        api_key=api_key,
                        question=question,
                        raw_text=raw_text,
                        extracted_data=data,
                        ratios=ratios_df.to_dict(),
                        chat_history=st.session_state["chat_history"][:-1],
                    )
                except Exception as e:
                    answer = f"Couldn't reach Claude: {e}"
        if answer:
            st.markdown(answer)

    if answer:
        st.session_state["chat_history"].append({"role": "assistant", "content": answer})
