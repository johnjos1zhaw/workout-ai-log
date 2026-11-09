"""Bounded LLM explanation of a fixed analytical recommendation."""
import json
import logging
import re
from src.parser import client

FIELDS = ("summary", "trend", "rationale", "limits", "recommendation")
ACTION_WORDS = re.compile(r"\b(erhöh\w*|reduzier\w*|senk\w*|steiger\w*|beibehalt\w*)\b", re.I)


def deterministic(analysis):
    evaluation = analysis["evaluation"]
    n = evaluation.get("n", 0)
    if analysis["forecast_e1rm"] is None:
        summary = "Für diese Übung sind noch keine vergleichbaren Kraftsätze vorhanden."
    else:
        summary = (f"Zuletzt wurde ein geschätztes 1RM von {analysis['forecast_e1rm']:.1f} kg "
                   f"beobachtet. Die einfache Prognose übernimmt diesen Wert für die nächste Einheit.")
    uncertainty = ("Der historische Testfehler dieser Baseline beträgt "
                   f"{evaluation['mae']:.2f} kg MAE bei {evaluation['test_n']} Testeinheiten. "
                   "Dies ist kein individuelles Prognoseintervall."
                   if evaluation.get("mae") is not None else
                   f"Mit {n} vergleichbaren Einheiten ist kein belastbarer Testfehler verfügbar.")
    return {"summary": summary, "trend": analysis["reason"],
            "rationale": "Die Entscheidung folgt ausschließlich der dokumentierten Trendregel.",
            "limits": uncertainty + " Die Empfehlung ist keine Bestimmung des optimalen Trainingsgewichts.",
            "recommendation": analysis["recommendation"], "source": "deterministic"}


def explain(analysis, use_llm=True):
    fallback = deterministic(analysis)
    if not use_llm:
        return fallback
    facts = {
        "exercise": analysis["exercise"],
        "recommendation": analysis["recommendation"],
        "trend_rule_result": analysis["reason"],
        "forecast_e1rm_kg": analysis["forecast_e1rm"],
        "historical_test_mae_kg": analysis["evaluation"].get("mae"),
        "test_sessions": analysis["evaluation"].get("test_n", 0),
        "observed_sessions": analysis["evaluation"].get("n", 0),
    }
    schema = {
        "type": "object",
        "properties": {key: {"type": "string"} for key in FIELDS},
        "required": list(FIELDS), "additionalProperties": False,
    }
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content":
                 "Erkläre die strukturierten Trainingsfakten auf Deutsch. Ändere die Empfehlung nicht. "
                 "Nenne keine neuen Zahlen, Diagnosen oder optimalen Trainingsgewichte. "
                 "Die Felder summary, trend, rationale und limits enthalten keine Ziffern. "
                 "Beschreibe Beobachtungen; formuliere keine eigene Handlungsaufforderung. "
                 "Kennzeichne Unsicherheit und fehlende Daten."},
                {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
            ],
            response_format={"type": "json_schema", "json_schema": {
                "name": "gymcoach_explanation", "strict": True, "schema": schema}},
        )
        output = json.loads(response.choices[0].message.content)
        if output["recommendation"] != analysis["recommendation"]:
            logging.warning("LLM explanation fallback: recommendation mismatch")
            return fallback
        if any(not output[key].strip() or len(output[key]) > 700 or
               re.search(r"\d", output[key]) for key in FIELDS[:-1]):
            logging.warning("LLM explanation fallback: unsupported format or numeric claim")
            return fallback
        if any(ACTION_WORDS.search(output[key]) for key in ("summary","trend")):
            logging.warning("LLM explanation fallback: action language in narrative")
            return fallback
        # The model never supplies the authoritative decision or its caveats.
        output["recommendation"] = analysis["recommendation"]
        output["rationale"] = fallback["rationale"]
        output["limits"] = fallback["limits"]
        output["source"] = "llm"
        return output
    except Exception as exc:
        logging.warning("LLM explanation fallback: %s", type(exc).__name__)
        return fallback
