"""Leakage-free, one-session-ahead strength baseline and decision rules."""
from dataclasses import dataclass
from math import ceil
from statistics import mean, median
from src import training

MIN_EVALUATION_SESSIONS = 12
MIN_MODEL_SESSIONS = 60  # Conservative project gate, not a statistical theorem.


def strength_series(exercise_name, path=training.DB):
    """One observed best Epley e1RM per completed session, in date order."""
    with training.connect(path) as con:
        result = training.rows(con, """
            SELECT s.id, s.session_date, se.name, ss.reps, ss.weight_kg
            FROM sessions s JOIN session_exercises se ON se.session_id=s.id
            JOIN session_sets ss ON ss.session_exercise_id=se.id
            WHERE s.status='completed' AND se.name=? AND ss.reps>0 AND ss.weight_kg>0
            ORDER BY s.session_date,s.id
        """, [exercise_name])
    best = {}
    for row in result:
        key = row["id"]
        value = float(row["weight_kg"]) * (1 + int(row["reps"]) / 30)
        if key not in best or value > best[key]["e1rm"]:
            best[key] = {"session_id": key, "date": row["session_date"],
                         "e1rm": round(value, 2), "weight_kg": row["weight_kg"],
                         "reps": row["reps"]}
    return sorted(best.values(), key=lambda row: (row["date"], row["session_id"]))


def evaluate_last_value(series):
    """Chronological 60/20/20 split; no future value enters a prediction."""
    n = len(series)
    if n < MIN_EVALUATION_SESSIONS:
        return {"status": "insufficient", "n": n, "mae": None, "test_n": 0}
    test_start = max(2, n - ceil(n * 0.2))
    validation_start = max(1, test_start - ceil(n * 0.2))
    validation_errors = [abs(series[i]["e1rm"] - series[i-1]["e1rm"])
                         for i in range(validation_start, test_start)]
    errors = [abs(series[i]["e1rm"] - series[i-1]["e1rm"])
              for i in range(test_start, n)]
    return {"status": "evaluated", "n": n,
            "train_n": validation_start, "validation_n": test_start-validation_start,
            "validation_mae": round(mean(validation_errors), 2),
            "test_n": len(errors), "mae": round(mean(errors), 2),
            "method": "last observed session e1RM", "split": "chronological 60/20/20"}


def decide(series):
    """Transparent signal, never an optimal-load prescription."""
    if len(series) < 6:
        return "beibehalten", "Weniger als sechs vergleichbare Einheiten."
    recent = median(row["e1rm"] for row in series[-3:])
    previous = median(row["e1rm"] for row in series[-6:-3])
    change = (recent / previous - 1) if previous > 0 else 0
    if change > 0.03:
        return "erhöhen", f"Median der letzten drei Einheiten liegt {change:.1%} über den drei vorherigen."
    if change < -0.05:
        return "reduzieren/überprüfen", f"Median der letzten drei Einheiten liegt {abs(change):.1%} darunter."
    return "beibehalten", f"Veränderung der Dreier-Mediane beträgt {change:.1%}."


def analyze(exercise_name, path=training.DB):
    series = strength_series(exercise_name, path)
    if not series:
        return {"exercise": exercise_name, "status": "no_data",
                "recommendation": "beibehalten", "reason": "Keine gültigen Kraftsätze.",
                "forecast_e1rm": None, "evaluation": {"status": "insufficient", "n": 0}}
    category, reason = decide(series)
    evaluation = evaluate_last_value(series)
    return {"exercise": exercise_name, "status": "baseline",
            "forecast_e1rm": series[-1]["e1rm"],
            "latest_date": str(series[-1]["date"]),
            "latest_weight_kg": series[-1]["weight_kg"],
            "latest_reps": series[-1]["reps"],
            "recommendation": category, "reason": reason,
            "evaluation": evaluation, "series": series}
