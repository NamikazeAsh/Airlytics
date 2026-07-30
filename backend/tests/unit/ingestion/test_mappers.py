import datetime

from app.ingestion.providers.google_health.mappers import (
    extract_active_minutes,
    extract_daily_hrv,
    extract_daily_resting_heart_rate,
    extract_daily_spo2,
    extract_main_sleep,
    extract_total_calories,
    map_activity_log,
    map_daily_summary,
    map_sleep_log,
)


def test_map_daily_summary_extracts_steps_count():
    rollup = {
        "rollupDataPoints": [
            {
                "civilStartTime": {"date": {"year": 2026, "month": 7, "day": 20}},
                "civilEndTime": {"date": {"year": 2026, "month": 7, "day": 21}},
                "steps": {"countSum": "8123"},
            }
        ]
    }

    summary = map_daily_summary(datetime.date(2026, 7, 20), rollup)

    assert summary.steps_total == 8123
    assert summary.raw_payload == {"steps": rollup}


def test_map_daily_summary_handles_no_data_points():
    summary = map_daily_summary(datetime.date(2026, 7, 20), {"rollupDataPoints": []})
    assert summary.steps_total is None


def test_map_daily_summary_handles_missing_key():
    summary = map_daily_summary(datetime.date(2026, 7, 20), {})
    assert summary.steps_total is None


def test_extract_total_calories():
    rollup = {"rollupDataPoints": [{"totalCalories": {"kcalSum": 3154.1488230333334}}]}
    assert extract_total_calories(rollup) == 3154


def test_extract_total_calories_no_data():
    assert extract_total_calories({"rollupDataPoints": []}) is None


def test_extract_active_minutes_sums_all_levels():
    rollup = {
        "rollupDataPoints": [
            {
                "activeMinutes": {
                    "activeMinutesRollupByActivityLevel": [
                        {"activityLevel": "LIGHT", "activeMinutesSum": "181"},
                        {"activityLevel": "MODERATE", "activeMinutesSum": "25"},
                        {"activityLevel": "VIGOROUS", "activeMinutesSum": "62"},
                    ]
                }
            }
        ]
    }
    assert extract_active_minutes(rollup) == 268


def test_extract_daily_resting_heart_rate():
    response = {"dataPoints": [{"dailyRestingHeartRate": {"beatsPerMinute": "57"}}]}
    assert extract_daily_resting_heart_rate(response) == 57


def test_extract_daily_hrv():
    response = {"dataPoints": [{"dailyHeartRateVariability": {"averageHeartRateVariabilityMilliseconds": 76.9}}]}
    assert extract_daily_hrv(response) == 76.9


def test_extract_daily_spo2():
    response = {
        "dataPoints": [
            {"dailyOxygenSaturation": {"averagePercentage": 96.3, "lowerBoundPercentage": 94.3}}
        ]
    }
    assert extract_daily_spo2(response) == (96.3, 94.3)


def test_extract_daily_spo2_no_data():
    assert extract_daily_spo2({"dataPoints": []}) == (None, None)


def test_extract_main_sleep_picks_longest_session():
    response = {
        "dataPoints": [
            {"sleep": {"summary": {"minutesInSleepPeriod": "191", "minutesAsleep": "120"}}},
            {"sleep": {"summary": {"minutesInSleepPeriod": "480", "minutesAsleep": "430"}}},
        ]
    }
    duration, efficiency = extract_main_sleep(response)
    assert duration == 430
    assert efficiency == round(430 / 480 * 100)


def test_map_sleep_log_extracts_fields():
    point = {
        "dataPointName": "users/123/dataTypes/sleep/dataPoints/abc",
        "sleep": {
            "interval": {"startTime": "2026-07-23T18:29:00Z", "endTime": "2026-07-23T19:27:00Z"},
            "stages": [{"type": "AWAKE"}],
            "summary": {"minutesInSleepPeriod": "58", "minutesAsleep": "50"},
        },
    }
    result = map_sleep_log(point, datetime.date(2026, 7, 23))
    assert result["external_log_id"] == "users/123/dataTypes/sleep/dataPoints/abc"
    assert result["start_time"] == datetime.datetime(2026, 7, 23, 18, 29)
    assert result["end_time"] == datetime.datetime(2026, 7, 23, 19, 27)
    assert result["duration_minutes"] == 50
    assert result["efficiency"] == round(50 / 58 * 100)
    assert result["stages"] == [{"type": "AWAKE"}]


def test_map_activity_log_extracts_fields():
    point = {
        "dataPointName": "users/123/dataTypes/exercise/dataPoints/def",
        "exercise": {
            "interval": {"startTime": "2026-07-23T17:07:45.200Z", "endTime": "2026-07-23T17:31:36.800Z"},
            "exerciseType": "WALKING",
            "metricsSummary": {
                "caloriesKcal": 198,
                "distanceMillimeters": 1701500,
                "averageHeartRateBeatsPerMinute": "101",
            },
        },
    }
    result = map_activity_log(point, datetime.date(2026, 7, 23))
    assert result["external_activity_id"] == "users/123/dataTypes/exercise/dataPoints/def"
    assert result["activity_type"] == "WALKING"
    assert result["calories"] == 198
    assert result["avg_heart_rate"] == 101
    assert result["distance_km"] == 1.7015
    assert result["duration_minutes"] == 24
