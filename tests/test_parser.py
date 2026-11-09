import unittest
from types import SimpleNamespace
from unittest.mock import patch
from src import parser


class ParserRegressionTest(unittest.TestCase):
    def test_structured_note_preserves_contract(self):
        payload = ('{"sets":[{"date":"2026-06-16","workout":"upper 1",'
                   '"exercise":"Bench","exercise_standardized":"Bench","set_number":1,'
                   '"target_sets":1,"reps":8,"duration_sec":null,"weight_kg":60,'
                   '"load_type":"external","is_unilateral_note":null,"notes":null}]}')
        response = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=payload))])
        with patch.object(parser.client.chat.completions, "create", return_value=response) as call:
            frame = parser.parse_workout_note("16.6.26 upper 1 Bench 1x8x60kg")
        self.assertEqual(list(frame.columns), parser.EXPECTED_COLUMNS)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["weight_kg"], 60)
        self.assertEqual(frame.iloc[0]["reps"], 8)
        self.assertEqual(call.call_args.kwargs["response_format"]["type"], "json_schema")


if __name__ == "__main__":
    unittest.main()
