import duckdb

con = duckdb.connect("data/workout_log.duckdb")

print("Tables:")
print(con.execute("SHOW TABLES").df())

print("\nSchema:")
print(con.execute("DESCRIBE workout_sets").df())

print("\nSample data:")
print(con.execute("SELECT * FROM workout_sets LIMIT 20").df())

con.close()