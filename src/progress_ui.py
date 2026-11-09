"""Performance, baseline forecast and constrained explanation view."""
import pandas as pd
import plotly.express as px
import streamlit as st
from src import explanations, progression, training


def render():
    st.subheader("Leistungsentwicklung und Empfehlung")
    with training.connect() as con:
        names = [row[0] for row in con.execute("""
            SELECT DISTINCT se.name FROM session_exercises se
            JOIN session_sets ss ON ss.session_exercise_id=se.id
            WHERE ss.reps>0 AND ss.weight_kg>0 ORDER BY se.name
        """).fetchall()]
    if not names:
        st.info("Noch keine vergleichbaren Kraftsätze vorhanden.")
        return
    selected = st.selectbox("Kraftübung", names)
    result = progression.analyze(selected)
    series = result.get("series", [])
    if series:
        chart = pd.DataFrame([{"Datum": row["date"], "e1RM (kg)": row["e1rm"]}
                              for row in series])
        st.plotly_chart(px.line(chart, x="Datum", y="e1RM (kg)", markers=True),
                        width="stretch")
    cols = st.columns(3)
    cols[0].metric("Beobachtete Einheiten", result["evaluation"]["n"])
    cols[1].metric("Nächster e1RM-Basiswert",
                   f"{result['forecast_e1rm']:.1f} kg" if result["forecast_e1rm"] else "–")
    mae = result["evaluation"].get("mae")
    cols[2].metric("Historischer Test-MAE", f"{mae:.2f} kg" if mae is not None else "–")
    st.caption("e1RM nach Epley, je Einheit der höchste gültige Kraftsatz. "
               "Die Prognose übernimmt den letzten beobachteten Wert. "
               "MAE ist ein historischer Durchschnittsfehler, kein individuelles Intervall.")
    st.markdown(f"**Entscheidungssignal: {result['recommendation']}**")
    st.write(result["reason"])
    st.info("Dies ist keine Vorgabe für ein optimales Gewicht. Du beurteilst die Empfehlung selbst und kannst abweichen.")
    fallback = explanations.deterministic(result)
    key = f"explanation_{selected}"
    signature = (result.get("latest_date"), result.get("forecast_e1rm"),
                 result["evaluation"].get("n"))
    if st.session_state.get(key, {}).get("signature") != signature:
        st.session_state[key] = {"signature": signature, "text": fallback,
                                 "llm_attempted": False}
    if st.button("KI-Erklärung anfordern"):
        st.session_state[key] = {"signature": signature,
                                 "text": explanations.explain(result),
                                 "llm_attempted": True}
    explanation = st.session_state[key]["text"]
    if (st.session_state[key]["llm_attempted"] and
            explanation["source"] != "llm"):
        st.info("Die KI-Erklärung ist derzeit nicht verfügbar. "
                "Die geprüften Kennzahlen und die feste Erklärung bleiben sichtbar.")
    st.subheader("Erklärung")
    for label, field in [("Zusammenfassung", "summary"), ("Trend", "trend"),
                         ("Begründung", "rationale"), ("Grenzen", "limits")]:
        st.markdown(f"**{label}:** {explanation[field]}")
    st.caption("Quelle: " + ("KI-Erklärung" if explanation["source"] == "llm"
                             else "deterministische Erklärung"))
