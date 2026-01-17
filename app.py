import streamlit as st
import os
import shutil
from datetime import datetime
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from llm_tools import fetch_user_context, read_training_data, create_and_upload_plan
from garmin_adapter import GarminAdapter

# Load environment variables
load_dotenv()

# Create .env from env.example if .env does not exist
if not os.path.exists(".env") and os.path.exists("env.example"):
    shutil.copy("env.example", ".env")

# Page Config
st.set_page_config(page_title="Garmin AI Coach", page_icon="🏃", layout="wide")

# Title
st.title("🏃 Garmin AI Running Coach")


def check_garmin_connection():
    """Check if we can connect to Garmin and return user info."""
    try:
        adapter = GarminAdapter()
        adapter.login()
        name = adapter.client.get_full_name()
        return True, name
    except Exception as e:
        return False, str(e)


# Initialize session state
if "garmin_connected" not in st.session_state:
    st.session_state.garmin_connected = False
    st.session_state.garmin_user = None

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.header("Settings")
    
    # OpenAI
    st.subheader("OpenAI")
    api_key = st.text_input("API Key", type="password", key="openai_key")
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    
    if os.environ.get("OPENAI_API_KEY"):
        st.success("✓ API Key configured")
    else:
        st.warning("Enter your OpenAI API key")

    # Garmin Connection
    st.subheader("Garmin Connect")
    
    if st.session_state.garmin_connected:
        st.success(f"✓ Connected as {st.session_state.garmin_user}")
    else:
        if st.button("🔗 Connect to Garmin", use_container_width=True):
            with st.spinner("Connecting to Garmin..."):
                success, result = check_garmin_connection()
                if success:
                    st.session_state.garmin_connected = True
                    st.session_state.garmin_user = result
                    st.rerun()
                else:
                    st.error(f"Connection failed: {result}")
        
        st.caption("Click to verify Garmin connection")

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

# Main content
if not st.session_state.garmin_connected:
    st.info("👈 Please connect to Garmin first using the sidebar button.")
elif not os.environ.get("OPENAI_API_KEY"):
    st.info("👈 Please enter your OpenAI API key in the sidebar.")
else:
    # Auto-fetch user context on first load
    if "user_context" not in st.session_state:
        with st.spinner("Fetching your Garmin data..."):
            try:
                # Call the tool function directly (not through the agent)
                context = fetch_user_context.invoke({})
                st.session_state.user_context = context
            except Exception as e:
                st.session_state.user_context = f"Error fetching data: {e}"
    
    # Initialize Agent with user context in system prompt
    if "agent" not in st.session_state:
        tools = [fetch_user_context, read_training_data, create_and_upload_plan]
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
                st.error(f"An error occurred: {e}")
