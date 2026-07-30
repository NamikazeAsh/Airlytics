import datetime

from app.ingestion.base import DailySummary


def parse_utc(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def map_daily_summary(date: datetime.date, steps_rollup: dict) -> DailySummary:
    steps_total = None
    for point in steps_rollup.get("rollupDataPoints", []):
        steps = point.get("steps")
        if steps is not None:
            steps_total = int(steps["countSum"])

    return DailySummary(date=date, steps_total=steps_total, raw_payload={"steps": steps_rollup})


def extract_total_calories(rollup: dict) -> int | None:
    for point in rollup.get("rollupDataPoints", []):
        calories = point.get("totalCalories")
        if calories is not None:
            return round(calories["kcalSum"])
    return None


def extract_active_minutes(rollup: dict) -> int | None:
    total = 0
    found = False
    for point in rollup.get("rollupDataPoints", []):
        active = point.get("activeMinutes")
        if active is not None:
            for level in active.get("activeMinutesRollupByActivityLevel", []):
                total += int(level.get("activeMinutesSum", 0))
                found = True
    return total if found else None


def extract_daily_resting_heart_rate(response: dict) -> int | None:
    for point in response.get("dataPoints", []):
        data = point.get("dailyRestingHeartRate")
        if data is not None:
            return int(data["beatsPerMinute"])
    return None


def extract_daily_hrv(response: dict) -> float | None:
    for point in response.get("dataPoints", []):
        data = point.get("dailyHeartRateVariability")
        if data is not None and "averageHeartRateVariabilityMilliseconds" in data:
            return data["averageHeartRateVariabilityMilliseconds"]
    return None


def extract_daily_spo2(response: dict) -> tuple[float | None, float | None]:
    for point in response.get("dataPoints", []):
        data = point.get("dailyOxygenSaturation")
        if data is not None:
            return data.get("averagePercentage"), data.get("lowerBoundPercentage")
    return None, None


def extract_main_sleep(response: dict) -> tuple[int | None, int | None]:
    """Among all sleep sessions overlapping the day (main sleep + naps), picks
    the longest as 'main sleep' for the daily_metrics summary — Google's API
    has no explicit is-main-sleep flag, unlike legacy Fitbit."""
    best_in_period = -1
    best = (None, None)
    for point in response.get("dataPoints", []):
        sleep = point.get("sleep")
        if sleep is None:
            continue
        summary = sleep.get("summary", {})
        in_period = summary.get("minutesInSleepPeriod")
        if in_period is None:
            continue
        in_period = int(in_period)
        if in_period > best_in_period:
            asleep = summary.get("minutesAsleep")
            asleep = int(asleep) if asleep is not None else None
            efficiency = round(asleep / in_period * 100) if asleep and in_period else None
            best_in_period = in_period
            best = (asleep, efficiency)
    return best


def map_sleep_log(point: dict, date: datetime.date) -> dict:
    sleep = point["sleep"]
    interval = sleep["interval"]
    summary = sleep.get("summary", {})
    asleep = summary.get("minutesAsleep")
    in_period = summary.get("minutesInSleepPeriod")
    asleep = int(asleep) if asleep is not None else None
    in_period = int(in_period) if in_period is not None else None
    efficiency = round(asleep / in_period * 100) if asleep and in_period else None

    return {
        "external_log_id": point["dataPointName"],
        "date": date,
        "start_time": parse_utc(interval["startTime"]),
        "end_time": parse_utc(interval["endTime"]),
        "duration_minutes": asleep,
        "efficiency": efficiency,
        "stages": sleep.get("stages"),
    }


def map_activity_log(point: dict, date: datetime.date) -> dict:
    exercise = point["exercise"]
    interval = exercise["interval"]
    metrics = exercise.get("metricsSummary", {})
    calories = metrics.get("caloriesKcal")
    avg_hr = metrics.get("averageHeartRateBeatsPerMinute")
    distance_mm = metrics.get("distanceMillimeters")
    start = parse_utc(interval["startTime"])
    end = parse_utc(interval["endTime"])

    return {
        "external_activity_id": point["dataPointName"],
        "date": date,
        "activity_type": exercise.get("exerciseType", "OTHER"),
        "start_time": start,
        "duration_minutes": round((end - start).total_seconds() / 60),
        "calories": round(calories) if calories is not None else None,
        "avg_heart_rate": int(avg_hr) if avg_hr is not None else None,
        "distance_km": (distance_mm / 1_000_000) if distance_mm is not None else None,
    }
