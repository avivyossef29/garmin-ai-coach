import streamlit as st
import os
import shutil
from datetime import datetime
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from llm_tools import fetch_user_context, read_training_data, create_and_upload_plan, get_fitness_metrics, set_adapter
from garmin_adapter import GarminAdapter, MFARequiredError

# Load environment variables
load_dotenv()


def friendly_error(error):
    """Convert technical errors to user-friendly messages."""
    error_str = str(error).lower()
    
    if "401" in error_str or "unauthorized" in error_str:
        return "Invalid email or password. Please check your credentials."
    elif "mfa" in error_str or "2fa" in error_str:
        return "Two-factor authentication required."
    elif "timeout" in error_str or "timed out" in error_str:
        return "Connection timed out. Please try again."
    elif "network" in error_str or "connection" in error_str:
        return "Network error. Please check your internet connection."
    elif "rate limit" in error_str or "429" in error_str:
        return "Too many requests. Please wait a moment and try again."
    elif "404" in error_str:
        return "Service temporarily unavailable. Please try again later."
    elif "openai" in error_str or "api_key" in error_str:
        return "OpenAI API key is invalid or missing."
    else:
        # Keep it short - just the first line, no stack trace
        first_line = str(error).split('\n')[0]
        if len(first_line) > 100:
            return first_line[:100] + "..."
        return first_line


# Create .env from env.example if .env does not exist
if not os.path.exists(".env") and os.path.exists("env.example"):
    shutil.copy("env.example", ".env")

# Page Config
st.set_page_config(page_title="Garmin AI Coach", page_icon="🏃", layout="wide")

# Title
st.title("🏃 Garmin AI Running Coach")


def attempt_garmin_login(email, password, mfa_code=None):
    """
    Attempt to login to Garmin.
    
    Returns:
        (success, result, needs_mfa)
        - success: True if login succeeded
        - result: User name on success, error message on failure
        - needs_mfa: True if 2FA code is required
    """
    try:
        adapter = GarminAdapter(email=email, password=password)
        adapter.login(mfa_code=mfa_code)
        name = adapter.client.get_full_name()
        # Store the authenticated adapter for use by llm_tools
        set_adapter(adapter)
        # Store credentials in environment for future use in this session
        os.environ["GARMIN_EMAIL"] = email
        os.environ["GARMIN_PASSWORD"] = password
        return True, name, False
    except MFARequiredError:
        # Store credentials for step 2
        os.environ["GARMIN_EMAIL"] = email
        os.environ["GARMIN_PASSWORD"] = password
        return False, "2FA code required", True
    except Exception as e:
        return False, str(e), False


# Initialize session state
if "garmin_connected" not in st.session_state:
    st.session_state.garmin_connected = False
    st.session_state.garmin_user = None
    st.session_state.awaiting_mfa = False

if "messages" not in st.session_state:
    st.session_state.messages = []

# Check for API key from environment (set once, invisible to user)
if not os.environ.get("OPENAI_API_KEY"):
    # Only show API key input if not configured in .env
    with st.sidebar:
        st.header("⚙️ Setup Required")
        api_key = st.text_input("OpenAI API Key", type="password", key="openai_key", 
                                help="Get your key from platform.openai.com")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            st.rerun()

# Sidebar - Only show status when connected
with st.sidebar:
    if st.session_state.garmin_connected:
        st.success(f"🏃 {st.session_state.garmin_user}")
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            if "agent" in st.session_state:
                del st.session_state.agent
            if "user_context" in st.session_state:
                del st.session_state.user_context
            st.rerun()

SYSTEM_PROMPT = """You are an AI Running Coach that creates personalized, structured training plans.

TODAY'S DATE: {today}

USER'S GARMIN DATA:
{user_context}

TOOLS:
1. fetch_user_context - Refresh Garmin data (summary)
2. read_training_data - Read FULL activity details from saved file
3. create_and_upload_plan - Create STRUCTURED workouts with intervals, pace targets, and repeats

WORKOUT TYPES TO CREATE:
- **Intervals**: Use WorkoutRepeatStep for 5x800m, 6x1000m, etc. with SPEED targets
- **Tempo runs**: Warmup + sustained pace block + cooldown with SPEED targets  
- **Long runs**: Simple distance with easy pace target
- **Easy runs**: Recovery pace, no hard targets

IMPORTANT:
- ALWAYS use structured workouts with steps, NOT just text descriptions
- Use suggested_zones speed values (m/s) for targetValueOne/Two
- Include WARMUP and COOLDOWN in every workout
- Use WorkoutRepeatStep for interval sessions
- Calculate weeks until race and adjust intensity accordingly
- Call create_and_upload_plan(confirmed=false) to preview, then confirmed=true after user approves
"""

# Main content - Connection flow
if not os.environ.get("OPENAI_API_KEY"):
    st.info("👈 Please enter your OpenAI API key in the sidebar to get started.")
elif not st.session_state.garmin_connected:
    # Garmin Connection UI - Main area (not sidebar)
    st.markdown("### Connect to Garmin")
    st.markdown("To create personalized workouts, we need to connect to your Garmin account.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Step 1: Email/Password
        if not st.session_state.awaiting_mfa:
            garmin_email = st.text_input("Garmin Email", key="garmin_email", 
                                          placeholder="your.email@example.com")
            garmin_password = st.text_input("Garmin Password", type="password", key="garmin_password")
            
            if st.button("🔗 Connect to Garmin", use_container_width=True, type="primary", 
                         disabled=not (garmin_email and garmin_password)):
                with st.spinner("Connecting to Garmin..."):
                    success, result, needs_mfa = attempt_garmin_login(garmin_email, garmin_password)
                    if success:
                        st.session_state.garmin_connected = True
                        st.session_state.garmin_user = result
                        st.rerun()
                    elif needs_mfa:
                        st.session_state.awaiting_mfa = True
                        st.rerun()
                    else:
                        st.error(f"❌ {friendly_error(result)}")
        
        # Step 2: 2FA Code
        else:
            st.info("📧 A 2FA code has been sent to your email.")
            mfa_code = st.text_input("Enter 2FA Code", key="mfa_code", 
                                      placeholder="123456", max_chars=6)
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✓ Submit Code", use_container_width=True, type="primary",
                             disabled=not mfa_code):
                    with st.spinner("Verifying..."):
                        email = os.environ.get("GARMIN_EMAIL", "")
                        password = os.environ.get("GARMIN_PASSWORD", "")
                        success, result, _ = attempt_garmin_login(email, password, mfa_code=mfa_code)
                        if success:
                            st.session_state.garmin_connected = True
                            st.session_state.garmin_user = result
                            st.session_state.awaiting_mfa = False
                            st.rerun()
                        else:
                            st.error(f"❌ Invalid code. Please check and try again.")
            with col_b:
                if st.button("← Back", use_container_width=True):
                    st.session_state.awaiting_mfa = False
                    st.rerun()
else:
    # Auto-fetch user context on first load
    if "user_context" not in st.session_state:
        with st.spinner("Fetching your Garmin data..."):
            try:
                # Call the tool function directly (not through the agent)
                context = fetch_user_context.invoke({})
                st.session_state.user_context = context
            except Exception as e:
                st.session_state.user_context = f"Could not load Garmin data: {friendly_error(e)}"
    
    # Initialize Agent with user context in system prompt
    if "agent" not in st.session_state:
        tools = [fetch_user_context, read_training_data, get_fitness_metrics, create_and_upload_plan]
        today = datetime.now().strftime("%Y-%m-%d")
        populated_prompt = SYSTEM_PROMPT.format(
            today=today,
            user_context=st.session_state.user_context
        )
        st.session_state.agent = create_agent(
            "openai:gpt-4o",  # Using smarter model
            tools=tools,
            system_prompt=populated_prompt,
        )
        
        # Generate initial greeting with user summary
        if len(st.session_state.messages) == 0:
            with st.spinner("Analyzing your training data..."):
                try:
                    intro_response = st.session_state.agent.invoke({
                        "messages": [HumanMessage(content="""Introduce yourself briefly as an AI Running Coach, then summarize what you know about me:
- Name
- Training goal (race name, date, level)
- Race predictions (5K, 10K, Half, Marathon paces)
- Lactate threshold
- Recent training summary
- Suggested training zones

Keep it concise but complete. End by asking: "Is there anything else I should know about you before we start planning? (e.g., injuries, schedule constraints, preferences) If not, just let me know how I can help with your training!"
""")]
                    })
                    intro_message = intro_response["messages"][-1].content
                    st.session_state.messages.append({"role": "assistant", "content": intro_message})
                except Exception as e:
                    # Fallback greeting
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": "👋 Hi! I'm your AI Running Coach. I've analyzed your Garmin data and I'm ready to help you train. Is there anything I should know about you before we start planning? If not, let me know how I can help!"
                    })

    # Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("How can I help with your training today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                chat_history = []
                for msg in st.session_state.messages:
                    if msg["role"] == "user":
                        chat_history.append(HumanMessage(content=msg["content"]))
                    else:
                        chat_history.append(AIMessage(content=msg["content"]))

                with st.spinner("Thinking..."):
                    response = st.session_state.agent.invoke(
                        {"messages": chat_history}
                    )

                output = response["messages"][-1].content
                st.markdown(output)
                st.session_state.messages.append({"role": "assistant", "content": output})
            except Exception as e:
                st.error(f"❌ {friendly_error(e)}")
