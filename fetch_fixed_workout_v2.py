from garminconnect import Garmin
import os
import json

EMAIL = os.environ.get("GARMIN_EMAIL", "aviv2904@gmail.com")
PASSWORD = os.environ.get("GARMIN_PASSWORD", "Aviv2904")

def main():
    try:
        print("Logging in...")
        client = Garmin(EMAIL, PASSWORD)
        client.login(tokenstore=os.path.expanduser("~/.garminconnect"))
        
        print("Fetching workouts...")
        workouts = client.get_workouts(start=0, limit=20)
        
        target_workout = None
        for w in workouts:
            # We look for the one the user manually fixed.
            # Assuming it's still named similarly or has the same ID
            if "W1_Fri_33km_Mixed" in w.get("workoutName", ""):
                target_workout = w
                break
        
        if target_workout:
            print(f"Found workout: {target_workout['workoutName']} (ID: {target_workout['workoutId']})")
            # Use get_workout_by_id to get the JSON structure
            details = client.get_workout_by_id(target_workout['workoutId'])
            
            with open("real_fixed_workout.json", "w") as f:
                json.dump(details, f, indent=2)
            print("Saved full workout details to real_fixed_workout.json")
        else:
            print("Could not find workout 'W1_Fri_33km_Mixed'")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
