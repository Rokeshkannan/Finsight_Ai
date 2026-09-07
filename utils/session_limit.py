"""
Session-level API key resolution and usage capping.

Strategy: if an ANTHROPIC_API_KEY is set in Streamlit secrets (i.e. the app
owner has embedded their own key for a hosted demo), use that automatically
and enforce a per-session cap on how many Claude calls a single visitor can
make. If no secret is configured, fall back to BYOK (the user pastes their
own key in the sidebar) with no cap, since they're paying for their own use.
"""

import streamlit as st

MAX_REQUESTS_PER_SESSION = 10


def _get_secret_key():
    """
    Safely reads ANTHROPIC_API_KEY from Streamlit secrets. Returns None if
    no secrets.toml exists at all (st.secrets raises in that case rather
    than behaving like a normal dict) or if the key just isn't set.
    """
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", None)
    except Exception:
        return None


def get_api_key():
    """
    Returns (api_key, is_shared_key).
    is_shared_key=True means this is the app owner's embedded key, so the
    usage cap applies. False means the user supplied their own key (BYOK),
    so no cap applies -- it's their own cost.
    """
    secret_key = _get_secret_key()
    if secret_key:
        return secret_key, True

    # Fall back to BYOK: sidebar input
    user_key = st.session_state.get("api_key")
    return user_key, False


def render_key_sidebar():
    """
    Renders the sidebar API key UI. Call once from the main page (app.py).
    Shows a usage counter if running on a shared/embedded key; shows a
    password input if the user needs to supply their own.
    """
    secret_key = _get_secret_key()

    if secret_key:
        used = st.session_state.get("request_count", 0)
        remaining = max(0, MAX_REQUESTS_PER_SESSION - used)
        st.sidebar.success("Using the demo's built-in API access.")
        st.sidebar.caption(f"{remaining} of {MAX_REQUESTS_PER_SESSION} AI requests left this session.")
        if remaining == 0:
            st.sidebar.warning("Session limit reached. Refresh the page to reset, "
                                "or add your own Anthropic API key below to continue.")
        with st.sidebar.expander("Use your own key instead"):
            own_key = st.text_input("Anthropic API key", type="password",
                                     value=st.session_state.get("api_key", ""), key="own_key_input")
            if own_key:
                st.session_state["api_key"] = own_key
                st.caption("Your own key will be used instead of the demo's shared access, "
                           "with no session limit.")
    else:
        api_key = st.sidebar.text_input("Anthropic API key", type="password",
                                         value=st.session_state.get("api_key", ""))
        if api_key:
            st.session_state["api_key"] = api_key
        st.sidebar.caption("Your key is only kept in this session and never stored.")


def check_and_consume_quota():
    """
    Call this immediately before making a Claude API call.
    Returns True if the call is allowed to proceed, False if the session cap
    was hit (in which case a message has already been shown to the user).
    Only meaningful when running on the app owner's shared/embedded key --
    BYOK users are never capped.
    """
    api_key, is_shared_key = get_api_key()

    if not api_key:
        st.error("No API key available. Add one in the sidebar.")
        return False

    if not is_shared_key:
        return True  # BYOK: user pays for their own usage, no cap

    used = st.session_state.get("request_count", 0)
    if used >= MAX_REQUESTS_PER_SESSION:
        st.warning(f"You've used all {MAX_REQUESTS_PER_SESSION} free AI requests for this session. "
                   "Refresh the page to reset, or add your own Anthropic API key in the sidebar "
                   "to keep going without a limit.")
        return False

    st.session_state["request_count"] = used + 1
    return True
