import unittest
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest


class StreamlitSmokeTest(unittest.TestCase):
    def test_app_renders_all_tabs(self):
        app = AppTest.from_file("app.py", default_timeout=90).run()
        self.assertEqual(len(app.exception), 0, [str(e.message) for e in app.exception])
        self.assertEqual(len(app.tabs), 5)
        for view in ("Übungen", "Vorlagen", "Aktives Training", "Historie"):
            app.radio[1].set_value(view).run()
            self.assertEqual(len(app.exception), 0,
                             [str(e.message) for e in app.exception])

    def test_parser_result_is_visible_before_save(self):
        frame = pd.DataFrame([{
            "date": pd.Timestamp("2026-11-01").date(), "workout": "Upper",
            "exercise": "Bench", "exercise_standardized": "Bench",
            "set_number": 1, "target_sets": 1, "reps": 8,
            "duration_sec": None, "weight_kg": 60.0, "load_type": "external",
            "is_unilateral_note": None, "notes": None,
        }])
        with patch("src.parser.parse_workout_note", return_value=frame):
            app = AppTest.from_file("app.py", default_timeout=90).run()
            app.text_area[0].set_value("Mock note").run()
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0,
                         [str(e.message) for e in app.exception])
        self.assertEqual(len(app.session_state["preview_df"]), 1)
        self.assertTrue(any("Bench" in str(table.value) for table in app.dataframe))
        receipt = {"row_count": 1, "set_ids": ["saved-set"],
                   "session_ids": ["saved-session"], "legacy_total": 1777}
        saved = [{"date": "2026-11-01", "workout": "Upper", "exercise": "Bench",
                  "set_number": 1, "reps": 8, "weight_kg": 60.0,
                  "duration_sec": None, "notes": None, "set_id": "saved-set"}]
        with patch("src.training.import_workout_sets", return_value=receipt):
            with patch("src.training.imported_sets", return_value=saved):
                next(button for button in app.button if button.label == "Save to database").click().run()
        self.assertEqual(len(app.exception), 0,
                         [str(e.message) for e in app.exception])
        self.assertNotIn("preview_df", app.session_state)
        self.assertTrue(any("erneut gelesen" in str(message.value) for message in app.success))


if __name__ == "__main__":
    unittest.main()
