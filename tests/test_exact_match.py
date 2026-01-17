import json
import pytest
from workout_manager import WorkoutManager

class TestExactWorkoutMatch:
    """Test that the generated workout matches the manually fixed JSON exactly where it matters."""
    
    def test_match_fixed_json(self):
        # Load the manually fixed JSON
        with open("real_fixed_workout.json", "r") as f:
            fixed_workout = json.load(f)
            
        # Reconstruct the input workout dictionary based on the fixed JSON's intent
        # "33km: 12k Easy, 4x(3km MP + 1km Easy), 5km Cool. First big MP test."
        # Using the same pace values as in the fixed JSON for precision matching
        
        # Pace values from JSON:
        # Easy (Warmup/Cool/Recovery): 2.9850747 - 3.3898305 m/s
        # MP (Interval): 3.4965035 - 3.7593985 m/s
        
        easy_min, easy_max = 2.9850747, 3.3898305
        mp_min, mp_max = 3.4965035, 3.7593985
        
        workout_input = {
            "workoutName": "W1_Fri_33km_Mixed",
            "description": "33km: 12k Easy, 4x(3km MP + 1km Easy), 5km Cool. First big MP test.",
            "steps": [
                {"type": "WorkoutStep", "intensity": "WARMUP", "durationType": "DISTANCE", "durationValue": 12000, "targetType": "SPEED", "targetValueOne": easy_min, "targetValueTwo": easy_max},
                {"type": "WorkoutRepeatStep", "repeatValue": 4, "steps": [
                    {"type": "WorkoutStep", "intensity": "INTERVAL", "durationType": "DISTANCE", "durationValue": 3000, "targetType": "SPEED", "targetValueOne": mp_min, "targetValueTwo": mp_max},
                    {"type": "WorkoutStep", "intensity": "RECOVERY", "durationType": "DISTANCE", "durationValue": 1000, "targetType": "SPEED", "targetValueOne": easy_min, "targetValueTwo": easy_max}
                ]},
                {"type": "WorkoutStep", "intensity": "COOLDOWN", "durationType": "DISTANCE", "durationValue": 5000, "targetType": "SPEED", "targetValueOne": easy_min, "targetValueTwo": easy_max}
            ]
        }
        
        manager = WorkoutManager()
        generated = manager.convert_to_garmin_format(workout_input)
        
        # Compare Key Structure
        
        # 1. Check Sport Type
        assert generated["sportType"]["sportTypeId"] == fixed_workout["sportType"]["sportTypeId"]
        assert generated["sportType"]["sportTypeKey"] == fixed_workout["sportType"]["sportTypeKey"]
        
        # 2. Check Segments
        gen_segment = generated["workoutSegments"][0]
        fixed_segment = fixed_workout["workoutSegments"][0]
        
        assert len(gen_segment["workoutSteps"]) == len(fixed_segment["workoutSteps"])
        
        # 3. Check Steps
        for gen_step, fixed_step in zip(gen_segment["workoutSteps"], fixed_segment["workoutSteps"]):
            assert gen_step["type"] == fixed_step["type"]
            assert gen_step["stepOrder"] == fixed_step["stepOrder"]
            
            # Check Step Type
            assert gen_step["stepType"]["stepTypeId"] == fixed_step["stepType"]["stepTypeId"]
            assert gen_step["stepType"]["stepTypeKey"] == fixed_step["stepType"]["stepTypeKey"]
            
            # Check End Condition
            if "endCondition" in fixed_step:
                assert gen_step["endCondition"]["conditionTypeId"] == fixed_step["endCondition"]["conditionTypeId"]
                assert gen_step["endCondition"]["conditionTypeKey"] == fixed_step["endCondition"]["conditionTypeKey"]
                
                # Check Value
                if "endConditionValue" in fixed_step and fixed_step["endConditionValue"] is not None:
                    assert gen_step["endConditionValue"] == fixed_step["endConditionValue"]
                
                # Check Unit (Crucial Part)
                if "preferredEndConditionUnit" in fixed_step and fixed_step["preferredEndConditionUnit"]:
                    assert "preferredEndConditionUnit" in gen_step
                    assert gen_step["preferredEndConditionUnit"]["unitId"] == fixed_step["preferredEndConditionUnit"]["unitId"]
                    assert gen_step["preferredEndConditionUnit"]["unitKey"] == fixed_step["preferredEndConditionUnit"]["unitKey"]
                    assert gen_step["preferredEndConditionUnit"]["factor"] == fixed_step["preferredEndConditionUnit"]["factor"]

            # Check Recursive Steps (for repeats)
            if gen_step["type"] == "RepeatGroupDTO":
                assert len(gen_step["workoutSteps"]) == len(fixed_step["workoutSteps"])
                for sub_gen, sub_fixed in zip(gen_step["workoutSteps"], fixed_step["workoutSteps"]):
                    # Check Sub Step Type
                    assert sub_gen["stepType"]["stepTypeId"] == sub_fixed["stepType"]["stepTypeId"]
                    assert sub_gen["stepType"]["stepTypeKey"] == sub_fixed["stepType"]["stepTypeKey"]
                    
                    # Check Sub Step End Condition
                    assert sub_gen["endCondition"]["conditionTypeId"] == sub_fixed["endCondition"]["conditionTypeId"]
                    
                    # Check Sub Step Unit
                    if "preferredEndConditionUnit" in sub_fixed and sub_fixed["preferredEndConditionUnit"]:
                        assert sub_gen["preferredEndConditionUnit"]["unitId"] == sub_fixed["preferredEndConditionUnit"]["unitId"]
                        assert sub_gen["preferredEndConditionUnit"]["unitKey"] == sub_fixed["preferredEndConditionUnit"]["unitKey"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
