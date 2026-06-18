import duckdb
from src.exercise_normalizer import normalize_exercise_dataframe

DB_PATH = "data/workout_log.duckdb"

con = duckdb.connect(DB_PATH)

df = con.execute("SELECT * FROM workout_sets").df()

if df.empty:
    print("No data found.")
else:
    normalized_df = normalize_exercise_dataframe(df)

    con.execute("DROP TABLE workout_sets")
    con.register("normalized_sets", normalized_df)
    con.execute("CREATE TABLE workout_sets AS SELECT * FROM normalized_sets")

    print(f"Normalized {len(normalized_df)} rows.")

con.close()