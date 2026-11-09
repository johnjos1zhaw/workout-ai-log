"""Optional live parser check with synthetic data; does not write to DuckDB."""
from src.parser import parse_workout_note


def main():
    frame = parse_workout_note(
        "16.6.26 upper 1\nBench\n1x8x60kg\n"
    )
    required = {"date", "workout", "exercise", "set_number", "reps", "weight_kg"}
    if frame.empty or not required.issubset(frame.columns):
        raise RuntimeError("Parser returned no usable set")
    print({"parsed_rows": len(frame), "columns": list(frame.columns),
           "first_exercise": frame.iloc[0]["exercise"]})


if __name__ == "__main__":
    main()
