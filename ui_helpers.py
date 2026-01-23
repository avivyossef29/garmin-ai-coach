"""UI helpers for the Garmin AI Running Coach."""
import os
import traceback
from collections import defaultdict
from datetime import datetime, timedelta

import streamlit as st


def friendly_error(error):
    """Map technical errors to short, user-facing messages."""
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
    first_line = str(error).split('\n')[0]
    if len(first_line) > 100:
        return first_line[:100] + "..."
    return first_line


def render_sidebar(get_sidebar_stats_fn, on_logout):
    """Render the sidebar and return whether an API key is available."""
    with st.sidebar:
        if not os.environ.get("OPENAI_API_KEY"):
            st.header("⚙️ Setup Required")
            api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                key="openai_key",
                help="Get your key from platform.openai.com",
            )
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
                st.rerun()
            return False

        if st.session_state.garmin_connected:
            st.success(f"🏃 {st.session_state.garmin_user}")
            try:
                stats = get_sidebar_stats_fn()
                render_sidebar_stats(stats)
            except Exception as e:
                print(f"❌ Sidebar stats error: {e}")
                traceback.print_exc()

            st.markdown("---")
            if st.button("🗑️ Logout", use_container_width=True):
                on_logout()

        return True


def render_sidebar_stats(stats):
    """Render quick stats, skipping any missing metrics."""
    has_any_stat = any([
        stats.get('days_until_race') is not None,
        stats.get('this_week_km') is not None,
        stats.get('vo2_max') is not None,
        stats.get('recovery_emoji') is not None
    ])
    
    if not has_any_stat:
        return
    
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    
    if stats.get('days_until_race') is not None:
        race_name = stats.get('race_name', 'Race')
        days = stats['days_until_race']
        if days == 0:
            st.metric(f"🏁 {race_name}", "Race Day!")
        elif days == 1:
            st.metric(f"⏱️ {race_name}", "1 day left")
        else:
            st.metric(f"⏱️ {race_name}", f"{days} days left")
    
    if stats.get('this_week_km') is not None or stats.get('last_week_km') is not None:
        last_7 = stats.get('this_week_km', 0)
        prev_7 = stats.get('last_week_km', 0)
        
        if prev_7 > 0:
            delta = last_7 - prev_7
            st.metric("🏃 Last 7 Days", f"{last_7} km", 
                     delta=f"{delta:+.1f} km")
        else:
            st.metric("🏃 Last 7 Days", f"{last_7} km")
    
    if stats.get('vo2_max') is not None:
        st.metric("💪 VO2 Max", stats['vo2_max'])
    
    if stats.get('recovery_emoji') is not None and stats.get('recovery_status') is not None:
        status_map = {
            'ready': 'Ready to Train',
            'fair': 'Moderate',
            'poor': 'Need Rest'
        }
        status_text = status_map.get(stats['recovery_status'], 'Unknown')
        st.metric(f"{stats['recovery_emoji']} Recovery", status_text)


def render_calendar_tab(adapter):
    """Render the calendar tab showing scheduled workouts."""
    st.markdown("### 📅 Upcoming Workouts")
    st.markdown("View your scheduled workouts for the next 2 weeks")
    
    try:
        workouts = adapter.fetch_calendar_workouts(days_ahead=14)
        
        if not workouts:
            st.info("🏃 No workouts scheduled for the next 2 weeks. Ask the coach to create a training plan!")
        else:
            weeks = defaultdict(list)
            
            for workout in workouts:
                workout_date = datetime.strptime(workout['date'], "%Y-%m-%d")
                week_start = workout_date - timedelta(days=workout_date.weekday())
                week_key = week_start.strftime("%Y-%m-%d")
                weeks[week_key].append(workout)
            
            for week_start_str in sorted(weeks.keys()):
                week_start = datetime.strptime(week_start_str, "%Y-%m-%d")
                week_end = week_start + timedelta(days=6)
                
                st.markdown(f"#### Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}")
                
                cols = st.columns(7)
                
                week_workouts = {w['date']: w for w in weeks[week_start_str]}
                
                for i in range(7):
                    day_date = week_start + timedelta(days=i)
                    day_str = day_date.strftime("%Y-%m-%d")
                    
                    with cols[i]:
                        day_name = day_date.strftime("%a")
                        day_num = day_date.strftime("%d")
                        
                        if day_date.date() == datetime.now().date():
                            st.markdown(f"**{day_name}**  \n**{day_num}** 📍")
                        else:
                            st.markdown(f"{day_name}  \n{day_num}")
                        
                        if day_str in week_workouts:
                            workout = week_workouts[day_str]
                            
                            with st.expander(f"{workout['color']} {workout['workout_type'].title()}", expanded=False):
                                st.markdown(f"**{workout['workout_name']}**")
                                if workout['description']:
                                    st.markdown(workout['description'])
                        else:
                            st.markdown("—")
                
                st.markdown("---")
    
    except Exception as e:
        st.warning("Unable to load calendar. Please try again later.")
        print(f"❌ Calendar error: {e}")
        traceback.print_exc()
