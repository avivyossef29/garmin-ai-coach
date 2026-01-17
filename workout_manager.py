class WorkoutManager:
    def __init__(self):
        # Default paces (min/km) for 3:14 Marathon - CAN BE OVERRIDDEN BY AI AGENT IN PLAN
        self.paces = {
            "MP": "4:36",
            "INT": "4:15",
            "TEMPO": "4:25",
            "EASY": "5:15"
        }

    def get_pace_window(self, pace_str, margin_sec=5):
        """
        Converts '4:30' (min/km) to Garmin's pace.zone format (m/s).
        Returns a tuple: (min_speed, max_speed) in meters/second.
        """
        mins, secs = map(int, pace_str.split(':'))
        total_sec = mins * 60 + secs
        
        slowest_sec = total_sec + margin_sec
        fastest_sec = total_sec - margin_sec
        
        min_speed = round(1000 / slowest_sec, 4)
        max_speed = round(1000 / fastest_sec, 4)
        
        return min_speed, max_speed

    def convert_to_garmin_format(self, workout):
        """
        Converts simplified workout format to Garmin API format.
        """
        # Step type mappings
        STEP_TYPES = {
            "WARMUP": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
            "COOLDOWN": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
            "INTERVAL": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
            "RECOVERY": {"stepTypeId": 4, "stepTypeKey": "recovery", "displayOrder": 4},
            "REST": {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5},
            "ACTIVE": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
        }
        
        # Condition type mappings
        CONDITION_TYPES = {
            "DISTANCE": {"conditionTypeId": 3, "conditionTypeKey": "distance", "displayOrder": 3, "displayable": True},
            "TIME": {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True},
        }
        
        # Target type mappings
        TARGET_TYPES = {
            "NONE": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1},
            "SPEED": {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6},
        }
        
        # Sport type
        sport_type = {"sportTypeId": 1, "sportTypeKey": "running"}
        
        # Unit definitions
        UNIT_KILOMETER = {"unitId": 2, "unitKey": "kilometer", "factor": 100000.0}
        
        def convert_step(step, step_order):
            """Convert a single step to Garmin format."""
            if step.get("type") == "WorkoutRepeatStep":
                repeat_steps = []
                sub_step_order = 1
                for sub_step in step.get("steps", []):
                    converted = convert_step(sub_step, sub_step_order)
                    repeat_steps.append(converted)
                    sub_step_order += 1
                
                return {
                    "type": "RepeatGroupDTO",
                    "stepOrder": step_order,
                    "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                    "numberOfIterations": step.get("repeatValue", 1),
                    "workoutSteps": repeat_steps,
                    "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations"},
                    "endConditionValue": float(step.get("repeatValue", 1)),
                    "smartRepeat": False
                }
            else:
                intensity = step.get("intensity", "ACTIVE")
                duration_type = step.get("durationType", "DISTANCE")
                duration_value = step.get("durationValue", 0)
                target_type_key = step.get("targetType", "NONE")
                
                step_type = STEP_TYPES.get(intensity, STEP_TYPES["ACTIVE"])
                condition = CONDITION_TYPES.get(duration_type, CONDITION_TYPES["DISTANCE"])
                target_type = TARGET_TYPES.get(target_type_key, TARGET_TYPES["NONE"])
                
                result = {
                    "type": "ExecutableStepDTO",
                    "stepOrder": step_order,
                    "stepType": step_type,
                    "endCondition": condition,
                    "endConditionValue": float(duration_value),
                    "targetType": target_type,
                }
                
                # Add unit for Distance
                if duration_type == "DISTANCE":
                    result["preferredEndConditionUnit"] = UNIT_KILOMETER
                
                # Add speed target if specified
                if target_type_key == "SPEED" and "targetValueOne" in step and "targetValueTwo" in step:
                    result["targetValueOne"] = step["targetValueOne"]
                    result["targetValueTwo"] = step["targetValueTwo"]
                
                return result
        
        workout_steps = []
        for idx, step in enumerate(workout.get("steps", []), start=1):
            step_order = step.get("stepOrder", idx)
            converted = convert_step(step, step_order)
            workout_steps.append(converted)
        
        def calculate_total_distance_time(steps):
            total_dist = 0
            total_time = 0
            for step in steps:
                if step.get("type") == "WorkoutRepeatStep":
                    repeat_count = step.get("repeatValue", 1)
                    sub_dist, sub_time = calculate_total_distance_time(step.get("steps", []))
                    total_dist += sub_dist * repeat_count
                    total_time += sub_time * repeat_count
                else:
                    if step.get("durationType") == "DISTANCE":
                        total_dist += step.get("durationValue", 0)
                    elif step.get("durationType") == "TIME":
                        total_time += step.get("durationValue", 0)
            return total_dist, total_time
        
        total_distance, total_time = calculate_total_distance_time(workout.get("steps", []))
        estimated_distance = total_distance + (total_time * 3.33)
        estimated_duration_sec = int((estimated_distance / 1000) * 300) + total_time
        
        garmin_workout = {
            "workoutName": workout.get("workoutName", "Untitled Workout"),
            "description": workout.get("description", ""),
            "sportType": sport_type,
            "estimatedDurationInSecs": max(estimated_duration_sec, 1800),
            "workoutSegments": [
                {
                    "segmentOrder": 1,
                    "sportType": sport_type,
                    "workoutSteps": workout_steps
                }
            ]
        }
        
        return garmin_workout
