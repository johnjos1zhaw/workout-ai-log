import json
import os
from datetime import datetime
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

EXPECTED_COLUMNS = [
    "date",
    "workout",
    "exercise",
    "exercise_standardized",
    "set_number",
    "target_sets",
    "reps",
    "duration_sec",
    "weight_kg",
    "load_type",
    "is_unilateral_note",
    "notes",
]

WORKOUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "workout": {"type": "string"},
                    "exercise": {"type": "string"},
                    "exercise_standardized": {"type": "string"},
                    "set_number": {"type": "integer"},
                    "target_sets": {"type": "integer"},
                    "reps": {"type": ["integer", "null"]},
                    "duration_sec": {"type": ["integer", "null"]},
                    "weight_kg": {"type": ["number", "null"]},
                    "load_type": {
                        "type": "string",
                        "enum": ["external", "bodyweight", "duration", "unknown"],
                    },
                    "is_unilateral_note": {"type": ["string", "null"]},
                    "notes": {"type": ["string", "null"]},
                },
                "required": [
                    "date",
                    "workout",
                    "exercise",
                    "exercise_standardized",
                    "set_number",
                    "target_sets",
                    "reps",
                    "duration_sec",
                    "weight_kg",
                    "load_type",
                    "is_unilateral_note",
                    "notes",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sets"],
    "additionalProperties": False,
}


def parse_workout_note(raw_note: str) -> pd.DataFrame:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
You are a workout log parser.

Convert the user's messy workout note into structured workout set rows.

Rules:
- Output one row per set.
- Date format must be YYYY-MM-DD.
- Input dates like 16.6.26 mean 2026-06-16.
- workout is the workout title from the first line, e.g. "upper 1".
- target_sets is total number of sets for that exercise.
- For "3x12x70kg", create 3 rows, set_number 1-3, reps 12, weight_kg 70.
- For "1x10x60kg / 1x7x60kg", create separate rows.
- For EMOM push-ups/pull-ups, create separate rows for each set.
- Bodyweight exercises have load_type "bodyweight" and weight_kg null.
- Weighted exercises have load_type "external".
- Duration exercises use duration_sec.
- Preserve relevant comments in notes.
- Standardize common German/abbreviated exercise names:
  - Schulterdrücken kurzhantel -> Shoulder Press DB
  - Seitheben kzh -> Seitheben DB
  - Reverse fly maschine -> Reverse Fly Machine
  - pullups -> EMOM Pull-ups if listed under EMOM
  - push ups -> EMOM Push-ups if listed under EMOM

Messy workout note:
{raw_note}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "workout_sets",
                "schema": WORKOUT_SCHEMA,
                "strict": True,
            }
        },
    )

    parsed = json.loads(response.output_text)
    df = pd.DataFrame(parsed["sets"])

    df = df[EXPECTED_COLUMNS]
    df["date"] = pd.to_datetime(df["date"]).dt.date

    numeric_cols = ["set_number", "target_sets", "reps", "duration_sec", "weight_kg"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df