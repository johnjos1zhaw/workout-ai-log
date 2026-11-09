"""Read-only data suitability profile for one-step performance forecasts."""
from src import training


def main():
    with training.connect(training.DB) as con:
        result = training.rows(con, """
            SELECT se.name, COUNT(DISTINCT s.id) AS sessions,
                   COUNT(DISTINCT s.session_date) AS days,
                   COUNT(ss.id) FILTER (WHERE ss.weight_kg IS NOT NULL
                       AND ss.weight_kg > 0 AND ss.reps > 0) AS valid_external_sets
            FROM sessions s JOIN session_exercises se ON se.session_id=s.id
            LEFT JOIN session_sets ss ON ss.session_exercise_id=se.id
            WHERE s.status='completed'
            GROUP BY se.name ORDER BY sessions DESC LIMIT 20
        """)
    for row in result:
        print(row)


if __name__ == "__main__":
    main()
