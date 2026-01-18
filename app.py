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
    elif "name resolution" in error_str or "failed to resolve" in error_str:
        return "Network error. Please check your internet connection and try again."
    elif "connectionerror" in error_str or "connection" in error_str:
        return "Network error. Please check your internet connection."
    elif "rate limit" in error_str or "429" in error_str:
        return "Too many requests. Please wait a moment and try again."
    elif "404" in error_str:
        return "Service temporarily unavailable. Please try again later."
    elif "openai" in error_str or "api_key" in error_str:
        return "OpenAI API key is invalid or missing."
    elif "invalid" in error_str and "code" in error_str:
        return "Invalid 2FA code. Please check and try again."
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

# Custom CSS for bigger fonts
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
        # Reuse existing adapter for MFA step (same session required!)
        if mfa_code and "pending_adapter" in st.session_state:
            adapter = st.session_state.pending_adapter
            adapter.login(mfa_code=mfa_code)
        else:
            adapter = GarminAdapter(email=email, password=password)
            adapter.login(mfa_code=mfa_code)
        
        name = adapter.client.get_full_name()
        # Store the authenticated adapter in session state and for use by llm_tools
        st.session_state.garmin_adapter = adapter
        set_adapter(adapter)
        # Clean up pending adapter
        if "pending_adapter" in st.session_state:
            del st.session_state.pending_adapter
        return True, name, False
    except MFARequiredError:
        # Store adapter for MFA step 2 (must reuse same session!)
        st.session_state.pending_adapter = adapter
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

# Check for existing adapter in session state and restore if valid
if "garmin_adapter" in st.session_state and st.session_state.garmin_adapter:
    adapter = st.session_state.garmin_adapter
    # Verify session is still valid by testing a simple API call
    try:
        adapter.client.get_full_name()
        # Session is valid - restore connection
        st.session_state.garmin_connected = True
        st.session_state.garmin_user = adapter.client.get_full_name()
        set_adapter(adapter)  # Sync to llm_tools
    except:
        # Session expired - clear it and redirect to login
        del st.session_state.garmin_adapter
        st.session_state.garmin_connected = False
        st.session_state.garmin_user = None

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

SYSTEM_PROMPT = """You are an AI Running Coach with access to the user's Garmin data.

TODAY'S DATE: {today}

USER'S GARMIN DATA:
{user_context}

TRAINING PHILOSOPHY - Follow a structured, phased approach:

**PHASE-BASED TRAINING STRUCTURE:**
1. **Initial Phase** (Base Building):
   - Focus on building aerobic base with easy runs
   - Gradual volume increase (10% rule max)
   - Emphasize consistency over intensity
   - Establish natural running rhythm

2. **Progression Phase** (Building Fitness):
   - Introduce structured workouts gradually
   - Mix easy runs (80%) with quality sessions (20%)
   - Progressive overload: increase volume/intensity gradually
   - Include variety: intervals, tempo, long runs

3. **Taper Phase** (Race Preparation):
   - Reduce volume 2-3 weeks before race
   - Maintain intensity but reduce frequency
   - Focus on recovery and freshness
   - Race-specific pace work

4. **Recovery Phase** (Post-Race/Rest):
   - Active recovery with easy runs
   - Allow body to adapt and rebuild
   - Prevent overtraining and injury

**CORE PRINCIPLES:**
- **Natural Rhythm**: Respect the body's natural adaptation process
- **Gradual Progress**: Avoid sudden jumps in volume or intensity
- **Resilience**: Build durability through consistent, smart training
- **Injury Prevention**: Prioritize recovery, mobility, and strength work
- **Individualization**: Adapt plans based on user's fitness, schedule, and goals

**WORKOUT DISTRIBUTION:**
- 80% easy/conversational pace runs
- 20% quality sessions (intervals, tempo, threshold)
- Include rest days and recovery weeks
- Progressive overload with deload weeks

**COACHING STYLE - BE PROACTIVE AND ENGAGING:**
- **Ask clarifying questions** before creating plans, but ONLY if the information is NOT already available in the Garmin data:
  * Check Garmin data first: race dates (from upcoming_races), training frequency (from recent_runs), experience level (from race predictions)
  * Only ask if information is missing:
    - "Do you have any current injuries or limitations I should know about?" (if not mentioned)
    - "What time of day do you prefer to run? (morning/evening)" (not in Garmin data)
    - "Are there specific days that work better for long runs or quality sessions?" (not in Garmin data)
    - "Do you do any cross-training or strength work?" (not in Garmin data)
  * If race date/goal, training frequency, or experience level are missing from Garmin data, ask:
    - "What's your target race date and goal time?"
    - "How many days per week can you realistically run?"
    - "What's your experience level? (beginner/intermediate/advanced)"

YOU CAN HELP WITH:
- **Training Analysis**: "How did my week go?", "Am I training too hard?"
- **Fitness Insights**: "What's my VO2max?", "Am I recovered enough to train hard today?"
- **Workout Planning**: Create single workouts or full training weeks following the phased approach
- **Race Preparation**: Taper plans, race-day pacing, goal setting
- **General Coaching**: Answer training questions, explain concepts
- **Phase Planning**: Create multi-week plans with proper progression through Initial → Progression → Taper phases

TOOLS:
1. fetch_user_context - Refresh Garmin data (profile, goals, recent runs)
2. read_training_data - Get detailed activity data (splits, HR, cadence)
3. get_fitness_metrics - Get VO2max, training load, HRV, readiness
4. create_and_upload_plan - Create and upload workouts to Garmin

WHEN CREATING WORKOUTS:
- Use structured workouts with steps (warmup, intervals, cooldown)
- Use WorkoutRepeatStep for intervals (5x800m, 6x1000m, etc.)
- Use suggested_zones speed values (m/s) for pace targets
- Preview first (confirmed=false), then upload after user approves
- When creating multi-week plans, structure them by phases:
  * Weeks 1-4: Initial phase (base building, mostly easy runs)
  * Weeks 5-12: Progression phase (gradual introduction of quality work)
  * Weeks 13-16: Taper phase (if race approaching, reduce volume)
  * Include recovery weeks every 3-4 weeks (reduced volume)

WHEN CREATING FULL TRAINING PLANS:
- **First check Garmin data** for race dates, training frequency, and experience level
- **Only ask questions** if information is missing (see COACHING STYLE section above)
- Start with current fitness level assessment
- Build gradually with 10% volume increases max
- Include variety: easy runs, tempo, intervals, long runs
- Schedule rest days and recovery weeks
- Adjust based on user's schedule, injuries, and preferences
- **Format multi-week plans as a clean markdown table** with columns: Week | Day | Session | Details | KM | Pace
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
            st.info("📧 A 2FA code has been sent to your email. Use the **most recent** code if you received multiple.")
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
                            st.error(f"❌ {friendly_error(result)}")
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
            "openai:gpt-5-mini",  
            tools=tools,
            system_prompt=populated_prompt,
        )
        
        # Generate initial greeting with user summary
        if len(st.session_state.messages) == 0:
            with st.spinner("Analyzing your training data..."):
                try:
                    intro_response = st.session_state.agent.invoke({
                        "messages": [HumanMessage(content="""Introduce yourself as an AI Running Coach. Briefly summarize what you know about the user:
- Name and current fitness level
- Training goal (if any race planned)
- Recent training highlights
- Key metrics (race predictions, suggested paces) ... 

Keep it concise (8-15 sentences max). 

End with: "Is there anything else I should know about you? (injuries, schedule, preferences) Otherwise, how can I help today? I can analyze your training, check your fitness metrics, create workouts, or answer any running questions!"
""")]
                    })
                    intro_message = intro_response["messages"][-1].content
                    st.session_state.messages.append({"role": "assistant", "content": intro_message})
                except Exception as e:
                    # Fallback greeting
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": "👋 Hi! I'm your AI Running Coach. I've connected to your Garmin data and I'm ready to help. I can analyze your training, check your fitness metrics, create workouts, or answer running questions. What would you like to do?"
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
