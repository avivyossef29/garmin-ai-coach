import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from garmin_adapter import GarminAdapter
from workout_manager import WorkoutManager

USER_CONTEXT_FILE = "user_context.json"
SUGGESTED_PLAN_FILE = "suggested_plan.json"

def fetch_data(args):
    print(f"Fetching user data...")
    adapter = GarminAdapter()
    data = adapter.fetch_user_data(days_back=args.days)
    
    print("\n" + "="*50)
    print("USER CONTEXT VERIFICATION")
    print("="*50)
    
    # 1. Profile
    print(f"Name: {data.get('full_name')}")
    print(f"Unit System: {data.get('unit_system')}")
    
    # 2. Goals
    goals = data.get('goals', [])
    if goals:
        print(f"\nDetected Goals/Events:")
        for g in goals:
            print(f" - {g.get('date', 'Unknown Date')}: {g.get('title', 'Untitled Event')}")
    else:
        print("\nNo upcoming race goals detected in Garmin Calendar.")
        
    # 3. Recent Activity Summary
    activities = data.get('recent_activities', [])
    print(f"\nRecent Activities ({len(activities)} found):")
    if activities:
        # Simple summary of last 3
        for a in activities[:3]:
            # Convert m/s to min/km
            avg_speed = a.get('avgSpeed', 0)
            dist_km = a.get('distance', 0) / 1000
            
            pace_str = "-"
            if avg_speed > 0:
                sec_km = 1000 / avg_speed
                m = int(sec_km // 60)
                s = int(sec_km % 60)
                pace_str = f"{m}:{s:02d}/km"
                
            print(f" - {a.get('startTimeLocal')}: {a.get('activityType', {}).get('typeKey')} | {dist_km:.2f}km @ {pace_str}")

    print("\n" + "-"*50)
    
    # Interactive Goal Setting
    if args.goal:
        print(f"Goal set via argument: {args.goal}")
        data['active_goal'] = args.goal
    else:
        print("Please verify the current training goal.")
        if goals:
            use_garmin = input("Use the detected goal(s) above? [Y/n]: ").strip().lower()
            if use_garmin == 'n':
                custom_goal = input("Enter your primary training goal (e.g., 'Sub 3:14 Marathon on Feb 27'): ").strip()
                data['active_goal'] = custom_goal
            else:
                data['active_goal'] = "Derived from Garmin Calendar"
        else:
            custom_goal = input("No goals found. Enter your primary training goal: ").strip()
            data['active_goal'] = custom_goal
        
    # User Notes
    if args.notes is not None:
        print(f"Notes set via argument: {args.notes}")
        data['user_notes'] = args.notes
    else:
        notes = input("Any specific constraints or requests for next week? (e.g., 'Sick, easy week', 'Long run Sunday'): ").strip()
        data['user_notes'] = notes

    with open(USER_CONTEXT_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"\nContext saved to {USER_CONTEXT_FILE}")
    print("You can now ask the Agent to generate a plan based on this file.")

def execute_plan(args):
    if not os.path.exists(SUGGESTED_PLAN_FILE):
        print(f"Error: {SUGGESTED_PLAN_FILE} not found. You must generate a plan first.")
        sys.exit(1)

    with open(SUGGESTED_PLAN_FILE, "r") as f:
        plan = json.load(f)

    if not plan:
        print("No workouts to upload.")
        return

    print("\n" + "="*50)
    print("PLAN EXECUTION VERIFICATION")
    print("="*50)
    print(f"Found {len(plan)} workouts to upload:")
    for w in plan:
        print(f" - {w.get('scheduleDate')}: {w.get('workoutName')}")
    
    if not args.yes:
        confirm = input("\nAre you satisfied with this plan and ready to upload? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled. Ask the Agent to regenerate the plan if needed.")
            return

    adapter = GarminAdapter()
    manager = WorkoutManager()
    
    success_count = 0
    
    for i, workout in enumerate(plan):
        print(f"\nProcessing {i+1}/{len(plan)}: {workout.get('workoutName')}")
        
        try:
            # Conversion happens here to ensure valid format
            garmin_json = manager.convert_to_garmin_format(workout)
            
            print("  Uploading...", end=" ")
            result = adapter.upload_workout(garmin_json)
            workout_id = result.get('workoutId')
            print(f"✓ (ID: {workout_id})")
            
            if workout_id:
                date_str = workout.get('scheduleDate')
                if isinstance(date_str, str):
                    if " " in date_str:
                        schedule_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        schedule_date = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    schedule_date = date_str

                print(f"  Scheduling to {schedule_date.strftime('%Y-%m-%d')}...", end=" ")
                res = adapter.schedule_workout(workout_id, schedule_date)
                if res:
                    print("✓")
                    success_count += 1
                else:
                    print("⚠ (schedule failed)")
                    
        except Exception as e:
            print(f"✗ Failed: {e}")

    print(f"\nCompleted. {success_count}/{len(plan)} workouts uploaded and scheduled.")

def main():
    parser = argparse.ArgumentParser(description="Garmin AI Agent Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Context (Fetch)
    parser_fetch = subparsers.add_parser("context", help="Fetch and verify user context")
    parser_fetch.add_argument("--days", type=int, default=14, help="Days of history to fetch")
    parser_fetch.add_argument("--goal", type=str, help="Manually set the training goal (skips interactive check)")
    parser_fetch.add_argument("--notes", type=str, help="Manually set user notes (skips interactive check)")
    
    # Execute
    parser_exec = subparsers.add_parser("execute", help="Upload and schedule the suggested plan")
    parser_exec.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    
    args = parser.parse_args()
    
    if args.command == "context":
        fetch_data(args)
    elif args.command == "execute":
        execute_plan(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
