"""
Unit tests for workout converter functions.
Run with: python -m pytest test_workout_converter.py -v
"""
import pytest
from workout_manager import WorkoutManager


class TestGetPaceWindow:
    """Tests for the get_pace_window function.
    
    The function returns (min_speed, max_speed) in m/s.
    Garmin expects m/s values for pace.zone.
    """
    
    def setup_method(self):
        self.manager = WorkoutManager()

    def test_marathon_pace_4_36(self):
        """Test MP 4:36/km converts to correct pace values."""
        # 4:36/km = 276 sec/km
        # With ±10 sec margin: 266-286 sec/km
        # Speed (m/s) = 1000 / sec_per_km
        # Slowest (286s): 1000/286 = 3.4965 m/s
        # Fastest (266s): 1000/266 = 3.7594 m/s
        min_speed, max_speed = self.manager.get_pace_window("4:36", margin_sec=10)
        
        assert 3.49 < min_speed < 3.50, f"min_speed {min_speed} should be ~3.496"
        assert 3.75 < max_speed < 3.77, f"max_speed {max_speed} should be ~3.759"
    
    def test_easy_pace_5_15(self):
        """Test easy pace 5:15/km converts to correct pace values."""
        # 5:15/km = 315 sec/km
        # With ±20 sec margin: 295-335 sec/km
        # Slowest (335s): 1000/335 = 2.985 m/s
        # Fastest (295s): 1000/295 = 3.389 m/s
        min_speed, max_speed = self.manager.get_pace_window("5:15", margin_sec=20)
        
        assert 2.98 < min_speed < 2.99, f"min_speed {min_speed} should be ~2.985"
        assert 3.38 < max_speed < 3.40, f"max_speed {max_speed} should be ~3.390"
    
    def test_interval_pace_4_15(self):
        """Test interval pace 4:15/km converts to correct pace values."""
        # 4:15/km = 255 sec/km
        # With ±10 sec margin: 245-265 sec/km
        # Slowest (265s): 1000/265 = 3.773 m/s
        # Fastest (245s): 1000/245 = 4.081 m/s
        min_speed, max_speed = self.manager.get_pace_window("4:15", margin_sec=10)
        
        assert 3.77 < min_speed < 3.78, f"min_speed {min_speed} should be ~3.773"
        assert 4.08 < max_speed < 4.09, f"max_speed {max_speed} should be ~4.081"
    
    def test_tempo_pace_4_25(self):
        """Test tempo pace 4:25/km converts to correct pace values."""
        # 4:25/km = 265 sec/km
        # With ±10 sec margin: 255-275 sec/km
        # Slowest (275s): 1000/275 = 3.636 m/s
        # Fastest (255s): 1000/255 = 3.921 m/s
        min_speed, max_speed = self.manager.get_pace_window("4:25", margin_sec=10)
        
        assert 3.63 < min_speed < 3.64, f"min_speed {min_speed} should be ~3.636"
        assert 3.92 < max_speed < 3.93, f"max_speed {max_speed} should be ~3.921"
    
    def test_min_speed_less_than_max(self):
        """Slower pace (lower m/s) should be less than faster pace (higher m/s)."""
        min_speed, max_speed = self.manager.get_pace_window("5:00", margin_sec=10)
        assert min_speed < max_speed, "min_speed (slower) should be less than max_speed (faster)"


class TestConvertWorkoutToGarminFormat:
    """Tests for the convert_to_garmin_format function."""
    
    def setup_method(self):
        self.manager = WorkoutManager()

    def test_simple_workout_structure(self):
        """Test basic workout structure is correct."""
        workout = {
            "workoutName": "Test Workout",
            "description": "Test description",
            "steps": [
                {"type": "WorkoutStep", "intensity": "WARMUP", "durationType": "DISTANCE", 
                 "durationValue": 2000, "targetType": "NONE"}
            ]
        }
        
        result = self.manager.convert_to_garmin_format(workout)
        
        assert result["workoutName"] == "Test Workout"
        assert result["sportType"]["sportTypeKey"] == "running"
        assert len(result["workoutSegments"]) == 1
        assert len(result["workoutSegments"][0]["workoutSteps"]) == 1
    
    def test_pace_target_values_passed_directly(self):
        """Test that pace target values are passed directly without conversion."""
        # Pace values in m/s
        min_speed = 2.98  # ~5:35/km
        max_speed = 3.39  # ~4:55/km
        
        workout = {
            "workoutName": "Pace Target Test",
            "steps": [
                {"type": "WorkoutStep", "intensity": "ACTIVE", "durationType": "DISTANCE",
                 "durationValue": 5000, "targetType": "SPEED", 
                 "targetValueOne": min_speed, "targetValueTwo": max_speed}
            ]
        }
        
        result = self.manager.convert_to_garmin_format(workout)
        step = result["workoutSegments"][0]["workoutSteps"][0]
        
        # Values should be passed directly
        assert step["targetValueOne"] == min_speed
        assert step["targetValueTwo"] == max_speed
    
    def test_pace_zone_target_type(self):
        """Test that pace target uses pace.zone type."""
        workout = {
            "workoutName": "Pace Zone Test",
            "steps": [
                {"type": "WorkoutStep", "intensity": "ACTIVE", "durationType": "DISTANCE",
                 "durationValue": 1000, "targetType": "SPEED",
                 "targetValueOne": 3.0, "targetValueTwo": 3.2}
            ]
        }
        
        result = self.manager.convert_to_garmin_format(workout)
        step = result["workoutSegments"][0]["workoutSteps"][0]
        
        assert step["targetType"]["workoutTargetTypeId"] == 6, \
            "Should use pace.zone (id=6)"
        assert step["targetType"]["workoutTargetTypeKey"] == "pace.zone"
    
    def test_repeat_step_structure(self):
        """Test repeat step (intervals) structure."""
        workout = {
            "workoutName": "Interval Test",
            "steps": [
                {"type": "WorkoutRepeatStep", "repeatValue": 5, "steps": [
                    {"type": "WorkoutStep", "intensity": "INTERVAL", "durationType": "DISTANCE",
                     "durationValue": 1000, "targetType": "SPEED",
                     "targetValueOne": 3.8, "targetValueTwo": 4.0},
                    {"type": "WorkoutStep", "intensity": "REST", "durationType": "TIME",
                     "durationValue": 90, "targetType": "NONE"}
                ]}
            ]
        }
        
        result = self.manager.convert_to_garmin_format(workout)
        repeat_step = result["workoutSegments"][0]["workoutSteps"][0]
        
        assert repeat_step["type"] == "RepeatGroupDTO"
        assert repeat_step["numberOfIterations"] == 5
        assert len(repeat_step["workoutSteps"]) == 2
        
        # Check interval step has correct pace values
        interval_step = repeat_step["workoutSteps"][0]
        assert interval_step["targetValueOne"] == 3.8
        assert interval_step["targetValueTwo"] == 4.0
    
    def test_no_target_type(self):
        """Test step with no target."""
        workout = {
            "workoutName": "No Target Test",
            "steps": [
                {"type": "WorkoutStep", "intensity": "COOLDOWN", "durationType": "DISTANCE",
                 "durationValue": 2000, "targetType": "NONE"}
            ]
        }
        
        result = self.manager.convert_to_garmin_format(workout)
        step = result["workoutSegments"][0]["workoutSteps"][0]
        
        assert step["targetType"]["workoutTargetTypeKey"] == "no.target"
        assert "targetValueOne" not in step
        assert "targetValueTwo" not in step


class TestPaceConversionEndToEnd:
    """End-to-end tests verifying pace values are correct for Garmin display."""
    
    def setup_method(self):
        self.manager = WorkoutManager()

    def test_duration_values_set_correctly(self):
        """Test that duration values (distance/time) are correctly set in endCondition."""
        workout = {
            "workoutName": "Duration Test",
            "steps": [
                {"type": "WorkoutStep", "intensity": "ACTIVE", "durationType": "DISTANCE", "durationValue": 5000},
                {"type": "WorkoutStep", "intensity": "REST", "durationType": "TIME", "durationValue": 120}
            ]
        }
        
        result = self.manager.convert_to_garmin_format(workout)
        steps = result["workoutSegments"][0]["workoutSteps"]
        
        # Check Distance Step
        dist_step = steps[0]
        assert dist_step["endCondition"]["conditionTypeKey"] == "distance"
        assert dist_step["endCondition"]["conditionTypeId"] == 3
        assert dist_step["endCondition"]["displayable"] is True
        assert dist_step["endConditionValue"] == 5000.0
        # Check Unit (New)
        assert "preferredEndConditionUnit" in dist_step
        assert dist_step["preferredEndConditionUnit"]["unitKey"] == "kilometer"
        assert dist_step["preferredEndConditionUnit"]["factor"] == 100000.0
        
        # Check Time Step
        time_step = steps[1]
        assert time_step["endCondition"]["conditionTypeKey"] == "time"
        assert time_step["endCondition"]["conditionTypeId"] == 2
        assert time_step["endConditionValue"] == 120.0
        # Time steps usually don't have unit object in this implementation
        assert "preferredEndConditionUnit" not in time_step

    def test_marathon_pace_workout(self):
        """Test a marathon pace workout has correct pace values for Garmin display."""
        # MP = 4:36/km ± 10s
        min_speed, max_speed = self.manager.get_pace_window("4:36", margin_sec=10)
        
        workout = {
            "workoutName": "MP Test",
            "steps": [
                {"type": "WorkoutStep", "intensity": "ACTIVE", "durationType": "DISTANCE",
                 "durationValue": 5000, "targetType": "SPEED",
                 "targetValueOne": min_speed, "targetValueTwo": max_speed}
            ]
        }
        
        result = self.manager.convert_to_garmin_format(workout)
        step = result["workoutSegments"][0]["workoutSteps"][0]
        
        # Verify the values
        target_one = step["targetValueOne"]  # Slowest pace (min speed)
        target_two = step["targetValueTwo"]  # Fastest pace (max speed)
        
        # Convert back to sec/km to verify: 1000 / m/s
        # Target: ~286 sec (4:46)
        garmin_slow_sec = 1000 / target_one
        # Target: ~266 sec (4:26)
        garmin_fast_sec = 1000 / target_two
        
        assert 285 < garmin_slow_sec < 287, f"Slow pace should be ~286 sec (4:46), got {garmin_slow_sec}"
        assert 265 < garmin_fast_sec < 267, f"Fast pace should be ~266 sec (4:26), got {garmin_fast_sec}"
        
        # Convert to min:sec for clarity
        fast_min = int(garmin_fast_sec // 60)
        fast_sec = int(garmin_fast_sec % 60)
        slow_min = int(garmin_slow_sec // 60)
        slow_sec = int(garmin_slow_sec % 60)
        
        assert fast_min == 4 and 25 <= fast_sec <= 27, f"Fast pace should be ~4:26, got {fast_min}:{fast_sec}"
        assert slow_min == 4 and 45 <= slow_sec <= 47, f"Slow pace should be ~4:46, got {slow_min}:{slow_sec}"
    
    def test_easy_pace_display_values(self):
        """Test easy pace values display correctly."""
        # Easy = 5:15/km ± 20s
        min_speed, max_speed = self.manager.get_pace_window("5:15", margin_sec=20)
        
        # Garmin will display pace based on m/s
        # Slower limit (min speed) -> 5:35/km (335s)
        # Faster limit (max speed) -> 4:55/km (295s)
        
        garmin_slow_sec = 1000 / min_speed
        garmin_fast_sec = 1000 / max_speed
        
        fast_min, fast_sec = divmod(int(round(garmin_fast_sec)), 60)
        slow_min, slow_sec = divmod(int(round(garmin_slow_sec)), 60)
        
        assert fast_min == 4 and 54 <= fast_sec <= 56, f"Expected ~4:55, got {fast_min}:{fast_sec}"
        assert slow_min == 5 and 34 <= slow_sec <= 36, f"Expected ~5:35, got {slow_min}:{slow_sec}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
