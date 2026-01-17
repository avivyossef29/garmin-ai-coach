import streamlit as st
import os
import shutil
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from llm_tools import fetch_user_context, save_generated_plan, execute_upload_plan
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

SYSTEM_PROMPT = """You are an expert AI Running Coach. Your goal is to help the user achieve their running goals by managing their Garmin training plan.

You have access to tools that interact with the user's Garmin account.

### WORKFLOW:
1. **Context**: When starting or if requested, call `fetch_user_context` to understand the user's profile, recent activities, and goals.
2. **Analysis**: Analyze the user's recent load (distance, pace) vs. their goal.
3. **Planning**: 
   - When asked to create a plan, design a weekly schedule (Mon-Sun).
   - Use your knowledge of running science (periodization, 80/20 rule, tapering).
   - Calculate specific paces based on the user's recent data or goal pace.
   - Create the plan JSON.
   - Call `save_generated_plan` with the JSON string.
4. **Execution**: 
   - After saving, SUMMARIZE the plan to the user.
   - ASK for explicit confirmation to upload.
   - If confirmed, call `execute_upload_plan`.

### JSON PLAN FORMAT:
The JSON for `save_generated_plan` must be a list of objects:
[
  {
    "workoutName": "W1_Mon_Easy",
    "scheduleDate": "YYYY-MM-DD",
    "description": "8km Easy run",
    "steps": [
       {
         "type": "WorkoutStep",
         "intensity": "ACTIVE",  // WARMUP, ACTIVE, COOLDOWN, INTERVAL, RECOVERY, REST
         "durationType": "DISTANCE", // or TIME
         "durationValue": 8000, // meters or seconds
         "targetType": "SPEED", // or NONE
         "targetValueOne": 2.9, // m/s (min speed)
         "targetValueTwo": 3.1  // m/s (max speed)
       }
    ]
  }
]

### PACING:
- Convert paces (min/km) to m/s: Speed = 1000 / (min*60 + sec).
- Always set targetValueOne < targetValueTwo.
"""

# Main content
if not st.session_state.garmin_connected:
    st.info("👈 Please connect to Garmin first using the sidebar button.")
elif not os.environ.get("OPENAI_API_KEY"):
    st.info("👈 Please enter your OpenAI API key in the sidebar.")
else:
    # Initialize Agent
    if "agent" not in st.session_state:
        tools = [fetch_user_context, save_generated_plan, execute_upload_plan]
        st.session_state.agent = create_agent(
            "openai:gpt-4o-mini",
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
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
