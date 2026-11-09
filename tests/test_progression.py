import unittest
from types import SimpleNamespace
from unittest.mock import patch
from src import explanations, progression


class ProgressionTest(unittest.TestCase):
    def test_chronological_one_step_baseline(self):
        series = [{"date": i, "session_id": str(i), "e1rm": float(i)}
                  for i in range(1, 21)]
        result = progression.evaluate_last_value(series)
        self.assertEqual(result["train_n"], 12)
        self.assertEqual(result["validation_n"], 4)
        self.assertEqual(result["test_n"], 4)
        self.assertEqual(result["mae"], 1)
        self.assertEqual(result["validation_mae"], 1)

    def test_sparse_series_has_no_claimed_mae(self):
        series = [{"e1rm": 50.0}] * 5
        self.assertIsNone(progression.evaluate_last_value(series)["mae"])
        self.assertEqual(progression.decide(series)[0], "beibehalten")

    def test_trend_rule(self):
        increasing = [{"e1rm": value} for value in [100,100,100,105,106,107]]
        self.assertEqual(progression.decide(increasing)[0], "erhöhen")
        decreasing = [{"e1rm": value} for value in [100,100,100,90,91,92]]
        self.assertEqual(progression.decide(decreasing)[0], "reduzieren/überprüfen")

    def test_llm_cannot_change_recommendation(self):
        analysis = {"exercise": "Bench", "forecast_e1rm": 80.0,
                    "recommendation": "beibehalten", "reason": "Stabil.",
                    "evaluation": {"status": "evaluated", "n": 20, "mae": 2, "test_n": 4}}
        bad = '{"summary":"Stabil.","trend":"Stabil.","rationale":"Unverändert.","limits":"Unsicher.","recommendation":"erhöhen"}'
        response = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=bad))])
        with patch.object(explanations.client.chat.completions, "create", return_value=response):
            result = explanations.explain(analysis)
        self.assertEqual(result["source"], "deterministic")
        self.assertEqual(result["recommendation"], "beibehalten")

    def test_api_failure_uses_deterministic_baseline(self):
        analysis = {"exercise": "Bench", "forecast_e1rm": None,
                    "recommendation": "beibehalten", "reason": "Keine Daten.",
                    "evaluation": {"status": "insufficient", "n": 0}}
        with patch.object(explanations.client.chat.completions, "create",
                          side_effect=RuntimeError("offline")):
            result = explanations.explain(analysis)
        self.assertEqual(result["source"], "deterministic")
        self.assertIn("keine vergleichbaren", result["summary"])

    def test_llm_format_and_numeric_claim_guard(self):
        analysis = {"exercise": "Bench", "forecast_e1rm": 80.0,
                    "recommendation": "beibehalten", "reason": "Stabil.",
                    "evaluation": {"status": "evaluated", "n": 20, "mae": 2, "test_n": 4}}
        invalid = '{"summary":"Der Wert ist 999 kg.","trend":"Stabil.",' + (
            '"rationale":"Unverändert.","limits":"Unsicher.","recommendation":"beibehalten"}')
        response = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=invalid))])
        with patch.object(explanations.client.chat.completions, "create", return_value=response):
            self.assertEqual(explanations.explain(analysis)["source"], "deterministic")
        valid = ('{"summary":"Die Leistung ist stabil.","trend":"Kein klarer Anstieg.",'
                 '"rationale":"Die letzte Beobachtung dient als Basis.",'
                 '"limits":"Der Verlauf ist unsicher.","recommendation":"beibehalten"}')
        response.choices[0].message.content = valid
        with patch.object(explanations.client.chat.completions, "create", return_value=response):
            explanation = explanations.explain(analysis)
        self.assertEqual(explanation["source"], "llm")
        self.assertEqual(explanation["recommendation"], analysis["recommendation"])
        self.assertEqual(explanation["rationale"], explanations.deterministic(analysis)["rationale"])
        response.choices[0].message.content = valid.replace(
            "Die Leistung ist stabil.", "Du solltest das Gewicht erhöhen.")
        with patch.object(explanations.client.chat.completions, "create", return_value=response):
            self.assertEqual(explanations.explain(analysis)["source"], "deterministic")


if __name__ == "__main__":
    unittest.main()
