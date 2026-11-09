import streamlit as st
import pandas as pd
import plotly.express as px

from src.db import init_db, insert_workout_sets, load_workout_sets, delete_all_data
from src.parser import parse_workout_note
from src.exercise_normalizer import normalize_exercise_dataframe
from src.training_ui import render as render_training
from src.progress_ui import render as render_progress
from src.training import import_workout_sets, imported_sets
from src.metrics import (
    add_metrics,
    dashboard_summary,
    weekly_volume,
    exercise_volume,
    exercise_e1rm,
    exercise_summary,
    detect_prs,
)

st.set_page_config(page_title="Workout AI Log", layout="wide")

EXPECTED_COLUMNS = [
    "date",
    "workout",
    "exercise",
    "exercise_standardized",
    "set_number",
    "target_sets",
    "reps",
    "duration_sec",
    "weight_kg",
    "load_type",
    "is_unilateral_note",
    "notes",
]

init_db()

st.title("Workout AI Log")

tab_import, tab_data, tab_dashboard, tab_training, tab_progress = st.tabs(
    ["Import workout", "Data", "Dashboard", "Trainingsverwaltung", "KI-Fortschritt"]
)

with tab_import:
    st.subheader("Parse messy workout note with AI")

    raw_note = st.text_area(
        "Paste Samsung Notes workout log",
        height=250,
        key="raw_note_input",
    )

    if st.button("Parse note with AI"):
        if not raw_note.strip():
            st.warning("Paste a workout note first.")
        else:
            with st.spinner("Parsing workout note..."):
                parsed_df = parse_workout_note(raw_note)
                parsed_df = normalize_exercise_dataframe(parsed_df)
            
            st.session_state["preview_df"] = parsed_df
            st.session_state.pop("last_import_receipt", None)
            st.success(f"Parsed {len(parsed_df)} sets.")
            st.dataframe(parsed_df, width="stretch")

    st.divider()
    st.subheader("Paste your workout table")

    raw_table = st.text_area(
        "Paste tab-separated data from Excel, including the header row",
        height=300,
    )

    if st.button("Preview import"):
        if not raw_table.strip():
            st.warning("Paste data first.")
        else:
            from io import StringIO

            df = pd.read_csv(StringIO(raw_table), sep="\t")

            missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
            extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]

            if missing_cols:
                st.error(f"Missing columns: {missing_cols}")
            else:
                df = df[EXPECTED_COLUMNS]
                df = normalize_exercise_dataframe(df)

                df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y").dt.date

                numeric_cols = [
                    "set_number",
                    "target_sets",
                    "reps",
                    "duration_sec",
                    "weight_kg",
                ]

                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    df = normalize_exercise_dataframe(df)
                st.session_state["preview_df"] = df
                st.session_state.pop("last_import_receipt", None)

                if extra_cols:
                    st.warning(f"Ignoring extra columns: {extra_cols}")

                st.success(f"Parsed {len(df)} rows.")
                st.dataframe(df, width="stretch")

    if "last_import_receipt" in st.session_state:
        receipt = st.session_state["last_import_receipt"]
        saved_rows = imported_sets(receipt["set_ids"])
        if len(saved_rows) == receipt["row_count"]:
            st.success(
                f"{receipt['row_count']} Sätze in DuckDB gespeichert und erneut gelesen. "
                f"{len(receipt['session_ids'])} Trainingseinheit(en) in der Historie."
            )
            st.subheader("Gespeicherte Sätze")
            st.dataframe(
                pd.DataFrame(saved_rows).drop(columns=["set_id"]),
                width="stretch",
            )
        else:
            st.error("Die gespeicherten Sätze konnten nicht vollständig bestätigt werden.")

    if "preview_df" in st.session_state:
        st.subheader("Editable preview")
        st.info("Diese Daten sind noch nicht gespeichert. Prüfe sie und klicke dann auf „Save to database“.")
        edited_df = st.data_editor(
            st.session_state["preview_df"],
            width="stretch",
            num_rows="dynamic",
        )

        if st.button("Save to database"):
            try:
                st.session_state["last_import_receipt"] = import_workout_sets(edited_df)
            except Exception as exc:
                st.error(f"Speichern fehlgeschlagen: {exc}")
            else:
                del st.session_state["preview_df"]
                st.rerun()

with tab_data:
    st.subheader("Stored workout sets")

    df = load_workout_sets()

    if df.empty:
        st.info("No data saved yet.")
    else:
        st.dataframe(df, width="stretch")

with tab_dashboard:
    st.subheader("Workout dashboard")

    df = load_workout_sets()
    df = add_metrics(df)

    if df.empty:
        st.info("No data available yet.")
    else:
        summary = dashboard_summary(df)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Volume in latest logged week", f"{summary['weekly_volume']:,.0f} kg")
        col2.metric("Training days in latest logged week", summary["training_days_this_week"])
        col3.metric("PRs in latest logged month", summary["prs_this_month"])
        col4.metric("Best e1RM", f"{summary['best_e1rm']:.1f} kg")

        st.divider()

        view = st.radio(
            "Analytics view",
            ["Overview", "Workout-day analytics", "Exercise analytics", "PRs", "Advanced"],
            horizontal=True,
        )

        if view == "Overview":
            weekly = weekly_volume(df)

            fig = px.line(
                weekly,
                x="week",
                y="volume_kg",
                markers=True,
                title="Weekly volume trend",
            )
            st.plotly_chart(fig, width="stretch")

            e1rm = exercise_e1rm(df)

            if not e1rm.empty:
                selected_exercises = st.multiselect(
                    "Select exercises for strength trend",
                    sorted(e1rm["exercise_standardized"].unique()),
                    default=sorted(e1rm["exercise_standardized"].unique())[:3],
                )

                filtered = e1rm[e1rm["exercise_standardized"].isin(selected_exercises)]

                fig2 = px.line(
                    filtered,
                    x="date",
                    y="e1rm",
                    color="exercise_standardized",
                    markers=True,
                    title="Estimated 1RM trend",
                )
                st.plotly_chart(fig2, width="stretch")
        
        elif view == "Workout-day analytics":
            workouts = sorted(df["workout"].dropna().unique())
            selected_workout = st.selectbox("Select workout day/type", workouts)

            workout_df = df[df["workout"] == selected_workout].copy()

            workout_by_date = (
                workout_df.groupby("date", as_index=False)
                .agg(
                    volume_kg=("volume_kg", "sum"),
                    sets=("set_number", "count"),
                    exercises=("exercise_standardized", "nunique"),
                    best_e1rm=("e1rm", "max"),
                )
                .sort_values("date")
            )

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Sessions", workout_by_date.shape[0])
            col2.metric("Avg volume", f"{workout_by_date['volume_kg'].mean():,.0f} kg")
            col3.metric("Avg sets", f"{workout_by_date['sets'].mean():.1f}")
            col4.metric("Best session e1RM", f"{workout_by_date['best_e1rm'].max():.1f} kg")

            fig = px.line(
                workout_by_date,
                x="date",
                y="volume_kg",
                markers=True,
                title=f"{selected_workout} volume progression",
            )
            st.plotly_chart(fig, width="stretch")

            fig2 = px.line(
                workout_by_date,
                x="date",
                y="sets",
                markers=True,
                title=f"{selected_workout} set count progression",
            )
            st.plotly_chart(fig2, width="stretch")

            st.subheader("Exercise progression within this workout")

            exercise_options = sorted(workout_df["exercise_standardized"].dropna().unique())
            selected_exercise = st.selectbox(
                "Select exercise inside workout",
                exercise_options,
                key="workout_day_exercise_select",
            )

            exercise_df = workout_df[
                workout_df["exercise_standardized"] == selected_exercise
            ]

            exercise_by_date = (
                exercise_df.groupby("date", as_index=False)
                .agg(
                    volume_kg=("volume_kg", "sum"),
                    best_e1rm=("e1rm", "max"),
                    max_weight=("weight_kg", "max"),
                    total_reps=("reps", "sum"),
                )
                .sort_values("date")
            )

            fig3 = px.line(
                exercise_by_date,
                x="date",
                y="best_e1rm",
                markers=True,
                title=f"{selected_exercise} e1RM inside {selected_workout}",
            )
            st.plotly_chart(fig3, width="stretch")

            fig4 = px.bar(
                exercise_by_date,
                x="date",
                y="volume_kg",
                title=f"{selected_exercise} volume inside {selected_workout}",
            )
            st.plotly_chart(fig4, width="stretch")

            st.dataframe(
                exercise_df[
                    [
                        "date",
                        "exercise",
                        "exercise_standardized",
                        "set_number",
                        "reps",
                        "weight_kg",
                        "volume_kg",
                        "e1rm",
                        "is_unilateral_note",
                        "notes",
                    ]
                ].sort_values(["date", "set_number"]),
                width="stretch",
            )

        elif view == "Exercise analytics":
            exercises = sorted(df["exercise_standardized"].dropna().unique())

            selected_exercise = st.selectbox("Select exercise", exercises)

            summary_ex = exercise_summary(df, selected_exercise)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current e1RM", f"{summary_ex['current_e1rm']:.1f} kg")
            col2.metric("Best e1RM", f"{summary_ex['best_e1rm']:.1f} kg")
            col3.metric("Best weight", f"{summary_ex['best_weight']:.1f} kg")
            col4.metric("Best reps", f"{summary_ex['best_reps']:.0f}")

            ex_e1rm = exercise_e1rm(df)
            ex_e1rm = ex_e1rm[ex_e1rm["exercise_standardized"] == selected_exercise]

            fig = px.line(
                ex_e1rm,
                x="date",
                y="e1rm",
                markers=True,
                title=f"{selected_exercise} e1RM trend",
            )
            st.plotly_chart(fig, width="stretch")

            ex_volume = exercise_volume(df)
            ex_volume = ex_volume[
                ex_volume["exercise_standardized"] == selected_exercise
            ]

            fig2 = px.bar(
                ex_volume,
                x="date",
                y="volume_kg",
                title=f"{selected_exercise} volume trend",
            )
            st.plotly_chart(fig2, width="stretch")

            st.subheader("Set history")
            st.dataframe(
                df[df["exercise_standardized"] == selected_exercise][
                    [
                        "date",
                        "workout",
                        "set_number",
                        "reps",
                        "weight_kg",
                        "volume_kg",
                        "e1rm",
                        "notes",
                    ]
                ],
                width="stretch",
            )

        elif view == "PRs":
            prs = detect_prs(df)

            if prs.empty:
                st.info("No PRs detected yet.")
            else:
                st.dataframe(prs.sort_values("date", ascending=False), width="stretch")

        elif view == "Advanced":
            st.subheader("Rep range distribution")

            rep_dist = (
                df.groupby("rep_range", observed=True)
                .size()
                .reset_index(name="sets")
            )

            fig = px.bar(
                rep_dist,
                x="rep_range",
                y="sets",
                title="Rep range distribution",
            )
            st.plotly_chart(fig, width="stretch")

            st.subheader("Exercise frequency")

            freq = (
                df.groupby("exercise_standardized")["date"]
                .nunique()
                .reset_index(name="sessions")
                .sort_values("sessions", ascending=False)
            )

            fig2 = px.bar(
                freq,
                x="exercise_standardized",
                y="sessions",
                title="Exercise frequency",
            )
            st.plotly_chart(fig2, width="stretch")

with tab_training:
    render_training()

with tab_progress:
    render_progress()
