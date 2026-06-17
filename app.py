import streamlit as st
import pandas as pd
import plotly.express as px

from src.db import init_db, insert_workout_sets, load_workout_sets
from src.metrics import add_metrics
from src.parser import parse_workout_note

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

tab_import, tab_data, tab_dashboard = st.tabs(
    ["Import workout", "Data", "Dashboard"]
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

            st.session_state["preview_df"] = parsed_df
            st.success(f"Parsed {len(parsed_df)} sets.")
            st.dataframe(parsed_df, use_container_width=True)

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

                st.session_state["preview_df"] = df

                if extra_cols:
                    st.warning(f"Ignoring extra columns: {extra_cols}")

                st.success(f"Parsed {len(df)} rows.")
                st.dataframe(df, use_container_width=True)

    if "preview_df" in st.session_state:
        st.subheader("Editable preview")
        edited_df = st.data_editor(
            st.session_state["preview_df"],
            use_container_width=True,
            num_rows="dynamic",
        )

        if st.button("Save to database"):
            insert_workout_sets(edited_df)
            st.success("Workout data saved.")
            del st.session_state["preview_df"]

with tab_data:
    st.subheader("Stored workout sets")

    df = load_workout_sets()

    if df.empty:
        st.info("No data saved yet.")
    else:
        st.dataframe(df, use_container_width=True)

with tab_dashboard:
    st.subheader("Workout dashboard")

    df = load_workout_sets()
    df = add_metrics(df)

    if df.empty:
        st.info("No data available yet.")
    else:
        total_volume = df["volume_kg"].sum()
        total_sets = len(df)
        total_workouts = df[["date", "workout"]].drop_duplicates().shape[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Total volume kg", f"{total_volume:,.0f}")
        col2.metric("Total sets", f"{total_sets}")
        col3.metric("Workouts", f"{total_workouts}")

        volume_by_workout = (
            df.groupby(["date", "workout"], as_index=False)["volume_kg"]
            .sum()
            .sort_values("date")
        )

        fig = px.bar(
            volume_by_workout,
            x="date",
            y="volume_kg",
            color="workout",
            title="Total volume per workout",
        )

        st.plotly_chart(fig, use_container_width=True)

        volume_by_exercise = (
            df.groupby("exercise_standardized", as_index=False)["volume_kg"]
            .sum()
            .sort_values("volume_kg", ascending=False)
        )

        fig2 = px.bar(
            volume_by_exercise,
            x="exercise_standardized",
            y="volume_kg",
            title="Total volume by exercise",
        )

        st.plotly_chart(fig2, use_container_width=True)