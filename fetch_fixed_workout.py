from garminconnect import Garmin
import os
import json

EMAIL = os.environ.get("GARMIN_EMAIL", "aviv2904@gmail.com")
PASSWORD = os.environ.get("GARMIN_PASSWORD", "Aviv2904")

def main():
    try:
        print("Logging in...")
        def prompt_mfa():
            code = input("Enter 2FA code: ")
            return code
            
        client = Garmin(EMAIL, PASSWORD, prompt_mfa=prompt_mfa)
        client.login(tokenstore=os.path.expanduser("~/.garminconnect"))
        
        print("Fetching workouts...")
        workouts = client.get_workouts(start=0, limit=20)
        
        target_workout = None
        for w in workouts:
            if "W1_Fri_33km_Mixed" in w.get("workoutName", ""):
                target_workout = w
                break
        
        if target_workout:
            print(f"Found workout: {target_workout['workoutName']} (ID: {target_workout['workoutId']})")
            # Fetch full details
            full_details = client.download_workout(target_workout['workoutId'])
            
            with open("fixed_workout.json", "w") as f:
                json.dump(full_details, f, indent=2)
            print("Saved full workout details to fixed_workout.json")
        else:
            print("Could not find workout 'W1_Fri_33km_Mixed'")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
