"""Streamlit views for the normalized training data."""
from datetime import datetime, timezone
import pandas as pd
import plotly.express as px
import streamlit as st
from src import training as t


def attempt(action, success):
    try:
        result = action()
        st.success(success)
        st.rerun()
        return result
    except Exception as exc:
        st.error(str(exc))


@st.fragment(run_every="1s")
def timer(started_at):
    if started_at:
        elapsed = max(0, int((datetime.now(timezone.utc).replace(tzinfo=None)-started_at).total_seconds()))
        hours, rest = divmod(elapsed, 3600)
        minutes, seconds = divmod(rest, 60)
        st.metric("Trainingsdauer", f"{hours:02}:{minutes:02}:{seconds:02}")


def overview():
    sessions = t.sessions()
    completed = [s for s in sessions if s["status"] == "completed"]
    manual = [s for s in completed if s["source"] == "manual"]
    cols = st.columns(3)
    cols[0].metric("Einheiten", len(completed))
    cols[1].metric("Davon neu erfasst", len(manual))
    cols[2].metric("Laufende Einheiten", len([s for s in sessions if s["status"] == "active"]))
    st.subheader("Letzte Einheiten")
    st.dataframe(pd.DataFrame([{"Datum": s["session_date"], "Workout": s["name"],
                               "Herkunft": s["source"], "Status": s["status"]}
                              for s in sessions[:10]]), width="stretch")
    st.caption("Legacy-Einheiten sind vorläufig nach Datum und Workout-Text gruppiert.")
    with t.connect() as con:
        volume = t.rows(con, """SELECT s.session_date AS date,
            SUM(CASE WHEN ss.weight_kg>0 AND ss.reps>0
                THEN ss.weight_kg*ss.reps ELSE 0 END) AS volume_kg
            FROM sessions s JOIN session_exercises se ON se.session_id=s.id
            JOIN session_sets ss ON ss.session_exercise_id=se.id
            WHERE s.status='completed' GROUP BY s.session_date ORDER BY s.session_date""")
    if volume:
        st.plotly_chart(px.line(pd.DataFrame(volume), x="date", y="volume_kg",
                                title="Trainingsvolumen nach Trainingstag"),
                        width="stretch")
    if st.button("Nächstes Workout starten"):
        st.session_state["training_view"] = "Aktives Training"
        st.rerun()


def exercise_view():
    st.subheader("Übungen")
    with st.form("new_exercise"):
        name = st.text_input("Neue Übung")
        kind = st.selectbox("Typ", t.KINDS)
        if st.form_submit_button("Übung erstellen"):
            attempt(lambda: t.create_exercise(name, kind), "Übung erstellt")
    current = t.exercises()
    query = st.text_input("Übungen suchen")
    current = [ex for ex in current if query.lower() in ex["name"].lower()]
    if not current:
        st.info("Keine Übungen gefunden.")
        return
    selected = st.selectbox("Übung bearbeiten", current,
                            format_func=lambda ex: f"{ex['name']} ({ex['kind']})")
    with st.form("edit_exercise"):
        new_name = st.text_input("Name", value=selected["name"])
        new_kind = st.selectbox("Übungstyp", t.KINDS,
                                index=t.KINDS.index(selected["kind"]) if selected["kind"] in t.KINDS else 0)
        if st.form_submit_button("Änderungen speichern"):
            attempt(lambda: t.edit_exercise(selected["id"], new_name, new_kind), "Übung geändert")
    if st.button("Übung archivieren"):
        attempt(lambda: t.archive_exercise(selected["id"]), "Übung archiviert; historische Daten bleiben erhalten")


def template_view():
    st.subheader("Workout-Vorlagen")
    all_templates = t.templates()
    options = [None] + all_templates
    selected = st.selectbox("Vorlage", options,
                            format_func=lambda x: "Neue Vorlage" if x is None else x["name"])
    key = "template_draft"
    selected_id = selected["id"] if selected else None
    if key not in st.session_state or st.session_state.get("template_selected") != selected_id:
        st.session_state["template_selected"] = selected_id
        st.session_state[key] = ([item["exercise_id"] for item in t.template_items(selected_id)]
                                 if selected_id else [])
    name = st.text_input("Vorlagenname", value=selected["name"] if selected else "",
                         key=f"template_name_{selected_id}")
    exs = t.exercises()
    by_id = {ex["id"]: ex for ex in exs}
    unused = [ex for ex in exs if ex["id"] not in st.session_state[key]]
    if unused:
        chosen = st.selectbox("Übung hinzufügen", unused, format_func=lambda ex: ex["name"])
        if st.button("Zur Vorlage hinzufügen"):
            st.session_state[key].append(chosen["id"])
            st.rerun()
    with st.expander("Neue Übung direkt anlegen"):
        with st.form("inline_template_exercise"):
            inline_name = st.text_input("Übungsname")
            inline_kind = st.selectbox("Typ der neuen Übung", t.KINDS)
            if st.form_submit_button("Übung anlegen und hinzufügen"):
                try:
                    eid = t.create_exercise(inline_name, inline_kind)
                    st.session_state[key].append(eid)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    for index, eid in enumerate(list(st.session_state[key])):
        cols = st.columns([5,1,1,1])
        cols[0].write(by_id.get(eid, {"name": eid})["name"])
        if cols[1].button("↑", key=f"up_{index}") and index:
            draft = st.session_state[key]
            draft[index-1], draft[index] = draft[index], draft[index-1]
            st.rerun()
        if cols[2].button("↓", key=f"down_{index}") and index < len(st.session_state[key])-1:
            draft = st.session_state[key]
            draft[index+1], draft[index] = draft[index], draft[index+1]
            st.rerun()
        if cols[3].button("×", key=f"remove_{index}"):
            st.session_state[key].pop(index)
            st.rerun()
    if st.button("Vorlage speichern"):
        attempt(lambda: t.save_template(name, st.session_state[key], template_id=selected_id),
                "Vorlage gespeichert")
    if selected and st.button("Vorlage archivieren"):
        attempt(lambda: t.archive_template(selected_id), "Vorlage archiviert")


def set_form(ex, old=None):
    kind = ex["kind"]
    old = old or {}
    with st.form(f"set_form_{ex['id']}_{old.get('id','new')}"):
        st.caption(f"Übungstyp: {kind}. Nicht benötigte Werte bei 0 belassen.")
        reps_value = st.number_input("Wiederholungen", min_value=0,
                                     value=int(old.get("reps") or 0))
        weight_value = st.number_input("Externes Gewicht (kg)", min_value=0.0,
                                       value=float(old.get("weight_kg") or 0))
        bodyweight_value = st.number_input("Körpergewicht (kg)", min_value=0.0,
                                           value=float(old.get("bodyweight_kg") or 0))
        duration_value = st.number_input("Dauer (Sekunden)", min_value=0,
                                         value=int(old.get("duration_sec") or 0))
        reps = reps_value or None
        weight = weight_value or None
        bodyweight = bodyweight_value or None
        duration = duration_value or None
        rest = st.number_input("Satzpause (Sekunden, optional)", min_value=0,
                               value=int(old.get("rest_sec") or 0))
        rpe = st.number_input("RPE (0 = nicht erfasst)", min_value=0.0, max_value=10.0,
                              value=float(old.get("rpe") or 0), step=0.5)
        notes = st.text_input("Notiz", value=old.get("notes") or "")
        if st.form_submit_button("Satz speichern"):
            attempt(lambda: t.save_set(ex["id"], set_id=old.get("id"), reps=reps,
                                       weight_kg=weight, bodyweight_kg=bodyweight,
                                       duration_sec=duration, rest_sec=rest or None,
                                       rpe=rpe or None, notes=notes),
                    "Satz gespeichert")
    if old.get("id") and st.button("Satz entfernen", key=f"delete_{old['id']}"):
        attempt(lambda: t.remove_set(old["id"]), "Satz entfernt und Änderung protokolliert")


def session_editor(session_id, live=False):
    session = t.session_detail(session_id)
    st.subheader(session["name"])
    st.write(f"Datum: {session['session_date']} · Status: {session['status']}")
    if session["source"] == "legacy":
        st.warning("Vorläufige historische Zuordnung nach Datum und Workout-Text. Beginn und Dauer sind unbekannt.")
    if live:
        timer(session["started_at"])
    for ex in session["exercises"]:
        with st.expander(f"{ex['position']}. {ex['name']} · {len(ex['sets'])} Sätze", expanded=live):
            for old in ex["sets"]:
                st.write(f"Satz {old['set_number']}: {old['reps'] or '–'} Wdh. · "
                         f"{old['weight_kg'] if old['weight_kg'] is not None else '–'} kg · "
                         f"{old['duration_sec'] or '–'} s")
                set_form(ex, old)
            st.write("Weiteren Satz erfassen")
            set_form(ex)
            if st.button("Übung aus Einheit entfernen", key=f"remove_session_ex_{ex['id']}"):
                attempt(lambda: t.remove_session_exercise(ex["id"]), "Übung entfernt")
    available = t.exercises()
    if available:
        extra = st.selectbox("Übung nachträglich ergänzen", available,
                             format_func=lambda item: item["name"], key=f"extra_{session_id}")
        if st.button("Übung ergänzen", key=f"add_ex_{session_id}"):
            attempt(lambda: t.add_session_exercise(session_id, extra["id"]), "Übung ergänzt")
    if live and st.button("Training abschließen"):
        attempt(lambda: t.finish_session(session_id), "Training abgeschlossen")


def active_view():
    st.subheader("Aktives Training")
    active = t.sessions(status="active")
    if active:
        selected = st.selectbox("Laufende Einheit fortsetzen", active,
                                format_func=lambda item: f"{item['name']} · {item['session_date']}")
        session_editor(selected["id"], live=True)
    else:
        templates = t.templates()
        if not templates:
            st.info("Zuerst eine Workout-Vorlage erstellen.")
            return
        selected = st.selectbox("Vorlage auswählen", templates,
                                format_func=lambda item: item["name"])
        if st.button("Training starten"):
            attempt(lambda: t.start_session(selected["id"]), "Training gestartet")


def history_view():
    st.subheader("Trainingshistorie")
    sessions = t.sessions(status="completed")
    if not sessions:
        st.info("Noch keine abgeschlossenen Einheiten.")
        return
    query = st.text_input("Workout suchen")
    sessions = [item for item in sessions if query.lower() in item["name"].lower()]
    selected = st.selectbox("Einheit öffnen", sessions,
                            format_func=lambda item: f"{item['session_date']} · {item['name']}"
                                + (" · vorläufig zugeordnet" if item["source"] == "legacy" else ""))
    session_editor(selected["id"])


def render():
    views = {
        "Übersicht": overview,
        "Übungen": exercise_view,
        "Vorlagen": template_view,
        "Aktives Training": active_view,
        "Historie": history_view,
    }
    selected = st.radio("Trainingsverwaltung", list(views), horizontal=True,
                        key="training_view")
    views[selected]()
