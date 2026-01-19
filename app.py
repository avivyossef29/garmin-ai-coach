import streamlit as st
import os
import shutil
import asyncio
import time
from datetime import datetime, timedelta
import extra_streamlit_components as stx
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from llm_tools import fetch_user_context, read_training_data, create_and_upload_plan, get_fitness_metrics, set_adapter, get_sidebar_stats
from garmin import MFARequiredError, attempt_garmin_login
from garmin.adapter import GarminAdapter
from user_storage import save_conversation_by_id, get_user_id, load_garmin_token_by_id, load_conversation_by_id, load_garmin_username_by_id
from config import SYSTEM_PROMPT, DEV_MODE
from ui_helpers import friendly_error

# Load environment variables
load_dotenv()


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

# Initialize CookieManager (use consistent key to persist across reruns)
cookie_manager = stx.CookieManager(key="garmin_cookies")

# Initialize session state
if "garmin_connected" not in st.session_state:
    st.session_state.garmin_connected = False
    st.session_state.garmin_user = None
    st.session_state.awaiting_mfa = False

if "messages" not in st.session_state:
    st.session_state.messages = []

# Try to restore session from cookie (persists across browser refresh/close)
if not st.session_state.garmin_connected:
    all_cookies = cookie_manager.get_all()
    print(f"🍪 All cookies: {all_cookies}")
    saved_user_id = cookie_manager.get("garmin_user_id")
    print(f"🍪 Cookie read: garmin_user_id = {saved_user_id}")
    if saved_user_id:
        saved_token = load_garmin_token_by_id(saved_user_id)
        saved_username = load_garmin_username_by_id(saved_user_id)
        if saved_token:
            try:
                # Restore from saved token - no email/password needed!
                adapter = GarminAdapter(garth_tokens=saved_token)
                adapter.login()
                # Success! Restore full session
                print(f"✅ Restored session from cookie for user {saved_user_id[:8]}...")
                st.session_state.garmin_connected = True
                # Use saved username, fallback to API call, then default
                st.session_state.garmin_user = saved_username or adapter.client.get_full_name() or "User"
                st.session_state.user_id = saved_user_id
                st.session_state.garmin_adapter = adapter
                set_adapter(adapter)
                # Load saved conversation (chat history)
                saved_messages = load_conversation_by_id(saved_user_id)
                if saved_messages:
                    st.session_state.messages = saved_messages
            except Exception as e:
                # Token expired or invalid - clear cookie and show login
                print(f"🍪 Cookie restore FAILED: {e}, deleting cookie")
                cookie_manager.delete("garmin_user_id")

# Fallback: Check for existing adapter in session state (same browser tab, no refresh)
if "garmin_adapter" in st.session_state and st.session_state.garmin_adapter and not st.session_state.garmin_connected:
    adapter = st.session_state.garmin_adapter
    try:
        adapter.client.get_full_name()
        st.session_state.garmin_connected = True
        st.session_state.garmin_user = adapter.client.get_full_name()
        set_adapter(adapter)
    except:
        del st.session_state.garmin_adapter
        st.session_state.garmin_connected = False
        st.session_state.garmin_user = None

# Check for API key from environment
if not os.environ.get("OPENAI_API_KEY"):
    with st.sidebar:
        st.header("⚙️ Setup Required")
        api_key = st.text_input("OpenAI API Key", type="password", key="openai_key", 
                                help="Get your key from platform.openai.com")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            st.rerun()

# Sidebar - Show status when connected
with st.sidebar:
    if st.session_state.garmin_connected:
        st.success(f"🏃 {st.session_state.garmin_user}")
        
        # Quick Stats section
        try:
            stats = get_sidebar_stats()
            
            # Only show stats header if we have at least one stat to display
            has_any_stat = any([
                stats.get('days_until_race') is not None,
                stats.get('this_week_km') is not None,
                stats.get('vo2_max') is not None,
                stats.get('recovery_emoji') is not None
            ])
            
            if has_any_stat:
                st.markdown("---")
                st.markdown("### 📊 Quick Stats")
                
                # Days until race (only if available)
                if stats.get('days_until_race') is not None:
                    race_name = stats.get('race_name', 'Race')
                    days = stats['days_until_race']
                    if days == 0:
                        st.metric("🎯 Race Day", "Today!")
                    elif days == 1:
                        st.metric("🎯 Race Day", "Tomorrow")
                    else:
                        st.metric("🎯 Race Day", f"{days} days", help=race_name)
                
                # Weekly mileage comparison (only if available)
                if stats.get('this_week_km') is not None or stats.get('last_week_km') is not None:
                    this_week = stats.get('this_week_km', 0)
                    last_week = stats.get('last_week_km', 0)
                    
                    if last_week > 0:
                        delta = this_week - last_week
                        st.metric("🏃 This Week", f"{this_week} km", 
                                 delta=f"{delta:+.1f} km vs last week")
                    else:
                        st.metric("🏃 This Week", f"{this_week} km")
                
                # VO2 Max (only if available)
                if stats.get('vo2_max') is not None:
                    st.metric("💪 VO2 Max", stats['vo2_max'])
                
                # Recovery status (only if available)
                if stats.get('recovery_emoji') is not None and stats.get('recovery_status') is not None:
                    status_map = {
                        'ready': 'Ready',
                        'fair': 'Fair',
                        'poor': 'Rest Needed'
                    }
                    status_text = status_map.get(stats['recovery_status'], 'Unknown')
                    st.metric(f"{stats['recovery_emoji']} Recovery", status_text)
        except Exception as e:
            # If stats fail, don't crash the sidebar - just skip them
            pass
        
        st.markdown("---")
        if st.button("🗑️ Logout", use_container_width=True):
            # Save conversation before logout
            if "user_id" in st.session_state and st.session_state.messages:
                save_conversation_by_id(st.session_state.user_id, st.session_state.messages)
            
            # Delete the cookie
            print(f"🍪 Cookie DELETE: garmin_user_id (logout)")
            cookie_manager.delete("garmin_user_id")
            
            # Clear session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# Main content - Connection flow
if not os.environ.get("OPENAI_API_KEY"):
    st.info("👈 Please enter your OpenAI API key in the sidebar to get started.")
elif not st.session_state.garmin_connected:
    # Garmin Connection UI
    st.markdown("### Connect to Garmin")
    st.markdown("Enter your Garmin credentials. If you've logged in before with these credentials, you'll skip 2FA!")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Step 1: Email/Password
        if not st.session_state.awaiting_mfa:
            garmin_email = st.text_input("Garmin Email", key="garmin_email_input", 
                                          placeholder="your.email@example.com")
            garmin_password = st.text_input("Garmin Password", type="password", key="garmin_password_input")
            
            if st.button("🔗 Connect to Garmin", use_container_width=True, type="primary", 
                         disabled=not (garmin_email and garmin_password)):
                with st.spinner("Connecting to Garmin..."):
                    success, result, needs_mfa = attempt_garmin_login(garmin_email, garmin_password)
                    if success:
                        st.session_state.garmin_connected = True
                        st.session_state.garmin_user = result
                        # Set cookie for 30-day persistence
                        user_id = get_user_id(garmin_email, garmin_password)
                        st.session_state.user_id = user_id
                        expire_date = datetime.now() + timedelta(days=30)
                        cookie_manager.set("garmin_user_id", user_id, expires_at=expire_date)
                        print(f"🍪 Cookie SET: garmin_user_id = {user_id}, expires = {expire_date}")
                        if "garmin_adapter" in st.session_state:
                            set_adapter(st.session_state.garmin_adapter)
                        time.sleep(0.5)  # Give browser time to save cookie
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
                        # Use stored credentials from MFA step 1
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
                            # Set cookie for 30-day persistence
                            user_id = get_user_id(email, password)
                            st.session_state.user_id = user_id
                            expire_date = datetime.now() + timedelta(days=30)
                            cookie_manager.set("garmin_user_id", user_id, expires_at=expire_date)
                            print(f"🍪 Cookie SET (MFA): garmin_user_id = {user_id}, expires = {expire_date}")
                            # Clean up pending credentials
                            for key in ["pending_email", "pending_password", "pending_adapter"]:
                                if key in st.session_state:
                                    del st.session_state[key]
                            if "garmin_adapter" in st.session_state:
                                set_adapter(st.session_state.garmin_adapter)
                            time.sleep(0.5)  # Give browser time to save cookie
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
else:
    # Connected - show chat interface
    
    # Auto-fetch user context on first load (skip in DEV_MODE)
    if "user_context" not in st.session_state:
        if DEV_MODE:
            st.session_state.user_context = "Dev mode: Garmin data not loaded. Ask me to fetch it if needed."
        else:
            with st.spinner("Fetching your Garmin data..."):
                try:
                    context = fetch_user_context.invoke({})
                    st.session_state.user_context = context
                except Exception as e:
                    st.session_state.user_context = f"Could not load Garmin data: {friendly_error(e)}"
    
    # Initialize Agent
    if "agent" not in st.session_state:
        tools = [fetch_user_context, read_training_data, get_fitness_metrics, create_and_upload_plan]
        today = datetime.now().strftime("%Y-%m-%d")
        populated_prompt = SYSTEM_PROMPT.format(
            today=today,
            user_context=st.session_state.user_context
        )
        st.session_state.agent = create_agent(
            "openai:gpt-4o-mini",  
            tools=tools,
            system_prompt=populated_prompt,
        )
        
        # Generate initial greeting ONLY if no messages AND not DEV_MODE
        if len(st.session_state.messages) == 0:
            if DEV_MODE:
                # Simple greeting in dev mode
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": "👋 Hi! I'm your AI Running Coach (DEV MODE). How can I help?"
                })
            else:
                with st.spinner("Analyzing your training data..."):
                    try:
                        intro_response = st.session_state.agent.invoke({
                            "messages": [HumanMessage(content="""Introduce yourself as an AI Running Coach. Briefly summarize what you know about the user:
- Name and current fitness level
- Training goal (if any race planned)
- Recent training highlights
- Key metrics (race predictions, suggested paces)

Keep it concise (8-15 sentences max). 

End with: "Is there anything else I should know about you? (injuries, schedule, preferences) Otherwise, how can I help today?"
""")]
                        })
                        intro_message = intro_response["messages"][-1].content
                        st.session_state.messages.append({"role": "assistant", "content": intro_message})
                    except Exception as e:
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": "👋 Hi! I'm your AI Running Coach. I've connected to your Garmin data. How can I help?"
                        })

    # Create tabs for Chat and Calendar views
    chat_tab, calendar_tab = st.tabs(["💬 Chat", "📅 Calendar"])
    
    with chat_tab:
        # Display Chat History
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat Input
        if prompt := st.chat_input("How can I help with your training today?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Auto-save after user message
            if "user_id" in st.session_state:
                save_conversation_by_id(st.session_state.user_id, st.session_state.messages)
            
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

                    async def stream_agent_events():
                        """Stream events from the agent and update UI in real-time."""
                        response_placeholder = st.empty()
                        full_response = ""
                        tool_statuses = {}
                        
                        async for event in st.session_state.agent.astream_events(
                            {"messages": chat_history},
                            version="v2"
                        ):
                            kind = event["event"]
                            
                            if kind == "on_chat_model_stream":
                                content = event["data"]["chunk"].content
                                if content:
                                    full_response += content
                                    response_placeholder.markdown(full_response + "▌")
                            
                            elif kind == "on_tool_start":
                                tool_name = event.get("name", "tool")
                                tool_statuses[tool_name] = st.status(f"🔧 Using {tool_name}...", state="running")
                            
                            elif kind == "on_tool_end":
                                tool_name = event.get("name", "tool")
                                if tool_name in tool_statuses:
                                    tool_statuses[tool_name].update(state="complete")
                        
                        response_placeholder.markdown(full_response)
                        return full_response
                    
                    output = asyncio.run(stream_agent_events())
                    st.session_state.messages.append({"role": "assistant", "content": output})
                    
                    # Auto-save after response
                    if "user_id" in st.session_state:
                        save_conversation_by_id(st.session_state.user_id, st.session_state.messages)
                    
                except Exception as e:
                    st.error(f"❌ {friendly_error(e)}")
    
    with calendar_tab:
        st.markdown("### 📅 Upcoming Workouts")
        st.markdown("View your scheduled workouts for the next 2 weeks")
        
        try:
            # Fetch calendar workouts
            adapter = st.session_state.garmin_adapter
            workouts = adapter.fetch_calendar_workouts(days_ahead=14)
            
            if not workouts:
                st.info("🏃 No workouts scheduled for the next 2 weeks. Ask the coach to create a training plan!")
            else:
                # Group workouts by week
                from collections import defaultdict
                weeks = defaultdict(list)
                
                for workout in workouts:
                    workout_date = datetime.strptime(workout['date'], "%Y-%m-%d")
                    # Get Monday of the week
                    week_start = workout_date - timedelta(days=workout_date.weekday())
                    week_key = week_start.strftime("%Y-%m-%d")
                    weeks[week_key].append(workout)
                
                # Display each week
                for week_start_str in sorted(weeks.keys()):
                    week_start = datetime.strptime(week_start_str, "%Y-%m-%d")
                    week_end = week_start + timedelta(days=6)
                    
                    st.markdown(f"#### Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}")
                    
                    # Create 7 columns for the week
                    cols = st.columns(7)
                    
                    # Create a lookup for workouts by date
                    week_workouts = {w['date']: w for w in weeks[week_start_str]}
                    
                    # Display each day
                    for i in range(7):
                        day_date = week_start + timedelta(days=i)
                        day_str = day_date.strftime("%Y-%m-%d")
                        
                        with cols[i]:
                            # Day header
                            day_name = day_date.strftime("%a")
                            day_num = day_date.strftime("%d")
                            
                            # Highlight today
                            if day_date.date() == datetime.now().date():
                                st.markdown(f"**{day_name}**  \n**{day_num}** 📍")
                            else:
                                st.markdown(f"{day_name}  \n{day_num}")
                            
                            # Show workout if exists
                            if day_str in week_workouts:
                                workout = week_workouts[day_str]
                                
                                # Display with color emoji and name
                                with st.expander(f"{workout['color']} {workout['workout_type'].title()}", expanded=False):
                                    st.markdown(f"**{workout['workout_name']}**")
                                    if workout['description']:
                                        st.markdown(workout['description'])
                            else:
                                # Empty day
                                st.markdown("—")
                    
                    st.markdown("---")
        
        except Exception as e:
            st.warning(f"Unable to load calendar. Please try again later.")
            print(f"Calendar error: {e}")

