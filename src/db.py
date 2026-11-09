import duckdb
from pathlib import Path

DB_PATH = Path("data/workout_log.duckdb")

def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    return duckdb.connect(str(DB_PATH))

def init_db():
    con = get_connection()
    con.execute("""
        CREATE TABLE IF NOT EXISTS workout_sets (
            date DATE,
            workout VARCHAR,
            exercise VARCHAR,
            exercise_standardized VARCHAR,
            set_number INTEGER,
            target_sets INTEGER,
            reps INTEGER,
            duration_sec INTEGER,
            weight_kg DOUBLE,
            load_type VARCHAR,
            is_unilateral_note VARCHAR,
            notes VARCHAR
        )
    """)
    con.close()

def insert_workout_sets(df):
    con = get_connection()
    con.register("new_sets", df)
    con.execute("INSERT INTO workout_sets SELECT * FROM new_sets")
    con.close()

def load_workout_sets():
    con = get_connection()
    has_sessions = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='sessions'"
    ).fetchone()[0] > 0
    if has_sessions:
        df = con.execute("""
            SELECT CAST(s.session_date AS TIMESTAMP) AS date,
                   s.name AS workout,
                   COALESCE(json_extract_string(l.raw_json, '$.exercise'), se.name) AS exercise,
                   se.name AS exercise_standardized,
                   ss.set_number,
                   TRY_CAST(json_extract_string(l.raw_json, '$.target_sets') AS INTEGER) AS target_sets,
                   ss.reps, ss.duration_sec, ss.weight_kg,
                   CASE WHEN l.set_id IS NOT NULL
                        THEN json_extract_string(l.raw_json, '$.load_type')
                        ELSE se.kind END AS load_type,
                   json_extract_string(l.raw_json, '$.is_unilateral_note') AS is_unilateral_note,
                   ss.notes
            FROM session_sets ss
            JOIN session_exercises se ON se.id=ss.session_exercise_id
            JOIN sessions s ON s.id=se.session_id
            LEFT JOIN legacy_row_map l ON l.set_id=ss.id
            WHERE s.status='completed'
            ORDER BY date, workout, exercise, ss.set_number
        """).df()
    else:
        df = con.execute(
            "SELECT * FROM workout_sets ORDER BY date, workout, exercise, set_number"
        ).df()
    con.close()
    return df

def delete_all_data():
    con = get_connection()
    con.execute("DELETE FROM workout_sets")
    con.close()
