"""Non-destructive, verified migration of the historical workout database."""
import hashlib
from src import training


def main():
    path = training.DB
    with training.connect(path) as con:
        before = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
    backup = training.backup(path)
    with training.connect(backup) as con:
        backup_count = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
    if backup_count != before:
        raise RuntimeError("Backup row count differs")
    training.initialize(path)
    result = training.migrate_legacy(path)
    with training.connect(path) as con:
        after = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        mapped = con.execute("SELECT COUNT(*) FROM legacy_row_map").fetchone()[0]
    if before != after or before != mapped:
        raise RuntimeError("Migration validation failed; keep backup for recovery")
    print({"backup": str(backup), "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
           "source_rows": after, "mapped_rows": mapped, "provisional_sessions": result["sessions"]})


if __name__ == "__main__":
    main()
