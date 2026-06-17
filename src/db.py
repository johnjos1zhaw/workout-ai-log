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
    df = con.execute("SELECT * FROM workout_sets ORDER BY date, workout, exercise, set_number").df()
    con.close()
    return df