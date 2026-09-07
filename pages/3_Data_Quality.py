import streamlit as st

from utils.validation import validate_data

st.set_page_config(page_title="Data Quality | FinSight AI", page_icon="\U0001F50D", layout="wide")
st.title("Data Quality")

if "extracted_data" not in st.session_state:
    st.warning("No data loaded yet -- go to the main page and choose a data source.")
    st.stop()

data = st.session_state["extracted_data"]
result = validate_data(data)
st.session_state["validation_result"] = result  # so the Dashboard's report includes it

if result["status"] == "good":
    st.success("✅ Data Quality: Good")
else:
    st.warning("⚠️ Data Quality: Issues Found")

st.divider()
st.subheader("Validation checks")

for check in result["checks"]:
    icon = "✅" if check["passed"] else "❌"
    with st.container():
        st.markdown(f"{icon} **{check['name']}**")
        st.caption(check["detail"])

st.divider()
with st.expander("Raw extracted data"):
    st.json(data)
