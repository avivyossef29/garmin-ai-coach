import os
import json
from garminconnect import Garmin
from datetime import datetime, timedelta

class GarminAdapter:
    def __init__(self, email=None, password=None):
        self.email = email or os.environ.get("GARMIN_EMAIL")
        self.password = password or os.environ.get("GARMIN_PASSWORD")
        self.client = None
        self.tokenstore_path = os.path.expanduser("~/.garminconnect")

    def login(self):
        """
        Authenticate with Garmin Connect.
        Uses stored tokens if available, otherwise performs fresh login.
        """
        def prompt_mfa():
            print("\n" + "=" * 50)
            print("2FA CODE REQUIRED")
            print("=" * 50)
            print("Garmin has sent an authentication code to your email.")
            code = input("\nEnter the 2FA code: ").strip()
            return code

        self.client = Garmin(self.email, self.password, prompt_mfa=prompt_mfa)

        login_success = False
        if os.path.exists(self.tokenstore_path):
            print("Found existing tokens, attempting to use them...")
            try:
                self.client.login(tokenstore=self.tokenstore_path)
                print("✓ Login Successful (using stored tokens)!")
                login_success = True
            except Exception as e:
                print(f"Stored tokens expired or invalid: {e}")

        if not login_success:
            print("Performing fresh login...")
            print("(You may be prompted for a 2FA code)")
            self.client.login()
            self.client.garth.dump(self.tokenstore_path)
            print(f"✓ Login Successful! Tokens saved to {self.tokenstore_path}")

    def fetch_user_data(self, days_back=7):
        """
        Aggregates user profile, stats, recent activities, and heart rate zones.
        """
        if not self.client:
            self.login()
        
        data = {}
        today = datetime.now().strftime("%Y-%m-%d")
        
        print("Fetching user profile...")
        try:
            data["full_name"] = self.client.get_full_name()
            data["unit_system"] = self.client.get_unit_system()
        except Exception as e:
            print(f"Warning: Could not fetch profile: {e}")

        print("Fetching stats...")
        try:
            data["stats"] = self.client.get_stats(today)
            data["user_summary"] = self.client.get_user_summary(today)
        except Exception as e:
            print(f"Warning: Could not fetch stats: {e}")
            
        print("Fetching heart rates...")
        try:
            data["heart_rates"] = self.client.get_heart_rates(today)
        except Exception as e:
            print(f"Warning: Could not fetch heart rates: {e}")
            
        print(f"Fetching recent activities ({days_back} days)...")
        try:
            data["recent_activities"] = self.fetch_recent_activities(days_back)
        except Exception as e:
             print(f"Warning: Could not fetch recent activities: {e}")
             
        print("Fetching calendar goals...")
        try:
            data["goals"] = self.fetch_goals()
        except Exception as e:
            print(f"Warning: Could not fetch goals: {e}")

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
        """
        if not self.client:
            self.login()
            
        url = "/workout-service/schedule"
        payload = {
            "workoutId": workout_id,
            "date": schedule_date.strftime("%Y-%m-%d")
        }
        
        try:
            response = self.client.garth.post("connectapi", url, json=payload, api=True)
            return response.json()
        except Exception as e:
            print(f"    Warning: Could not schedule to calendar: {e}")
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
