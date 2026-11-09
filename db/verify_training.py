"""Read-only comparison of live historical source, backup and provenance rows."""
import json
from collections import Counter
from src import training


def canonical(rows):
    return Counter(json.dumps(row, sort_keys=True, default=str) for row in rows)


def main():
    backup = training.DB.with_name(training.DB.stem + ".pre_gymcoach_backup.duckdb")
    before_templates = training.DB.with_name(
        training.DB.stem + ".before_core_templates.duckdb"
    )
    with training.connect(backup) as con:
        original = training.rows(con, "SELECT * FROM workout_sets")
    with training.connect(before_templates) as con:
        before_seed = training.rows(con, "SELECT * FROM workout_sets")
    with training.connect(training.DB) as con:
        current = training.rows(con, "SELECT * FROM workout_sets")
        mapped = [json.loads(item[0]) for item in con.execute(
            "SELECT raw_json FROM legacy_row_map").fetchall()]
        normalized = con.execute(
            "SELECT COUNT(*) FROM session_sets WHERE legacy_row_number IS NOT NULL").fetchone()[0]
        provisional = con.execute(
            "SELECT COUNT(*) FROM sessions WHERE source='legacy'").fetchone()[0]
        template_names = [r[0] for r in con.execute(
            "SELECT name FROM templates ORDER BY name").fetchall()]
    if canonical(original) - canonical(current):
        raise RuntimeError("Original historical rows missing from live source")
    if canonical(before_seed) != canonical(current):
        raise RuntimeError("Template seeding changed source rows")
    if canonical(current) != canonical(mapped):
        raise RuntimeError("Provenance mapping differs from current source")
    if len(current) != normalized:
        raise RuntimeError("Normalized historical row count differs")
    print({"backup_rows": len(original), "live_source_rows": len(current),
           "provenance_rows": len(mapped), "normalized_rows": normalized,
           "provisional_sessions": provisional,
           "templates": template_names, "status": "verified"})


if __name__ == "__main__":
    main()
