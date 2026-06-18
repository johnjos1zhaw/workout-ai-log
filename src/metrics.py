import pandas as pd
import numpy as np


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    df["date"] = pd.to_datetime(df["date"])
    df["reps"] = pd.to_numeric(df["reps"], errors="coerce")
    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
    df["duration_sec"] = pd.to_numeric(df["duration_sec"], errors="coerce")

    df["reps_filled"] = df["reps"].fillna(0)
    df["weight_filled"] = df["weight_kg"].fillna(0)

    df["volume_kg"] = df["reps_filled"] * df["weight_filled"]

    df["e1rm"] = np.where(
        (df["weight_kg"].notna()) & (df["reps"].notna()) & (df["reps"] > 0),
        df["weight_kg"] * (1 + df["reps"] / 30),
        np.nan,
    )

    df["week"] = df["date"].dt.to_period("W").astype(str)

    df["rep_range"] = pd.cut(
        df["reps"],
        bins=[0, 5, 12, 20, 100],
        labels=["Strength 1-5", "Hypertrophy 6-12", "Endurance 13-20", "Very high 20+"],
    )

    return df


def dashboard_summary(df: pd.DataFrame) -> dict:
    df = add_metrics(df)

    if df.empty:
        return {
            "weekly_volume": 0,
            "total_sets": 0,
            "training_days_this_week": 0,
            "prs_this_month": 0,
            "best_e1rm": 0,
        }

    latest_week = df["week"].max()
    latest_month = df["date"].dt.to_period("M").max()

    weekly_volume = df.loc[df["week"] == latest_week, "volume_kg"].sum()
    total_sets = len(df)

    training_days_this_week = (
        df.loc[df["week"] == latest_week, "date"].dt.date.nunique()
    )

    best_e1rm = df["e1rm"].max()

    prs = detect_prs(df)
    prs_this_month = prs[
        pd.to_datetime(prs["date"]).dt.to_period("M") == latest_month
    ].shape[0]

    return {
        "weekly_volume": weekly_volume,
        "total_sets": total_sets,
        "training_days_this_week": training_days_this_week,
        "prs_this_month": prs_this_month,
        "best_e1rm": best_e1rm if pd.notna(best_e1rm) else 0,
    }


def weekly_volume(df: pd.DataFrame) -> pd.DataFrame:
    df = add_metrics(df)

    return (
        df.groupby("week", as_index=False)["volume_kg"]
        .sum()
        .sort_values("week")
    )


def exercise_volume(df: pd.DataFrame) -> pd.DataFrame:
    df = add_metrics(df)

    return (
        df.groupby(["date", "exercise_standardized"], as_index=False)["volume_kg"]
        .sum()
        .sort_values("date")
    )


def exercise_e1rm(df: pd.DataFrame) -> pd.DataFrame:
    df = add_metrics(df)

    return (
        df.dropna(subset=["e1rm"])
        .groupby(["date", "exercise_standardized"], as_index=False)["e1rm"]
        .max()
        .sort_values("date")
    )


def top_sets(df: pd.DataFrame) -> pd.DataFrame:
    df = add_metrics(df)

    return (
        df.dropna(subset=["e1rm"])
        .sort_values(["date", "exercise_standardized", "e1rm"], ascending=[True, True, False])
        .groupby(["date", "exercise_standardized"], as_index=False)
        .first()
    )


def exercise_summary(df: pd.DataFrame, exercise: str) -> dict:
    df = add_metrics(df)
    ex = df[df["exercise_standardized"] == exercise].copy()

    if ex.empty:
        return {
            "current_e1rm": 0,
            "best_e1rm": 0,
            "best_weight": 0,
            "best_reps": 0,
            "sessions": 0,
            "total_volume": 0,
        }

    latest_date = ex["date"].max()
    latest = ex[ex["date"] == latest_date]

    return {
        "current_e1rm": latest["e1rm"].max(),
        "best_e1rm": ex["e1rm"].max(),
        "best_weight": ex["weight_kg"].max(),
        "best_reps": ex["reps"].max(),
        "sessions": ex["date"].nunique(),
        "total_volume": ex["volume_kg"].sum(),
    }


def detect_prs(df: pd.DataFrame) -> pd.DataFrame:
    df = add_metrics(df)
    df = df.sort_values(["exercise_standardized", "date", "set_number"]).copy()

    prs = []

    for exercise, group in df.groupby("exercise_standardized"):
        best_e1rm = -1
        best_weight = -1

        rep_prs = {}

        for _, row in group.iterrows():
            current_prs = []

            if pd.notna(row["e1rm"]) and row["e1rm"] > best_e1rm:
                current_prs.append("Best e1RM")
                best_e1rm = row["e1rm"]

            if pd.notna(row["weight_kg"]) and row["weight_kg"] > best_weight:
                current_prs.append("Weight PR")
                best_weight = row["weight_kg"]

            if pd.notna(row["weight_kg"]) and pd.notna(row["reps"]):
                weight = row["weight_kg"]
                reps = row["reps"]

                if weight not in rep_prs or reps > rep_prs[weight]:
                    current_prs.append(f"Rep PR at {weight:g}kg")
                    rep_prs[weight] = reps

            for pr_type in current_prs:
                prs.append(
                    {
                        "date": row["date"],
                        "exercise_standardized": exercise,
                        "pr_type": pr_type,
                        "weight_kg": row["weight_kg"],
                        "reps": row["reps"],
                        "e1rm": row["e1rm"],
                    }
                )

    return pd.DataFrame(prs)