import pandas as pd

def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df["reps"] = df["reps"].fillna(0)
    df["weight_kg"] = df["weight_kg"].fillna(0)
    df["duration_sec"] = df["duration_sec"].fillna(0)

    df["volume_kg"] = df["reps"] * df["weight_kg"]

    return df