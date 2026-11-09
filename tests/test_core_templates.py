import shutil
import tempfile
import unittest
from pathlib import Path
from db.seed_core_templates import DEFINITIONS, seed
from src import training


class CoreTemplatesTest(unittest.TestCase):
    def test_seed_on_copy_is_complete_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "workout_log.duckdb"
            shutil.copy2(training.DB, copy)
            with training.connect(copy, True) as con:
                before = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
                con.execute("DELETE FROM template_exercises")
                con.execute("DELETE FROM templates")
            self.assertEqual(set(seed(copy)), set(DEFINITIONS))
            self.assertEqual(seed(copy), [])
            templates = {row["name"]: row["id"] for row in training.templates(copy)}
            self.assertEqual(set(templates), set(DEFINITIONS))
            for name, expected in DEFINITIONS.items():
                actual = [row["name"] for row in training.template_items(templates[name], copy)]
                self.assertEqual(actual, expected)
            with training.connect(copy) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0], before)


if __name__ == "__main__":
    unittest.main()
