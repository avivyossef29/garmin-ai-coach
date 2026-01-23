import json
import logging
import os
from garminconnect import Garmin
from garth import Client
from datetime import datetime, timedelta
from config import DEV_MODE

logger = logging.getLogger(__name__)


def _log(level, message):
    if DEV_MODE:
        logger.log(level, message)

class MFARequiredError(Exception):
    """Raised when 2FA code is required."""
    pass

class GarminAdapter:
    def __init__(self, email=None, password=None, garth_tokens=None):
        self.email = email or os.environ.get("GARMIN_EMAIL")
        self.password = password or os.environ.get("GARMIN_PASSWORD")
        self.client = None
        self._mfa_required = False
        self._garth_tokens = garth_tokens  # Pre-loaded tokens for restoration

    def login(self, mfa_code=None):
        """
        Authenticate with Garmin Connect.
        
        Can either:
        1. Use saved tokens (if provided via garth_tokens in __init__)
        2. Perform fresh login with email/password
        
        Args:
            mfa_code: Optional 2FA code. If None and 2FA is required, raises MFARequiredError.
        
        Returns:
            True if login successful
            
        Raises:
            MFARequiredError: If 2FA code is needed but not provided
        """
        # Try to restore from saved tokens first
        if self._garth_tokens and not mfa_code:
            try:
                self.client = Garmin(self.email, self.password)
                # Restore garth session from saved token string
                self.client.garth.loads(self._garth_tokens)
                # Test if tokens are still valid
                self.client.get_full_name()
                _log(logging.INFO, "✅ Restored from saved tokens, skipping 2FA")
                return True
            except Exception as e:
                # Tokens expired or invalid, fall through to fresh login
                _log(logging.WARNING, f"❌ Saved tokens invalid: {e}, will request fresh login")
                self._garth_tokens = None
        
        # Fresh login flow
        def prompt_mfa():
            if mfa_code:
                return mfa_code
            # Signal that MFA is required
            self._mfa_required = True
            raise MFARequiredError("2FA code required")

        # Always create fresh client - Garmin handles MFA in the same login flow
        # When mfa_code is provided, it will be returned by prompt_mfa callback
        self.client = Garmin(self.email, self.password, prompt_mfa=prompt_mfa)

        try:
            self.client.login()
            return True
        except MFARequiredError:
            raise  # Re-raise for the caller to handle
        except Exception as e:
            error_str = str(e).upper()
            if "MFA" in error_str or self._mfa_required:
                raise MFARequiredError("2FA code required")
            if "UNEXPECTED TITLE" in error_str and "MFA" in error_str:
                # Garmin is showing MFA page - need code
                raise MFARequiredError("2FA code required")
            raise

    def get_tokens(self):
        """
        Extract OAuth tokens from the current session for persistence.
        Returns base64-encoded JSON string via garth.dumps().
        """
        if not self.client or not self.client.garth:
            return None
        
        # Use garth's built-in serialization
        return self.client.garth.dumps()

    def fetch_user_data(self, days_back=7):
        """
        Aggregates user profile, stats, recent activities, and heart rate zones.
        """
        if not self.client:
            self.login()
        
        data = {}
        today = datetime.now().strftime("%Y-%m-%d")
        
        _log(logging.INFO, "Fetching user profile...")
        try:
            data["full_name"] = self.client.get_full_name()
            data["unit_system"] = self.client.get_unit_system()
        except Exception as e:
            _log(logging.WARNING, f"Warning: Could not fetch profile: {e}")

        _log(logging.INFO, "Fetching stats...")
        try:
            data["stats"] = self.client.get_stats(today)
            data["user_summary"] = self.client.get_user_summary(today)
        except Exception as e:
            _log(logging.WARNING, f"Warning: Could not fetch stats: {e}")
            
        _log(logging.INFO, "Fetching heart rates...")
        try:
            data["heart_rates"] = self.client.get_heart_rates(today)
        except Exception as e:
            _log(logging.WARNING, f"Warning: Could not fetch heart rates: {e}")
            
        _log(logging.INFO, f"Fetching recent activities ({days_back} days)...")
        try:
            data["recent_activities"] = self.fetch_recent_activities(days_back)
        except Exception as e:
             _log(logging.WARNING, f"Warning: Could not fetch recent activities: {e}")
             
        _log(logging.INFO, "Fetching calendar goals...")
        try:
            data["goals"] = self.fetch_goals()
        except Exception as e:
            _log(logging.WARNING, f"Warning: Could not fetch goals: {e}")

        return data

    def fetch_recent_activities(self, days=14):
        """Fetch activities from the last N days."""
        if not self.client:
            self.login()
            
        # The library uses start/limit, not date range directly for get_activities
        # We'll fetch a batch and filter, or fetch by count.
        # Assuming ~1-2 activities per day, limit=days*2 is safe
        activities = self.client.get_activities(0, days * 2)
        
        # Filter by date if needed, but get_activities returns most recent first
        return activities

    def fetch_goals(self):
        """
        Fetch future race goals or events from the calendar.
        Note: Garmin API doesn't have a direct 'get_goals' for races easily exposed in the wrapper sometimes.
        We will try to fetch the calendar for the next 6 months to find events.
        """
        if not self.client:
            self.login()
            
        start_date = datetime.now()
        end_date = start_date + timedelta(days=180) # Look ahead 6 months
        
        year = start_date.year
        month = start_date.month
        
        # This wrapper might not have a range calendar fetch, let's check what's available.
        # Usually get_calendar(year, month).
        
        goals = []
        
        # Fetch current month and next few months
        for i in range(6):
            y = year
            m = month + i
            if m > 12:
                m -= 12
                y += 1
                
            try:
                # Returns calendar data
                calendar = self.client.get_calendar(y, m)
                # Parse calendar for race events or goals
                # Structure is complex, we look for 'calendarItems'
                for week in calendar.get('calendarWeeks', []):
                    for day in week.get('calendarDays', []):
                        for item in day.get('calendarItems', []):
                            if item.get('itemType') == 'EVENT':
                                goals.append(item)
            except Exception as e:
                pass
                
        return goals

    def upload_workout(self, workout_json):
        """Uploads a single workout to Garmin Connect."""
        if not self.client:
            self.login()
        return self.client.upload_workout(workout_json)

    def schedule_workout(self, workout_id, schedule_date):
        """
        Schedule a workout to a specific date on the Garmin calendar.
        
        Args:
            workout_id: The ID of the workout to schedule
            schedule_date: datetime object or string in YYYY-MM-DD format
        
        Returns:
            dict with workoutScheduleId and workout details
        """
        if not self.client:
            self.login()
        
        # Convert datetime to string if needed
        if isinstance(schedule_date, datetime):
            date_str = schedule_date.strftime("%Y-%m-%d")
        else:
            date_str = schedule_date
            
        url = f"workout-service/schedule/{workout_id}"
        payload = {"date": date_str}
        
        try:
            response = self.client.garth.post("connectapi", url, json=payload, api=True)
            result = response.json()
            return result
        except Exception as e:
            _log(logging.WARNING, f"    ⚠️  Could not schedule workout {workout_id}: {e}")
            return None

    def get_existing_workouts(self, limit=200):
        """Fetch existing workouts."""
        if not self.client:
            self.login()
        return self.client.get_workouts(start=0, limit=limit)

    def delete_workout(self, workout_id):
        """Delete a specific workout."""
        if not self.client:
            self.login()
        
        url = f"/workout-service/workout/{workout_id}"
        self.client.garth.delete("connectapi", url, api=True)

    def fetch_calendar_workouts(self, days_ahead=14):
        """
        Fetch scheduled workouts from Garmin calendar for the next N days.
        
        Returns a list of workout events with:
        - date: date string (YYYY-MM-DD)
        - workout_name: name of the workout (or "Workout" if missing)
        - workout_type: classified type (easy, tempo, intervals, other)
        - description: workout description
        - color: emoji for visual indication (🟢/🟡/🔴/⚪)
        """
        if not self.client:
            self.login()
        
        # Check if get_calendar method exists
        if not hasattr(self.client, 'get_calendar'):
            _log(logging.WARNING, "⚠️  Calendar API not available in this version of garminconnect")
            return []
        
        workouts = []
        today = datetime.now()
        end_date = today + timedelta(days=days_ahead)
        
        # Determine which months to fetch
        months_to_fetch = set()
        current = today
        while current <= end_date:
            months_to_fetch.add((current.year, current.month))
            # Move to next month
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)
        
        # Fetch calendar data for each month
        for year, month in sorted(months_to_fetch):
            try:
                calendar = self.client.get_calendar(year, month)
                
                # Parse calendar structure
                for week in calendar.get('calendarWeeks', []):
                    for day in week.get('calendarDays', []):
                        # Get the date for this day
                        day_date_str = day.get('calendarDate')
                        if not day_date_str:
                            continue
                        
                        try:
                            day_date = datetime.strptime(day_date_str, "%Y-%m-%d")
                        except:
                            continue
                        
                        # Only include workouts in our date range
                        if not (today.date() <= day_date.date() <= end_date.date()):
                            continue
                        
                        # Look for workout items
                        for item in day.get('calendarItems', []):
                            item_type = item.get('itemType', '')
                            
                            # Check for various workout-related item types
                            if item_type in ['WORKOUT', 'SCHEDULED_WORKOUT']:
                                workout_name = item.get('workoutName') or item.get('title') or "Workout"
                                description = item.get('description', '')
                                
                                # Classify workout type
                                workout_type, color = self._classify_workout(workout_name, description)
                                
                                workouts.append({
                                    'date': day_date_str,
                                    'workout_name': workout_name,
                                    'workout_type': workout_type,
                                    'description': description,
                                    'color': color,
                                    'date_obj': day_date  # For sorting
                                })
            except Exception as e:
                # Skip this month if there's an error
                _log(logging.WARNING, f"Warning: Could not fetch calendar for {year}-{month}: {e}")
                continue
        
        # Sort by date
        workouts.sort(key=lambda x: x['date_obj'])
        
        # Remove the date_obj helper field
        for w in workouts:
            del w['date_obj']
        
        return workouts
    
    def _classify_workout(self, name, description):
        """
        Classify workout type based on name and description.
        Returns: (type_name, emoji_color)
        """
        # Combine name and description for keyword search
        text = (name + " " + description).lower()
        
        # Check for workout types (order matters - check specific before general)
        if any(keyword in text for keyword in ['interval', 'speed', 'repeat', 'x800', 'x1000', 'x400', 'fartlek']):
            return 'intervals', '🔴'
        elif any(keyword in text for keyword in ['tempo', 'threshold', 'lt', 'lactate']):
            return 'tempo', '🟡'
        elif any(keyword in text for keyword in ['easy', 'recovery', 'base', 'aerobic']):
            return 'easy', '🟢'
        elif any(keyword in text for keyword in ['long', 'endurance']):
            return 'long', '🟢'
        elif any(keyword in text for keyword in ['rest', 'off']):
            return 'rest', '⚪'
        else:
            return 'other', '⚪'
