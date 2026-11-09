"""Training management; the historical workout_sets table remains untouched."""
import json
import shutil
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import duckdb

DB = Path("data/workout_log.duckdb")
KINDS = ("external", "bodyweight", "duration")

def uid():
    return str(uuid4())

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

@contextmanager
def connect(path=DB, write=False):
    con = duckdb.connect(str(path), read_only=not write)
    try:
        if write:
            con.execute("BEGIN")
        yield con
        if write:
            con.execute("COMMIT")
    except Exception:
        if write:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()

def backup(path=DB, target=None):
    path = Path(path)
    target = Path(target or path.with_name(path.stem + ".pre_gymcoach_backup.duckdb"))
    if target.exists():
        raise FileExistsError(target)
    shutil.copy2(path, target)
    if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
        target.unlink()
        raise IOError("Backup verification failed")
    return target

SCHEMA = [
"""CREATE TABLE IF NOT EXISTS exercises (
 id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL UNIQUE,
 kind VARCHAR NOT NULL CHECK(kind IN ('external','bodyweight','duration','unknown')),
 archived_at TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS templates (
 id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL UNIQUE, archived_at TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS template_exercises (
 id VARCHAR PRIMARY KEY, template_id VARCHAR NOT NULL,
 exercise_id VARCHAR NOT NULL, position INTEGER NOT NULL,
 UNIQUE(template_id,position))""",
"""CREATE TABLE IF NOT EXISTS sessions (
 id VARCHAR PRIMARY KEY, template_id VARCHAR,
 name VARCHAR NOT NULL, session_date DATE NOT NULL,
 status VARCHAR NOT NULL CHECK(status IN ('active','completed','abandoned')),
 started_at TIMESTAMP, ended_at TIMESTAMP, duration_sec INTEGER,
 source VARCHAR NOT NULL CHECK(source IN ('manual','legacy')))""",
"""CREATE TABLE IF NOT EXISTS session_exercises (
 id VARCHAR PRIMARY KEY, session_id VARCHAR NOT NULL,
 exercise_id VARCHAR, name VARCHAR NOT NULL,
 kind VARCHAR NOT NULL, position INTEGER NOT NULL, UNIQUE(session_id,position))""",
"""CREATE TABLE IF NOT EXISTS session_sets (
 id VARCHAR PRIMARY KEY, session_exercise_id VARCHAR NOT NULL,
 set_number INTEGER NOT NULL, reps INTEGER, weight_kg DOUBLE, bodyweight_kg DOUBLE,
 duration_sec INTEGER, rest_sec INTEGER, rpe DOUBLE, notes VARCHAR,
 recorded_at TIMESTAMP, legacy_row_number INTEGER)""",
"""CREATE TABLE IF NOT EXISTS history_edits (
 id VARCHAR PRIMARY KEY, entity VARCHAR NOT NULL, entity_id VARCHAR NOT NULL,
 action VARCHAR NOT NULL, before_json VARCHAR, after_json VARCHAR,
 changed_at TIMESTAMP NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS legacy_row_map (
 legacy_row_number INTEGER PRIMARY KEY, set_id VARCHAR NOT NULL UNIQUE,
 raw_json VARCHAR NOT NULL)""",
]

def initialize(path=DB):
    with connect(path, True) as con:
        for sql in SCHEMA:
            con.execute(sql)

def rows(con, sql, args=()):
    result = con.execute(sql, args)
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, item)) for item in result.fetchall()]

def one(con, sql, args=()):
    result = rows(con, sql, args)
    if not result:
        raise ValueError("Record not found")
    return result[0]

def audit(con, entity, entity_id, action, before=None, after=None):
    con.execute("INSERT INTO history_edits VALUES (?,?,?,?,?,?,?)",
                [uid(), entity, entity_id, action,
                 json.dumps(before, default=str) if before is not None else None,
                 json.dumps(after, default=str) if after is not None else None, now()])

def exercises(path=DB, archived=False):
    with connect(path) as con:
        return rows(con, "SELECT * FROM exercises " +
                    ("" if archived else "WHERE archived_at IS NULL ") + "ORDER BY name")

def create_exercise(name, kind, path=DB):
    name = name.strip()
    if not name or kind not in KINDS:
        raise ValueError("Name and valid type required")
    eid = uid()
    with connect(path, True) as con:
        con.execute("INSERT INTO exercises VALUES (?,?,?,NULL)", [eid,name,kind])
    return eid

def edit_exercise(eid, name, kind, path=DB):
    name = name.strip()
    if not name or kind not in KINDS:
        raise ValueError("Name and valid type required")
    with connect(path, True) as con:
        before = one(con, "SELECT * FROM exercises WHERE id=?", [eid])
        con.execute("UPDATE exercises SET name=?,kind=? WHERE id=?", [name,kind,eid])
        audit(con, "exercise", eid, "edit", before,
              one(con, "SELECT * FROM exercises WHERE id=?", [eid]))

def archive_exercise(eid, path=DB):
    with connect(path, True) as con:
        before = one(con, "SELECT * FROM exercises WHERE id=?", [eid])
        con.execute("UPDATE exercises SET archived_at=? WHERE id=?", [now(),eid])
        audit(con, "exercise", eid, "archive", before)

def templates(path=DB, archived=False):
    with connect(path) as con:
        return rows(con, "SELECT * FROM templates " +
                    ("" if archived else "WHERE archived_at IS NULL ") + "ORDER BY name")

def save_template(name, exercise_ids, path=DB, template_id=None):
    name = name.strip()
    if not name or len(exercise_ids) != len(set(exercise_ids)):
        raise ValueError("Template name and unique exercise IDs required")
    with connect(path, True) as con:
        if template_id:
            before = one(con, "SELECT * FROM templates WHERE id=?", [template_id])
            con.execute("UPDATE templates SET name=? WHERE id=?", [name,template_id])
            con.execute("DELETE FROM template_exercises WHERE template_id=?", [template_id])
        else:
            template_id, before = uid(), None
            con.execute("INSERT INTO templates VALUES (?,?,NULL)", [template_id,name])
        for position, eid in enumerate(exercise_ids, 1):
            ex = one(con, "SELECT * FROM exercises WHERE id=?", [eid])
            if ex["archived_at"] is not None:
                raise ValueError("Archived exercise")
            con.execute("INSERT INTO template_exercises VALUES (?,?,?,?)",
                        [uid(),template_id,eid,position])
        audit(con, "template", template_id, "edit" if before else "create", before,
              {"name":name,"exercise_ids":exercise_ids})
    return template_id

def template_items(template_id, path=DB):
    with connect(path) as con:
        return rows(con, """SELECT te.*,e.name,e.kind FROM template_exercises te
            JOIN exercises e ON e.id=te.exercise_id WHERE template_id=? ORDER BY position""",
            [template_id])

def archive_template(template_id, path=DB):
    with connect(path, True) as con:
        before = one(con, "SELECT * FROM templates WHERE id=?", [template_id])
        con.execute("UPDATE templates SET archived_at=? WHERE id=?", [now(),template_id])
        audit(con, "template", template_id, "archive", before)

def start_session(template_id, path=DB):
    sid, started = uid(), now()
    with connect(path, True) as con:
        template = one(con, "SELECT * FROM templates WHERE id=?", [template_id])
        if template["archived_at"] is not None:
            raise ValueError("Archived template")
        items = rows(con, """SELECT te.position,e.id,e.name,e.kind,e.archived_at
            FROM template_exercises te JOIN exercises e ON e.id=te.exercise_id
            WHERE te.template_id=? ORDER BY te.position""", [template_id])
        if any(item["archived_at"] is not None for item in items):
            raise ValueError("Template contains an archived exercise")
        con.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                    [sid,template_id,template["name"],started.date(),"active",started,None,None,"manual"])
        for item in items:
            con.execute("INSERT INTO session_exercises VALUES (?,?,?,?,?,?)",
                        [uid(),sid,item["id"],item["name"],item["kind"],item["position"]])
    return sid

def sessions(path=DB, status=None):
    with connect(path) as con:
        return rows(con, "SELECT * FROM sessions " +
                    ("WHERE status=? " if status else "") +
                    "ORDER BY session_date DESC,started_at DESC NULLS LAST",
                    [status] if status else [])

def session_detail(session_id, path=DB):
    with connect(path) as con:
        session = one(con, "SELECT * FROM sessions WHERE id=?", [session_id])
        session["exercises"] = rows(con, "SELECT * FROM session_exercises WHERE session_id=? ORDER BY position", [session_id])
        for ex in session["exercises"]:
            ex["sets"] = rows(con, "SELECT * FROM session_sets WHERE session_exercise_id=? ORDER BY set_number,id", [ex["id"]])
        return session

def add_session_exercise(session_id, exercise_id, path=DB):
    with connect(path, True) as con:
        one(con, "SELECT * FROM sessions WHERE id=?", [session_id])
        ex = one(con, "SELECT * FROM exercises WHERE id=?", [exercise_id])
        if ex["archived_at"] is not None:
            raise ValueError("Archived exercise")
        position = con.execute("SELECT COALESCE(MAX(position),0)+1 FROM session_exercises WHERE session_id=?", [session_id]).fetchone()[0]
        seid = uid()
        con.execute("INSERT INTO session_exercises VALUES (?,?,?,?,?,?)",
                    [seid,session_id,exercise_id,ex["name"],ex["kind"],position])
        audit(con, "session_exercise", seid, "create", after={"session_id":session_id,"exercise_id":exercise_id})
    return seid

def validate_set(kind, reps, weight_kg, bodyweight_kg, duration_sec, rest_sec, rpe):
    if kind == "external" and (reps is None or reps <= 0 or weight_kg is None or weight_kg <= 0):
        raise ValueError("Positive repetitions and weight required")
    if kind == "bodyweight" and (reps is None or reps <= 0 or bodyweight_kg is None or bodyweight_kg <= 0):
        raise ValueError("Positive repetitions and bodyweight required")
    if kind == "duration" and (duration_sec is None or duration_sec <= 0):
        raise ValueError("Positive duration required")
    if rest_sec is not None and rest_sec < 0:
        raise ValueError("Rest must be nonnegative")
    if rpe is not None and not 1 <= rpe <= 10:
        raise ValueError("RPE must be between 1 and 10")

def save_set(session_exercise_id, *, set_id=None, reps=None, weight_kg=None,
             bodyweight_kg=None, duration_sec=None, rest_sec=None, rpe=None,
             notes=None, path=DB):
    with connect(path, True) as con:
        ex = one(con, """SELECT se.*,s.status FROM session_exercises se
            JOIN sessions s ON s.id=se.session_id WHERE se.id=?""", [session_exercise_id])
        if ex["status"] == "abandoned":
            raise ValueError("Abandoned session")
        validate_set(ex["kind"],reps,weight_kg,bodyweight_kg,duration_sec,rest_sec,rpe)
        if set_id:
            before = one(con, "SELECT * FROM session_sets WHERE id=? AND session_exercise_id=?",
                         [set_id,session_exercise_id])
            con.execute("""UPDATE session_sets SET reps=?,weight_kg=?,bodyweight_kg=?,
                duration_sec=?,rest_sec=?,rpe=?,notes=? WHERE id=?""",
                [reps,weight_kg,bodyweight_kg,duration_sec,rest_sec,rpe,notes,set_id])
        else:
            before, set_id = None, uid()
            number = con.execute("SELECT COALESCE(MAX(set_number),0)+1 FROM session_sets WHERE session_exercise_id=?", [session_exercise_id]).fetchone()[0]
            con.execute("INSERT INTO session_sets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [set_id,session_exercise_id,number,reps,weight_kg,bodyweight_kg,
                         duration_sec,rest_sec,rpe,notes,now(),None])
        audit(con, "set", set_id, "edit" if before else "create", before,
              one(con, "SELECT * FROM session_sets WHERE id=?", [set_id]))
    return set_id

def remove_set(set_id, path=DB):
    with connect(path, True) as con:
        before = one(con, "SELECT * FROM session_sets WHERE id=?", [set_id])
        con.execute("DELETE FROM session_sets WHERE id=?", [set_id])
        audit(con, "set", set_id, "delete", before)

def remove_session_exercise(session_exercise_id, path=DB):
    with connect(path, True) as con:
        before = one(con, "SELECT * FROM session_exercises WHERE id=?", [session_exercise_id])
        sets = rows(con, "SELECT * FROM session_sets WHERE session_exercise_id=?", [session_exercise_id])
        con.execute("DELETE FROM session_sets WHERE session_exercise_id=?", [session_exercise_id])
        con.execute("DELETE FROM session_exercises WHERE id=?", [session_exercise_id])
        audit(con, "session_exercise", session_exercise_id, "delete", {"exercise":before,"sets":sets})

def finish_session(session_id, path=DB):
    with connect(path, True) as con:
        before = one(con, "SELECT * FROM sessions WHERE id=?", [session_id])
        if before["status"] != "active" or before["started_at"] is None:
            raise ValueError("Only active sessions can be finished")
        ended = now()
        duration = max(0, int((ended-before["started_at"]).total_seconds()))
        con.execute("UPDATE sessions SET status='completed',ended_at=?,duration_sec=? WHERE id=?",
                    [ended,duration,session_id])
        audit(con, "session", session_id, "finish", before,
              one(con, "SELECT * FROM sessions WHERE id=?", [session_id]))

def migrate_legacy(path=DB):
    """Group date+name provisionally; retain every source row and its original values.

    The caller must verify a backup first. Running again makes no changes.
    """
    with connect(path, True) as con:
        if con.execute("SELECT COUNT(*) FROM sessions WHERE source='legacy'").fetchone()[0]:
            source_count = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
            mapped = con.execute("SELECT COUNT(*) FROM legacy_row_map").fetchone()[0]
            if source_count != mapped:
                raise ValueError("Partial legacy migration detected")
            return {"rows": mapped, "sessions": con.execute(
                "SELECT COUNT(*) FROM sessions WHERE source='legacy'").fetchone()[0]}
        source = rows(con, "SELECT row_number() OVER () AS source_number,* FROM workout_sets")
        groups, occurrences, positions = {}, {}, {}
        kind_by_name = {}
        for row in source:
            name = (row["exercise_standardized"] or row["exercise"] or "").strip()
            kind = row["load_type"] if row["load_type"] in KINDS else "unknown"
            kind_by_name.setdefault(name, set()).add(kind)
        catalog = {}
        existing = {r["name"]: r["id"] for r in rows(con, "SELECT id,name FROM exercises")}
        for name, kinds in kind_by_name.items():
            if not name:
                continue
            if name in existing:
                catalog[name] = existing[name]
                continue
            eid = uid()
            kind = next(iter(kinds)) if len(kinds) == 1 else "unknown"
            con.execute("INSERT INTO exercises VALUES (?,?,?,NULL)", [eid,name,kind])
            catalog[name] = eid
        for row in source:
            day = row["date"].date() if hasattr(row["date"], "date") else row["date"]
            group_key = (day, row["workout"])
            if group_key not in groups:
                sid = uid()
                con.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                            [sid,None,row["workout"],day,"completed",None,None,None,"legacy"])
                groups[group_key] = sid
            sid = groups[group_key]
            ex_name = (row["exercise_standardized"] or row["exercise"] or "").strip()
            kind = row["load_type"] if row["load_type"] in KINDS else "unknown"
            occurrence_key = (sid,row["exercise"],ex_name,kind)
            if occurrence_key not in occurrences:
                seid = uid()
                position = positions.get(sid, 0) + 1
                positions[sid] = position
                con.execute("INSERT INTO session_exercises VALUES (?,?,?,?,?,?)",
                            [seid,sid,catalog.get(ex_name),ex_name,kind,position])
                occurrences[occurrence_key] = seid
            set_id = uid()
            con.execute("INSERT INTO session_sets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [set_id,occurrences[occurrence_key],row["set_number"],row["reps"],
                         row["weight_kg"],None,row["duration_sec"],None,None,row["notes"],
                         None,row["source_number"]])
            raw = {k:v for k,v in row.items() if k != "source_number"}
            con.execute("INSERT INTO legacy_row_map VALUES (?,?,?)",
                        [row["source_number"],set_id,json.dumps(raw,default=str)])
        mapped = con.execute("SELECT COUNT(*) FROM legacy_row_map").fetchone()[0]
        if mapped != len(source):
            raise ValueError("Legacy row count mismatch")
        return {"rows": mapped, "sessions": len(groups)}


def import_workout_sets(frame, path=DB):
    """Keep the legacy dashboard and normalized history in sync atomically."""
    import pandas as pd
    required = ["date","workout","exercise","exercise_standardized","set_number",
                "target_sets","reps","duration_sec","weight_kg","load_type",
                "is_unilateral_note","notes"]
    if frame.empty or any(col not in frame.columns for col in required):
        raise ValueError("Import requires at least one row and all expected columns")
    clean = frame[required].astype(object).where(pd.notna(frame[required]), None)
    records = clean.to_dict("records")
    for row in records:
        day = pd.to_datetime(row["date"]).date()
        row["date"] = datetime.combine(day, datetime.min.time())
        for column in ("set_number","target_sets","reps","duration_sec"):
            if row[column] is not None:
                row[column] = int(row[column])
        if row["weight_kg"] is not None:
            row["weight_kg"] = float(row["weight_kg"])
        for column in ("workout","exercise","exercise_standardized",
                       "load_type","is_unilateral_note","notes"):
            if row[column] is not None:
                row[column] = str(row[column])
    clean = pd.DataFrame(records, columns=required)
    with connect(path, True) as con:
        before = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        mapped_before = con.execute("SELECT COUNT(*) FROM legacy_row_map").fetchone()[0]
        if before != mapped_before:
            raise ValueError("Legacy source and normalized mapping differ")
        con.register("incoming_sets", clean)
        con.execute("INSERT INTO workout_sets SELECT * FROM incoming_sets")
        groups, occurrences, positions, set_ids = {}, {}, {}, []
        catalog = {row["name"]: row for row in rows(con, "SELECT * FROM exercises")}
        for index, row in enumerate(records, 1):
            date = row["date"].date()
            if not row["workout"] or not row["exercise"]:
                raise ValueError("Workout and exercise names required")
            group = (date,row["workout"])
            if group not in groups:
                sid = uid()
                con.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                            [sid,None,row["workout"],date,"completed",None,None,None,"legacy"])
                groups[group] = sid
            sid = groups[group]
            name = (row["exercise_standardized"] or row["exercise"]).strip()
            kind = row["load_type"] if row["load_type"] in KINDS else "unknown"
            if name not in catalog:
                eid = uid()
                con.execute("INSERT INTO exercises VALUES (?,?,?,NULL)", [eid,name,kind])
                catalog[name] = {"id":eid,"kind":kind}
            occurrence = (sid,row["exercise"],name,kind)
            if occurrence not in occurrences:
                seid = uid()
                position = positions.get(sid,0)+1
                positions[sid] = position
                con.execute("INSERT INTO session_exercises VALUES (?,?,?,?,?,?)",
                            [seid,sid,catalog[name]["id"],name,kind,position])
                occurrences[occurrence] = seid
            set_id = uid()
            set_ids.append(set_id)
            con.execute("INSERT INTO session_sets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [set_id,occurrences[occurrence],row["set_number"],row["reps"],
                         row["weight_kg"],None,row["duration_sec"],None,None,row["notes"],
                         None,before+index])
            con.execute("INSERT INTO legacy_row_map VALUES (?,?,?)",
                        [before+index,set_id,json.dumps(row,default=str)])
        after = con.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        if after != before+len(records):
            raise ValueError("Import row count mismatch")
        mapped_after = con.execute("SELECT COUNT(*) FROM legacy_row_map").fetchone()[0]
        if mapped_after != after:
            raise ValueError("Import provenance count mismatch")
    return {"row_count": len(records), "set_ids": set_ids,
            "session_ids": list(groups.values()), "legacy_total": after}


def imported_sets(set_ids, path=DB):
    """Read back exactly the newly committed sets for the user's save receipt."""
    if not set_ids:
        return []
    placeholders = ",".join("?" for _ in set_ids)
    with connect(path) as con:
        return rows(con, f"""SELECT s.session_date AS date, s.name AS workout,
            se.name AS exercise, ss.set_number, ss.reps, ss.weight_kg,
            ss.duration_sec, ss.notes, ss.id AS set_id
            FROM session_sets ss JOIN session_exercises se ON se.id=ss.session_exercise_id
            JOIN sessions s ON s.id=se.session_id
            WHERE ss.id IN ({placeholders}) ORDER BY ss.legacy_row_number""", set_ids)
