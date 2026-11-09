import tempfile
import unittest
import hashlib
import shutil
import json
from collections import Counter
from pathlib import Path
import duckdb
import pandas as pd
from unittest.mock import patch
from src import db as legacy_db
from src import training as t


class TrainingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.duckdb"
        t.initialize(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_catalog_template_and_archive(self):
        ex = t.create_exercise("Bench", "external", self.db)
        t.edit_exercise(ex, "Bench Press", "external", self.db)
        template = t.save_template("Upper", [ex], self.db)
        self.assertEqual(t.template_items(template, self.db)[0]["name"], "Bench Press")
        t.save_template("Upper 1", [ex], self.db, template)
        self.assertEqual(t.templates(self.db)[0]["name"], "Upper 1")
        t.archive_exercise(ex, self.db)
        self.assertEqual(t.exercises(self.db), [])
        self.assertEqual(len(t.template_items(template, self.db)), 1)
        with self.assertRaises(ValueError):
            t.start_session(template, self.db)
        t.archive_template(template, self.db)
        self.assertEqual(t.templates(self.db), [])

    def test_tracking_restore_and_history(self):
        ex = t.create_exercise("Bench", "external", self.db)
        template = t.save_template("Upper", [ex], self.db)
        sid = t.start_session(template, self.db)
        active = t.sessions(self.db, "active")
        self.assertEqual([s["id"] for s in active], [sid])
        se = t.session_detail(sid, self.db)["exercises"][0]["id"]
        set_id = t.save_set(se, reps=8, weight_kg=60, path=self.db)
        self.assertEqual(t.session_detail(sid, self.db)["exercises"][0]["sets"][0]["reps"], 8)
        t.finish_session(sid, self.db)
        self.assertEqual(t.session_detail(sid, self.db)["status"], "completed")
        t.save_set(se, set_id=set_id, reps=9, weight_kg=60, path=self.db)
        self.assertEqual(t.session_detail(sid, self.db)["exercises"][0]["sets"][0]["reps"], 9)
        t.remove_set(set_id, self.db)
        self.assertEqual(t.session_detail(sid, self.db)["exercises"][0]["sets"], [])
        with t.connect(self.db) as con:
            self.assertGreater(con.execute("SELECT COUNT(*) FROM history_edits").fetchone()[0], 0)

    def test_set_type_validation(self):
        self.assertRaises(ValueError, t.validate_set, "external", 0, 50, None, None, None, None)
        self.assertRaises(ValueError, t.validate_set, "bodyweight", 5, None, None, None, None, None)
        t.validate_set("bodyweight", 5, None, 80, None, 60, 7)
        t.validate_set("duration", None, None, None, 45, None, None)

    def test_import_keeps_legacy_and_new_history_in_sync(self):
        with duckdb.connect(str(self.db)) as con:
            con.execute("""CREATE TABLE workout_sets (
                date TIMESTAMP, workout VARCHAR, exercise VARCHAR,
                exercise_standardized VARCHAR, set_number INTEGER, target_sets INTEGER,
                reps INTEGER, duration_sec INTEGER, weight_kg DOUBLE, load_type VARCHAR,
                is_unilateral_note VARCHAR, notes VARCHAR)""")
        frame = pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "workout": "Upper",
            "exercise": "Bench", "exercise_standardized": "Bench", "set_number": 1,
            "target_sets": 1, "reps": 8, "duration_sec": None, "weight_kg": 60.0,
            "load_type": "external", "is_unilateral_note": None, "notes": None}])
        receipt = t.import_workout_sets(frame, self.db)
        self.assertEqual(receipt["row_count"], 1)
        self.assertEqual(len(t.imported_sets(receipt["set_ids"], self.db)), 1)
        with t.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM legacy_row_map").fetchone()[0], 1)
            source = t.rows(con, "SELECT * FROM workout_sets")[0]
            mapped = json.loads(con.execute("SELECT raw_json FROM legacy_row_map").fetchone()[0])
            self.assertEqual(json.dumps(source, default=str, sort_keys=True),
                             json.dumps(mapped, sort_keys=True))
        self.assertEqual(len(t.sessions(self.db)), 1)
        sid = t.sessions(self.db)[0]["id"]
        ex = t.session_detail(sid, self.db)["exercises"][0]
        old_set = ex["sets"][0]
        t.save_set(ex["id"], set_id=old_set["id"], reps=9, weight_kg=60, path=self.db)
        with patch.object(legacy_db, "DB_PATH", self.db):
            dashboard = legacy_db.load_workout_sets()
        self.assertEqual(int(dashboard.iloc[0]["reps"]), 9)
        with t.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT reps FROM workout_sets").fetchone()[0], 8)

    def test_legacy_remains_unchanged(self):
        with duckdb.connect(str(self.db)) as con:
            con.execute("CREATE TABLE workout_sets (date DATE, workout VARCHAR, exercise VARCHAR)")
            con.execute("INSERT INTO workout_sets VALUES (DATE '2026-01-01','Leg 1','Squat')")
        before = self.db.read_bytes()
        backup = t.backup(self.db, Path(self.tmp.name) / "backup.duckdb")
        self.assertEqual(before, backup.read_bytes())
        t.initialize(self.db)
        with t.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0], 1)

    def test_real_database_schema_on_copy(self):
        source = Path("data/workout_log.duckdb")
        if not source.exists():
            self.skipTest("Historical database unavailable")
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        copy = Path(self.tmp.name) / "historical_copy.duckdb"
        shutil.copy2(source, copy)
        with duckdb.connect(str(copy), read_only=True) as con:
            before = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        t.initialize(copy)
        migrated = t.migrate_legacy(copy)
        self.assertEqual(migrated["rows"], before)
        self.assertEqual(t.migrate_legacy(copy), migrated)
        with duckdb.connect(str(copy), read_only=True) as con:
            after = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            source_rows = t.rows(con, "SELECT * FROM workout_sets")
            mapped = [json.loads(r[0]) for r in con.execute("SELECT raw_json FROM legacy_row_map").fetchall()]
            self.assertEqual(Counter(json.dumps(r, default=str, sort_keys=True) for r in source_rows),
                             Counter(json.dumps(r, sort_keys=True) for r in mapped))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM session_sets WHERE legacy_row_number IS NOT NULL").fetchone()[0], before)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM sessions WHERE source='legacy' AND started_at IS NULL AND duration_sec IS NULL").fetchone()[0], migrated["sessions"])
        self.assertEqual(before, after)
        self.assertTrue({"exercises", "templates", "sessions", "session_sets"} <= tables)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)


if __name__ == "__main__":
    unittest.main()
