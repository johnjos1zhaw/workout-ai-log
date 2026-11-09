# Workout AI Log

## GymCoach AI: aktueller Stand

Die Streamlit-App enthält jetzt zusätzlich Trainingsverwaltung, vorläufig migrierte
Historie, eine nachvollziehbare Fortschreibungsprognose für den nächsten
geschätzten 1RM-Wert und eine optionale KI-Erklärung. Das ursprüngliche
`workout_sets`-Schema und der Notizimport bleiben erhalten. Die historische
Zuordnung nach Datum und Workout-Text ist vorläufig; die Originalzeilen stehen
weiterhin unverändert in `workout_sets`.
Die vier Grundvorlagen **Leg 1**, **Upper Body 1**, **Leg 2** und **Upper Body 2**
sind mit regelmäßig protokollierten Übungen angelegt und können in der
Trainingsverwaltung bearbeitet werden.

### Lokal starten

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Für Parser und KI-Erklärung ist `OPENAI_API_KEY` in einer lokalen `.env`-Datei
erforderlich. Bei Ausfall der KI-Erklärung bleiben Kennzahlen, Empfehlung und
deterministischer Erklärungstext verfügbar.
Die lokale `.env` hat Vorrang vor einem bereits gesetzten Prozesswert für
`OPENAI_API_KEY`. Ein Live-Test der KI-Erklärung mit diesem Wert war erfolgreich.

Tests: `python -B -m unittest discover -s tests -v`.
Die wissenschaftliche Methodik und die tatsächlich gemessenen Baseline-Fehler
stehen in [docs/AI_PROJECT_DOCUMENTATION.md](docs/AI_PROJECT_DOCUMENTATION.md).
Die Sicherung vor der historischen Migration liegt lokal unter
`data/workout_log.pre_gymcoach_backup.duckdb` und ist von Git ausgeschlossen.

A personal data engineering and AI project for tracking gym workouts, analyzing strength progression, and practicing modern data engineering concepts.

The project is built as a learning platform to practice:

* Python
* SQL
* Data Modeling
* ETL Pipelines
* DuckDB
* Streamlit
* AI/LLM Integration
* Analytics Engineering
* Databricks (future)
* AWS (future)
* MCP / AI Agents (future)

---

# Project Goal

Replace the current manual workflow:

```text
Samsung Notes
    ↓
ChatGPT formatting
    ↓
Excel
    ↓
Manual analysis
```

with:

```text
Samsung Notes
    ↓
AI Parser
    ↓
Structured Workout Data
    ↓
DuckDB
    ↓
Analytics Dashboard
    ↓
Insights & Progress Tracking
```

The application should automatically transform messy workout notes into structured workout records and provide analytics for:

* Strength progression
* Volume progression
* Workout consistency
* Personal records
* Exercise-specific trends

---

# Current Features

## Workout Import

### Method 1: AI Workout Parsing

Paste raw workout notes from Samsung Notes.

Example:

```text
16.6.26 upper 1

EMOM 5 min 3x 15 push ups, 3x 10 pullups

Bench
1x10x40kg
1x10x60kg
1x7x60kg

Row machine
3x12x70kg
```

The application:

1. Sends the note to an LLM
2. Extracts structured workout sets
3. Converts the result into a DataFrame
4. Displays an editable preview
5. Saves the workout into DuckDB

---

### Method 2: Tabular Import

Paste existing workout data copied from Excel.

The application:

1. Parses the table
2. Validates columns
3. Displays an editable preview
4. Saves the workout into DuckDB

---

# Data Storage

Current storage layer:

```text
DuckDB
```

Database file:

```text
data/workout_log.duckdb
```

Current table:

```text
workout_sets
```

Schema:

| Column                | Description                         |
| --------------------- | ----------------------------------- |
| date                  | Workout date                        |
| workout               | Workout type (Upper 1, Leg 1, etc.) |
| exercise              | Original exercise name              |
| exercise_standardized | Standardized exercise name          |
| set_number            | Set number                          |
| target_sets           | Planned number of sets              |
| reps                  | Repetitions                         |
| duration_sec          | Duration-based exercises            |
| weight_kg             | Weight used                         |
| load_type             | external, bodyweight, duration      |
| is_unilateral_note    | Single-arm/single-leg notes         |
| notes                 | Additional notes                    |

---

# Analytics

## Dashboard KPIs

Current dashboard displays:

* Weekly Volume
* Training Days This Week
* PRs This Month
* Best e1RM

---

## Strength Metrics

Currently implemented:

### Estimated 1RM (e1RM)

Uses the Epley formula:

```python
e1RM = weight * (1 + reps / 30)
```

Examples:

```text
60kg × 8 reps
≈ 76kg e1RM
```

---

### Best e1RM

Highest estimated strength achieved for an exercise.

---

### Weight PR

Highest weight ever lifted.

---

### Rep PR

Most repetitions achieved at a given weight.

---

## Volume Metrics

Currently implemented:

### Volume Load

```text
Sets × Reps × Weight
```

Example:

```text
3 × 10 × 60kg
=
1800kg volume
```

### Weekly Volume

Total training volume accumulated during a week.

### Exercise Volume

Total volume accumulated per exercise.

---

## Exercise Analytics

For each exercise:

### KPI Cards

* Current e1RM
* Best e1RM
* Best Weight
* Best Reps

### Charts

* e1RM Trend
* Volume Trend

### History

* Full set history
* Weight progression
* Repetition progression

---

## PR Tracking

The application automatically detects:

* New e1RM PRs
* New Weight PRs
* New Rep PRs

---

## Advanced Analytics

Current advanced analytics:

* Rep Range Distribution
* Exercise Frequency

---

# Planned Features

## Workout-Day Analytics

Track progression for:

* Upper Body 1
* Upper Body 2
* Leg 1
* Leg 2

Metrics:

* Session Volume
* Session e1RM
* Session Frequency
* Progression Over Time

---

## Exercise Normalization

Goal:

Store all exercises in English using canonical names.

Examples:

```text
RDL
Romanian Deadlift
Rdl
```

↓

```text
Romanian Deadlift
```

Examples:

```text
Waden
Calf Raise
```

↓

```text
Calf Raise Seated
```

Planned architecture:

```text
exercise_aliases
        ↓
canonical_exercise
```

This avoids repeatedly using an LLM for exercise normalization.

---

## Muscle Group Analytics

Planned metrics:

* Sets per Muscle Group
* Volume per Muscle Group
* Push/Pull Ratio
* Upper/Lower Ratio
* Muscle Balance

---

## Consistency Metrics

Planned metrics:

* Workout Adherence
* Set Adherence
* Exercise Adherence
* Workout Consistency

---

## Databricks Integration

Future architecture:

```text
DuckDB
    ↓
Bronze
    ↓
Silver
    ↓
Gold
```

Implemented using:

* Delta Tables
* Spark SQL
* Databricks

---

## AWS Integration

Future cloud deployment:

* Streamlit Frontend
* API Layer
* S3 Storage
* Lambda Functions
* CloudWatch

---

## MCP Integration

Planned MCP tools:

```text
get_recent_workouts()
get_exercise_progress()
calculate_weekly_volume()
detect_personal_records()
add_workout_from_note()
```

This will allow AI assistants to interact directly with workout data.

---

# Local Development

## Setup

Create virtual environment:

```bash
python -m venv .venv
```

Activate:

```bash
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create `.env`

```env
OPENAI_API_KEY=your_api_key_here
```

---

## Run Application

```bash
streamlit run app.py
```

Application opens in browser.

---

# Project Structure

```text
workout-ai-log/
│
├── app.py
├── requirements.txt
├── .env
│
├── data/
│   └── workout_log.duckdb
│
├── src/
│   ├── db.py
│   ├── parser.py
│   ├── metrics.py
│   ├── validation.py
│   └── exercise_normalizer.py
│
├── tests/
│
└── README.md
```

---

# Ursprünglicher MVP-Status (historische Projektbeschreibung)

Phase: MVP

Completed:

* Streamlit UI
* DuckDB storage
* AI workout parsing
* Tabular workout import
* Editable data review
* Dashboard analytics
* e1RM calculations
* Volume tracking
* PR detection

In Progress:

* Workout-day analytics
* Exercise normalization
* Exercise catalog management

Planned:

* Databricks lakehouse layer
* AWS deployment
* MCP integration
* Advanced training analytics
