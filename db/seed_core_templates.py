"""Create the four core workout templates from recurring historical exercises.

Existing templates are never overwritten. Run --test-copy before a live seed.
"""
import argparse
import shutil
import tempfile
from pathlib import Path
from src import training


DEFINITIONS = {
    "Leg 1": [
        "Leg Extension", "Hacksquat", "Romanian Deadlift",
        "Bulgarian Split Squat", "Waden Excentric Smith Machine",
        "Hipthrust Maschine",
    ],
    "Upper Body 1": [
        "Bench Press", "Row Machine", "Shoulder Press Db",
        "Seitheben Kzh", "Face Pulls", "Reverse Fly Maschine",
    ],
    "Leg 2": [
        "Leg Curl", "Leg Extension", "Hacksquat",
        "Bulg Split Squat", "Hip Thrust", "Waden Smith Machine",
    ],
    "Upper Body 2": [
        "Incline Bench", "Cable Row Shoulderwide-Grip", "Lat Pulldowns",
        "Bizeps Sz Curl Seated", "Dumbell Bizeps Curls Seated",
        "Triceps Rope Pushdown", "Reverse Fly Maschine",
    ],
}


def seed(path=training.DB):
    catalog = {row["name"]: row for row in training.exercises(path, archived=True)}
    missing = sorted({name for names in DEFINITIONS.values() for name in names
                      if name not in catalog or catalog[name]["archived_at"] is not None})
    if missing:
        raise ValueError(f"Required active catalog exercises missing: {missing}")
    existing = {row["name"]: row for row in training.templates(path, archived=True)}
    for label, names in DEFINITIONS.items():
        if label in existing:
            actual = [item["name"] for item in training.template_items(existing[label]["id"], path)]
            if actual != names:
                raise ValueError(f"Existing template {label!r} differs; no overwrite performed")
    # These historical catalog kinds were marked unknown because some source
    # load_type values were missing or mixed. New sets use the dominant
    # external-load interpretation; historical snapshots are not changed.
    for name in ("Leg Extension", "Triceps Rope Pushdown"):
        if catalog[name]["kind"] == "unknown":
            training.edit_exercise(catalog[name]["id"], name, "external", path)
    created = []
    for label, names in DEFINITIONS.items():
        if label not in existing:
            training.save_template(label, [catalog[name]["id"] for name in names], path)
            created.append(label)
    return created


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-copy", action="store_true")
    args = parser.parse_args()
    if args.test_copy:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "workout_log.duckdb"
            shutil.copy2(training.DB, copy)
            created = seed(copy)
            with training.connect(copy) as con:
                historical = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
            print({"mode": "test-copy", "created": created, "historical_rows": historical})
    else:
        with training.connect() as con:
            source_count = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
            mapped_count = con.execute("SELECT COUNT(*) FROM legacy_row_map").fetchone()[0]
        if source_count != mapped_count:
            raise RuntimeError("Historical source and provenance mapping differ; seeding stopped")
        backup = training.backup(
            training.DB,
            training.DB.with_name(training.DB.stem + ".before_core_templates.duckdb"),
        )
        created = seed()
        with training.connect() as con:
            historical = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        print({"mode": "live", "backup": str(backup),
               "created": created, "historical_rows": historical})


if __name__ == "__main__":
    main()
