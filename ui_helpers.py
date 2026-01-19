"""
UI helper functions for the Garmin AI Running Coach.
"""
import streamlit as st
from datetime import datetime, timedelta
from collections import defaultdict


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


def render_sidebar_stats(stats):
    """
    Render quick stats in the sidebar.
    Only displays metrics that have data available.
    """
    # Only show stats header if we have at least one stat to display
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
    
    # Days until race (only if available)
    if stats.get('days_until_race') is not None:
        race_name = stats.get('race_name', 'Race')
        days = stats['days_until_race']
        if days == 0:
            st.metric(f"🏁 {race_name}", "Race Day!")
        elif days == 1:
            st.metric(f"⏱️ {race_name}", "1 day left")
        else:
            st.metric(f"⏱️ {race_name}", f"{days} days left")
    
    # Weekly mileage comparison (only if available)
    if stats.get('this_week_km') is not None or stats.get('last_week_km') is not None:
        last_7 = stats.get('this_week_km', 0)
        prev_7 = stats.get('last_week_km', 0)
        
        if prev_7 > 0:
            delta = last_7 - prev_7
            st.metric("🏃 Last 7 Days", f"{last_7} km", 
                     delta=f"{delta:+.1f} km")
        else:
            st.metric("🏃 Last 7 Days", f"{last_7} km")
    
    # VO2 Max (only if available)
    if stats.get('vo2_max') is not None:
        st.metric("💪 VO2 Max", stats['vo2_max'])
    
    # Recovery status (only if available)
    if stats.get('recovery_emoji') is not None and stats.get('recovery_status') is not None:
        status_map = {
            'ready': 'Ready to Train',
            'fair': 'Moderate',
            'poor': 'Need Rest'
        }
        status_text = status_map.get(stats['recovery_status'], 'Unknown')
        st.metric(f"{stats['recovery_emoji']} Recovery", status_text)


def render_calendar_tab(adapter):
    """
    Render the calendar tab showing scheduled workouts.
    """
    st.markdown("### 📅 Upcoming Workouts")
    st.markdown("View your scheduled workouts for the next 2 weeks")
    
    try:
        # Fetch calendar workouts
        workouts = adapter.fetch_calendar_workouts(days_ahead=14)
        
        if not workouts:
            st.info("🏃 No workouts scheduled for the next 2 weeks. Ask the coach to create a training plan!")
        else:
            # Group workouts by week
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
        print(f"❌ Calendar error: {e}")
        import traceback
        traceback.print_exc()
