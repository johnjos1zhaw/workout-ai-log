import re
import pandas as pd

EXERCISE_ALIASES = {
    "bulgarian split squat": ("Bulgarian Split Squat", None),
    "bulgarian split squats": ("Bulgarian Split Squat", None),

    "cable row narrow": ("Cable Row", "narrow grip"),
    "cable row narrow grip": ("Cable Row", "narrow grip"),

    "calf raise": ("Calf Raise Seated", None),
    "waden": ("Calf Raise Seated", None),

    "biceps curls db": ("Dumbbell Curl", None),
    "dumbell curl seated": ("Dumbbell Curl", "seated"),
    "dumbbell curl seated": ("Dumbbell Curl", "seated"),

    "hip thrust machine": ("Hip Thrust Machine", None),
    "hiptrust maschine": ("Hip Thrust Machine", None),
    "hip thrust maschine": ("Hip Thrust Machine", None),

    "leg extension": ("Leg Extension", None),
    "leg extension single": ("Leg Extension", "single-leg"),
    "leg extension per side": ("Leg Extension", "single-leg"),

    "rdl": ("Romanian Deadlift", None),
    "romanian deadlift": ("Romanian Deadlift", None),

    "rope pushdown": ("Triceps Rope Pushdown", None),
    "rope triceps pushdown": ("Triceps Rope Pushdown", None),
    "triceps pull down rope": ("Triceps Rope Pushdown", None),
    "triceps pulldown rope": ("Triceps Rope Pushdown", None),

    "hamstring curl lying": ("Leg Curl", "lying"),
    "leg curl": ("Leg Curl", None),
    "leg curl lying": ("Leg Curl", "lying"),
    "leg curl seated": ("Leg Curl", "seated"),
}

def clean_name(name: str) -> str:
    if pd.isna(name):
        return ""

    name = str(name).lower().strip()
    name = name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name

def normalize_exercise_name(exercise: str) -> tuple[str, str | None]:
    key = clean_name(exercise)

    if key in EXERCISE_ALIASES:
        return EXERCISE_ALIASES[key]

    return exercise.strip().title(), None

def normalize_exercise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    standardized = []
    variation_notes = []

    for _, row in df.iterrows():
        canonical, variation = normalize_exercise_name(row["exercise"])

        standardized.append(canonical)

        existing_note = row.get("is_unilateral_note", None)

        notes = []
        if pd.notna(existing_note) and str(existing_note).strip():
            notes.append(str(existing_note).strip())
        if variation:
            notes.append(variation)

        variation_notes.append(", ".join(dict.fromkeys(notes)) if notes else None)

    df["exercise_standardized"] = standardized
    df["is_unilateral_note"] = variation_notes

    return df