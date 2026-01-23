"""
Garmin authentication and login flow.
Handles login with token persistence and 2FA.
"""

import logging
import streamlit as st
from .adapter import GarminAdapter, MFARequiredError
from config import DEV_MODE
from user_storage import (
    save_garmin_token, load_garmin_token,
    load_conversation, get_user_id
)

logger = logging.getLogger(__name__)


def _log(level, message):
    if DEV_MODE:
        logger.log(level, message)

def _handle_successful_login(adapter, email, password):
    """Handle successful login: save tokens and username, load conversation."""
    name = adapter.client.get_full_name()
    user_id = get_user_id(email, password)
    
    # Save tokens and username for next time
    tokens = adapter.get_tokens()
    if tokens:
        save_garmin_token(email, password, tokens, username=name)
    
    # Store in session state
    st.session_state.garmin_adapter = adapter
    st.session_state.garmin_email = email
    st.session_state.garmin_password = password
    st.session_state.user_id = user_id
    
    # Load previous conversation
    previous_messages = load_conversation(email, password)
    if previous_messages:
        st.session_state.messages = previous_messages
    
    return True, name, False


def attempt_garmin_login(email, password, mfa_code=None):
    """
    Attempt to login to Garmin, trying saved tokens first.
    
    Flow:
    1. Check if token exists for hash(email+password)
    2. If exists and valid: connected without 2FA!
    3. If not exists or expired: fresh login with 2FA
    
    Returns:
        (success, result, needs_mfa)
        - success: True if login succeeded
        - result: User name on success, error message on failure
        - needs_mfa: True if 2FA code is required
    """
    adapter = None
    
    try:
        # 1. Try saved tokens first (skip 2FA if tokens still valid)
        if not mfa_code and "pending_adapter" not in st.session_state:
            saved_tokens = load_garmin_token(email, password)
            if saved_tokens:
                _log(logging.INFO, "Found saved token for user, attempting restore...")
                adapter = GarminAdapter(email=email, password=password, garth_tokens=saved_tokens)
                adapter.login()
                _log(logging.INFO, "Token restore successful!")
                return _handle_successful_login(adapter, email, password)
        
        # 2. MFA continuation (reuse pending adapter from step 1)
        if mfa_code and "pending_adapter" in st.session_state:
            adapter = st.session_state.pending_adapter
            adapter.login(mfa_code=mfa_code)
            del st.session_state.pending_adapter
            return _handle_successful_login(adapter, email, password)
        
        # 3. Fresh login (no saved tokens)
        _log(logging.INFO, "No saved token found, starting fresh login...")
        adapter = GarminAdapter(email=email, password=password)
        adapter.login(mfa_code=mfa_code)
        return _handle_successful_login(adapter, email, password)
        
    except MFARequiredError:
        # Store adapter and credentials for MFA step 2
        st.session_state.pending_adapter = adapter
        st.session_state.pending_email = email
        st.session_state.pending_password = password
        return False, "2FA code required", True
    
    except Exception as e:
        _log(logging.ERROR, f"Login failed: {e}")
        return False, str(e), False
