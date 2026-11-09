"""Reproducible read-only baseline report."""
from src import progression, training


def main():
    with training.connect(training.DB) as con:
        exercises = [row[0] for row in con.execute("""
            SELECT se.name FROM sessions s
            JOIN session_exercises se ON se.session_id=s.id
            JOIN session_sets ss ON ss.session_exercise_id=se.id
            WHERE s.status='completed' AND ss.reps>0 AND ss.weight_kg>0
            GROUP BY se.name ORDER BY COUNT(DISTINCT s.id) DESC LIMIT 10
        """).fetchall()]
    for name in exercises:
        result = progression.analyze(name)
        print(name, result["evaluation"], result["recommendation"])


if __name__ == "__main__":
    main()
