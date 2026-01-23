import os
import shutil

import extra_streamlit_components as stx
import streamlit as st
from dotenv import load_dotenv

from auth_helpers import (
    init_session_state,
    restore_session_from_cookie,
    restore_adapter_from_state,
    render_login_flow,
    logout_user,
)
from chat_helpers import run_chat_ui
from config import SYSTEM_PROMPT, DEV_MODE
from llm_tools import (
    fetch_user_context,
    read_training_data,
    create_and_upload_plan,
    get_fitness_metrics,
    get_sidebar_stats,
)
from ui_helpers import render_sidebar, friendly_error

load_dotenv()


if not os.path.exists(".env") and os.path.exists("env.example"):
    shutil.copy("env.example", ".env")

st.set_page_config(page_title="Garmin AI Coach", page_icon="🏃", layout="wide")

st.markdown("""
<style>
    /* Main content text */
    .stMarkdown, .stText, p, li {
        font-size: 1.1rem !important;
    }
    
    /* Chat messages */
    .stChatMessage p {
        font-size: 1.15rem !important;
        line-height: 1.6 !important;
    }
    
    /* Input fields */
    .stTextInput input, .stTextArea textarea {
        font-size: 1.1rem !important;
    }
    
    /* Buttons */
    .stButton button {
        font-size: 1.1rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏃 Garmin AI Running Coach")

cookie_manager = stx.CookieManager(key="garmin_cookies")

init_session_state()
restore_session_from_cookie(cookie_manager)
restore_adapter_from_state()

api_ready = render_sidebar(get_sidebar_stats, lambda: logout_user(cookie_manager))

if not api_ready:
    st.info("👈 Please enter your OpenAI API key in the sidebar to get started.")
elif not st.session_state.garmin_connected:
    render_login_flow(cookie_manager)
else:
    tools = [fetch_user_context, read_training_data, get_fitness_metrics, create_and_upload_plan]
    run_chat_ui(
        system_prompt=SYSTEM_PROMPT,
        dev_mode=DEV_MODE,
        tools=tools,
        friendly_error=friendly_error,
    )

