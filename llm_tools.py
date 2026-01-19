import json
from datetime import datetime
from langchain.tools import tool
from garmin.adapter import GarminAdapter
from workout_manager import WorkoutManager

# Global adapter - set by app.py after successful login
# Also stores per-session data (full_activities, last_plan) to avoid shared files
_shared_adapter = None
_session_data = {}


def set_adapter(adapter):
    """Set the shared Garmin adapter (called by app.py after login)."""
    global _shared_adapter, _session_data
    _shared_adapter = adapter
    # Reset session data for new login
    _session_data = {"full_activities": [], "last_plan": []}
    
    # Also store in Streamlit session state if available
    try:
        import streamlit as st
        if hasattr(st, 'session_state'):
            st.session_state.garmin_adapter = adapter
    except:
        pass  # Streamlit not available (e.g., in tests)


def _get_adapter():
    """Get the shared authenticated Garmin adapter."""
    # First try to get from Streamlit session state
    try:
        import streamlit as st
        if hasattr(st, 'session_state') and 'garmin_adapter' in st.session_state:
            return st.session_state.garmin_adapter
    except:
        pass  # Streamlit not available (e.g., in tests)
    
    # Fallback to global variable
    global _shared_adapter
    if _shared_adapter is None:
        raise RuntimeError("Garmin adapter not set. Please login first.")
    return _shared_adapter


def _seconds_to_pace(seconds_per_km):
    """Convert seconds/km to pace string."""
    mins = int(seconds_per_km // 60)
    secs = int(seconds_per_km % 60)
    return f"{mins}:{secs:02d}/km"


def _speed_to_pace(speed_ms):
    """Convert m/s to pace string."""
    if speed_ms <= 0:
        return "N/A"
    seconds_per_km = 1000 / speed_ms
    return _seconds_to_pace(seconds_per_km)


@tool
def fetch_user_context(goal: str = "", notes: str = "") -> str:
    """
    Fetches the user's Garmin data including recent runs, race predictions, goals, and training zones.
    
    ALWAYS call this FIRST before creating any workout plan!
    
    Args:
        goal: The user's training goal if mentioned (e.g., "sub-3:30 marathon")
        notes: Any specific notes from the user
    
    Returns:
        JSON with user's profile, upcoming race goals, recent runs with paces, race predictions, and suggested training zones.
    """
    try:
        adapter = _get_adapter()
        
        summary = {
            "name": adapter.client.get_full_name(),
            "user_stated_goal": goal or "Not specified",
            "notes": notes or "None",
        }
        
        # Get training plans (contains race events with dates!)
        try:
            plans_data = adapter.client.get_training_plans()
            plans = plans_data.get("trainingPlanList", [])
            if plans:
                upcoming_races = []
                for p in plans:
                    race_date = p.get("endDate", "")[:10] if p.get("endDate") else None
                    if race_date:
                        upcoming_races.append({
                            "name": p.get("name", "Training Plan"),
                            "race_date": race_date,
                            "start_date": p.get("startDate", "")[:10] if p.get("startDate") else None,
                            "duration_weeks": p.get("durationInWeeks"),
                            "level": p.get("trainingLevel", {}).get("levelKey"),
                        })
                if upcoming_races:
                    summary["upcoming_races"] = upcoming_races
        except Exception as e:
            summary["training_plans_error"] = str(e)
        
        # Get race predictions
        try:
            predictions = adapter.client.get_race_predictions()
            if predictions:
                summary["race_predictions"] = {
                    "5K": _seconds_to_pace(predictions.get("time5K", 0) / 5),
                    "10K": _seconds_to_pace(predictions.get("time10K", 0) / 10),
                    "half_marathon": _seconds_to_pace(predictions.get("timeHalfMarathon", 0) / 21.0975),
                    "marathon": _seconds_to_pace(predictions.get("timeMarathon", 0) / 42.195),
                    "marathon_time": f"{predictions.get('timeMarathon', 0) // 3600}:{(predictions.get('timeMarathon', 0) % 3600) // 60:02d}:{predictions.get('timeMarathon', 0) % 60:02d}"
                }
        except Exception as e:
            summary["race_predictions"] = f"Error: {e}"
        
        # Get lactate threshold
        try:
            lt = adapter.client.get_lactate_threshold(latest=True)
            if lt:
                summary["lactate_threshold"] = {
                    "heart_rate": lt.get("speed_and_heart_rate", {}).get("heartRate"),
                    "ftp_watts": lt.get("power", {}).get("functionalThresholdPower"),
                }
        except Exception as e:
            summary["lactate_threshold"] = f"Error: {e}"
        
        # Get recent activities with proper speed data
        activities = adapter.client.get_activities(0, 15)
        recent_runs = []
        full_activities = []  # Store full data for file
        
        for act in activities:
            if act.get("activityType", {}).get("typeKey") == "running":
                avg_speed = act.get("averageSpeed", 0)
                max_speed = act.get("maxSpeed", 0)
                distance = act.get("distance", 0)
                duration = act.get("duration", 0)
                
                # Summary for context
                run_data = {
                    "date": act.get("startTimeLocal", "")[:10],
                    "name": act.get("activityName", "Run"),
                    "distance_km": round(distance / 1000, 1),
                    "duration_min": round(duration / 60, 0),
                    "avg_pace": _speed_to_pace(avg_speed),
                    "avg_speed_ms": round(avg_speed, 2) if avg_speed else None,
                    "max_pace": _speed_to_pace(max_speed),
                    "avg_hr": act.get("averageHR"),
                    "max_hr": act.get("maxHR"),
                    "training_effect": act.get("aerobicTrainingEffect"),
                }
                recent_runs.append(run_data)
                
                # Full data for file
                full_activities.append({
                    "activity_id": act.get("activityId"),
                    "date": act.get("startTimeLocal", "")[:10],
                    "name": act.get("activityName", "Run"),
                    "distance_m": distance,
                    "duration_sec": duration,
                    "avg_speed_ms": avg_speed,
                    "max_speed_ms": max_speed,
                    "avg_hr": act.get("averageHR"),
                    "max_hr": act.get("maxHR"),
                    "calories": act.get("calories"),
                    "elevation_gain": act.get("elevationGain"),
                    "avg_cadence": act.get("averageRunningCadenceInStepsPerMinute"),
                    "training_effect_aerobic": act.get("aerobicTrainingEffect"),
                    "training_effect_anaerobic": act.get("anaerobicTrainingEffect"),
                    "avg_power": act.get("avgPower"),
                    "description": act.get("description", ""),
                })
        
        summary["recent_runs"] = recent_runs
        
        # Calculate suggested training zones from the data
        if recent_runs:
            speeds = [r["avg_speed_ms"] for r in recent_runs if r["avg_speed_ms"]]
            if speeds:
                avg_speed = sum(speeds) / len(speeds)
                fastest = max(speeds)
                
                # Suggest zones based on user's actual data
                summary["suggested_zones"] = {
                    "easy_pace": _speed_to_pace(avg_speed * 0.85),
                    "easy_speed_ms": round(avg_speed * 0.85, 2),
                    "tempo_pace": _speed_to_pace(avg_speed * 1.05),
                    "tempo_speed_ms": round(avg_speed * 1.05, 2),
                    "interval_pace": _speed_to_pace(fastest * 1.05),
                    "interval_speed_ms": round(fastest * 1.05, 2),
                    "note": "Use speed_ms values for workout targetValueOne/Two"
                }
        
        # Store full training data in session (not file - for multi-user safety)
        global _session_data
        _session_data["full_activities"] = full_activities
        _session_data["fetched_at"] = datetime.now().isoformat()
        
        summary["note"] = "Full activity details available - use read_training_data tool for more detail"
        
        return json.dumps(summary, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return f"Error fetching Garmin data: {str(e)}"


@tool
def read_training_data() -> str:
    """
    Reads the full training data with detailed activity information.
    
    Use this to see more details about the user's recent runs, including:
    - Full distance and duration
    - Heart rate data
    - Cadence and power
    - Training effects
    - Elevation gain
    
    Returns:
        JSON with full activity details
    """
    global _session_data
    try:
        if not _session_data.get("full_activities"):
            return "No training data available. Call fetch_user_context first."
        
        data = {
            "fetched_at": _session_data.get("fetched_at"),
            "full_activities": _session_data["full_activities"]
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error reading training data: {str(e)}"


@tool  
def create_and_upload_plan(plan_json: str, confirmed: bool = False) -> str:
    """
    Creates structured running workouts and uploads them to Garmin Connect.
    
    EXAMPLE - Interval workout (5x800m):
    ```json
    [{
      "workoutName": "5x800m Intervals",
      "scheduleDate": "2026-01-20",
      "description": "Speed work",
      "steps": [
        {"type": "WorkoutStep", "intensity": "WARMUP", "durationType": "DISTANCE", "durationValue": 2000, "targetType": "NONE"},
        {
          "type": "WorkoutRepeatStep",
          "repeatValue": 5,
          "steps": [
            {"type": "WorkoutStep", "intensity": "INTERVAL", "durationType": "DISTANCE", "durationValue": 800, "targetType": "SPEED", "targetValueOne": 3.9, "targetValueTwo": 4.2},
            {"type": "WorkoutStep", "intensity": "RECOVERY", "durationType": "TIME", "durationValue": 120, "targetType": "NONE"}
          ]
        },
        {"type": "WorkoutStep", "intensity": "COOLDOWN", "durationType": "DISTANCE", "durationValue": 2000, "targetType": "NONE"}
      ]
    }]
    ```
    
    EXAMPLE - Tempo run with pace target:
    ```json
    [{
      "workoutName": "Tempo Run",
      "scheduleDate": "2026-01-22",
      "description": "6km at tempo pace",
      "steps": [
        {"type": "WorkoutStep", "intensity": "WARMUP", "durationType": "DISTANCE", "durationValue": 2000, "targetType": "NONE"},
        {"type": "WorkoutStep", "intensity": "ACTIVE", "durationType": "DISTANCE", "durationValue": 6000, "targetType": "SPEED", "targetValueOne": 3.5, "targetValueTwo": 3.7},
        {"type": "WorkoutStep", "intensity": "COOLDOWN", "durationType": "DISTANCE", "durationValue": 1000, "targetType": "NONE"}
      ]
    }]
    ```
    
    SPEED VALUES (m/s) - use suggested_zones from user data:
    - 4:00/km pace = 4.17 m/s
    - 4:30/km pace = 3.70 m/s  
    - 5:00/km pace = 3.33 m/s
    - 5:30/km pace = 3.03 m/s
    
    Args:
        plan_json: JSON array of workouts (see examples above)
        confirmed: false=preview, true=upload after user confirms
    
    Returns:
        Preview of plan or upload results
    """
    try:
        plan_data = json.loads(plan_json)
        if not isinstance(plan_data, list):
            return "Error: Plan must be a JSON array of workouts"
        
        if not plan_data:
            return "Error: Plan is empty"
        
        # Store plan in session (not file - for multi-user safety)
        global _session_data
        _session_data["last_plan"] = plan_data
        
        # If not confirmed, show preview
        if not confirmed:
            summary = f"**Plan with {len(plan_data)} workouts:**\n\n"
            for w in plan_data:
                date = w.get("scheduleDate", "TBD")
                name = w.get("workoutName", "Workout")
                desc = w.get("description", "")
                summary += f"• {date}: **{name}** - {desc}\n"
            summary += "\n*Reply 'yes' to upload these workouts to Garmin.*"
            return summary
        
        # Upload to Garmin
        adapter = _get_adapter()
        manager = WorkoutManager()
        
        results = []
        success_count = 0
        
        for workout in plan_data:
            try:
                garmin_json = manager.convert_to_garmin_format(workout)
                result = adapter.upload_workout(garmin_json)
                workout_id = result.get('workoutId')
                
                if workout_id:
                    date_str = workout.get('scheduleDate')
                    schedule_date = datetime.strptime(date_str, "%Y-%m-%d")
                    adapter.schedule_workout(workout_id, schedule_date)
                    results.append(f"✓ {workout['workoutName']} scheduled for {date_str}")
                    success_count += 1
                else:
                    results.append(f"⚠ {workout['workoutName']} - upload issue")
            except Exception as e:
                results.append(f"✗ {workout.get('workoutName', 'Unknown')}: {str(e)}")
        
        return f"**Uploaded {success_count}/{len(plan_data)} workouts:**\n" + "\n".join(results)
        
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON - {e}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_fitness_metrics() -> str:
    """
    Gets the user's current fitness metrics from Garmin.
    
    Includes:
    - VO2 Max
    - Training load (7-day acute, 28-day chronic)
    - Training status (productive, maintaining, detraining, etc.)
    - Recovery time and readiness score
    - HRV (heart rate variability)
    - Load focus (anaerobic, high aerobic, low aerobic)
    
    Use this to understand the user's current fitness level, recovery status, and training balance.
    
    Returns:
        JSON with fitness and training metrics
    """
    try:
        adapter = _get_adapter()
        today = datetime.now().strftime("%Y-%m-%d")
        
        result = {}
        
        # Training status
        try:
            status = adapter.client.get_training_status(today)
            if status:
                result["training_status"] = {
                    "status": status.get("trainingStatusPhrase"),
                    "vo2_max": status.get("vo2MaxPreciseValue"),
                    "acute_load": status.get("acuteTrainingLoad"),
                    "chronic_load": status.get("chronicTrainingLoad"),
                    "load_focus": status.get("trainingLoadBalancePhrase"),
                }
        except Exception as e:
            result["training_status_error"] = str(e)
        
        # Training readiness
        try:
            readiness = adapter.client.get_training_readiness(today)
            if readiness:
                result["readiness"] = {
                    "score": readiness.get("score"),
                    "level": readiness.get("level"),
                    "recovery_time_hours": readiness.get("recoveryTimeInHours"),
                }
        except Exception as e:
            result["readiness_error"] = str(e)
        
        # HRV data
        try:
            hrv = adapter.client.get_hrv_data(today)
            if hrv:
                result["hrv"] = {
                    "weekly_average": hrv.get("hrvSummary", {}).get("weeklyAvg"),
                    "last_night": hrv.get("hrvSummary", {}).get("lastNightAvg"),
                    "status": hrv.get("hrvSummary", {}).get("status"),
                }
        except Exception as e:
            result["hrv_error"] = str(e)
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return f"Error getting fitness metrics: {str(e)}"
