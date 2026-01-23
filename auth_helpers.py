import time
from datetime import datetime, timedelta

import streamlit as st

from garmin import attempt_garmin_login
from garmin.adapter import GarminAdapter
from llm_tools import set_adapter
from ui_helpers import friendly_error
from user_storage import (
    save_conversation_by_id,
    get_user_id,
    load_garmin_token_by_id,
    load_conversation_by_id,
    load_garmin_username_by_id,
)


def init_session_state():
    """Ensure required session keys exist with sensible defaults."""
    defaults = {
        "garmin_connected": False,
        "garmin_user": None,
        "awaiting_mfa": False,
        "messages": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def restore_session_from_cookie(cookie_manager):
    """Restore a logged-in session from a stored cookie if possible."""
    if st.session_state.garmin_connected:
        return False

    all_cookies = cookie_manager.get_all()
    print(f"🍪 All cookies: {all_cookies}")
    saved_user_id = cookie_manager.get("garmin_user_id")
    print(f"🍪 Cookie read: garmin_user_id = {saved_user_id}")

    if not saved_user_id:
        return False

    saved_token = load_garmin_token_by_id(saved_user_id)
    saved_username = load_garmin_username_by_id(saved_user_id)
    if not saved_token:
        return False

    try:
        adapter = GarminAdapter(garth_tokens=saved_token)
        adapter.login()
        print(f"✅ Restored session from cookie for user {saved_user_id[:8]}...")
        st.session_state.garmin_connected = True
        st.session_state.garmin_user = saved_username or adapter.client.get_full_name() or "User"
        st.session_state.user_id = saved_user_id
        st.session_state.garmin_adapter = adapter
        set_adapter(adapter)

        saved_messages = load_conversation_by_id(saved_user_id)
        if saved_messages:
            st.session_state.messages = saved_messages
        return True
    except Exception as e:
        print(f"🍪 Cookie restore FAILED: {e}, deleting cookie")
        cookie_manager.delete("garmin_user_id")
        return False


def restore_adapter_from_state():
    """Recover connection from an existing adapter in session state."""
    if st.session_state.garmin_connected:
        return False

    if "garmin_adapter" not in st.session_state or not st.session_state.garmin_adapter:
        return False

    adapter = st.session_state.garmin_adapter
    try:
        st.session_state.garmin_connected = True
        st.session_state.garmin_user = adapter.client.get_full_name()
        set_adapter(adapter)
        return True
    except Exception:
        del st.session_state.garmin_adapter
        st.session_state.garmin_connected = False
        st.session_state.garmin_user = None
        return False


def _set_login_cookie(cookie_manager, user_id):
    """Persist login for future sessions."""
    expire_date = datetime.now() + timedelta(days=30)
    cookie_manager.set("garmin_user_id", user_id, expires_at=expire_date)
    print(f"🍪 Cookie SET: garmin_user_id = {user_id}, expires = {expire_date}")
    time.sleep(0.5)


def render_login_flow(cookie_manager):
    """Render the Garmin login + MFA flow and update session state."""
    st.markdown("### Connect to Garmin")
    st.markdown("Enter your Garmin credentials. If you've logged in before with these credentials, you'll skip 2FA!")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not st.session_state.awaiting_mfa:
            garmin_email = st.text_input(
                "Garmin Email",
                key="garmin_email_input",
                placeholder="your.email@example.com",
            )
            garmin_password = st.text_input(
                "Garmin Password",
                type="password",
                key="garmin_password_input",
            )

            if st.button(
                "🔗 Connect to Garmin",
                use_container_width=True,
                type="primary",
                disabled=not (garmin_email and garmin_password),
            ):
                with st.spinner("Connecting to Garmin..."):
                    success, result, needs_mfa = attempt_garmin_login(garmin_email, garmin_password)
                    if success:
                        st.session_state.garmin_connected = True
                        st.session_state.garmin_user = result
                        user_id = get_user_id(garmin_email, garmin_password)
                        st.session_state.user_id = user_id
                        _set_login_cookie(cookie_manager, user_id)
                        if "garmin_adapter" in st.session_state:
                            set_adapter(st.session_state.garmin_adapter)
                        st.rerun()
                    elif needs_mfa:
                        st.session_state.awaiting_mfa = True
                        st.rerun()
                    else:
                        st.error(f"❌ {friendly_error(result)}")
        else:
            st.info("📧 A 2FA code has been sent to your email. Use the most recent code if you received multiple.")
            mfa_code = st.text_input(
                "Enter 2FA Code",
                key="mfa_code",
                placeholder="123456",
                max_chars=6,
            )

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(
                    "✓ Submit Code",
                    use_container_width=True,
                    type="primary",
                    disabled=not mfa_code,
                ):
                    with st.spinner("Verifying..."):
                        email = st.session_state.get("pending_email", "")
                        password = st.session_state.get("pending_password", "")
                        if not email or not password:
                            st.error("❌ Session expired. Please start over.")
                            st.session_state.awaiting_mfa = False
                            st.rerun()

                        success, result, _ = attempt_garmin_login(email, password, mfa_code=mfa_code)
                        if success:
                            st.session_state.garmin_connected = True
                            st.session_state.garmin_user = result
                            st.session_state.awaiting_mfa = False
                            user_id = get_user_id(email, password)
                            st.session_state.user_id = user_id
                            _set_login_cookie(cookie_manager, user_id)
                            for key in ["pending_email", "pending_password", "pending_adapter"]:
                                if key in st.session_state:
                                    del st.session_state[key]
                            if "garmin_adapter" in st.session_state:
                                set_adapter(st.session_state.garmin_adapter)
                            st.rerun()
                        else:
                            st.error(f"❌ {friendly_error(result)}")
            with col_b:
                if st.button("← Back", use_container_width=True):
                    st.session_state.awaiting_mfa = False
                    for key in ["pending_adapter", "pending_email", "pending_password"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()


def logout_user(cookie_manager):
    """Clear session state and cookies, then rerun."""
    if "user_id" in st.session_state and st.session_state.messages:
        save_conversation_by_id(st.session_state.user_id, st.session_state.messages)

    print("🍪 Cookie DELETE: garmin_user_id (logout)")
    cookie_manager.delete("garmin_user_id")

    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
