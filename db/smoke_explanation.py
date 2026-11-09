"""Optional one-request live API smoke test; never prints credentials."""
from src import explanations, progression


def main():
    analysis = progression.analyze("Hacksquat")
    result = explanations.explain(analysis)
    print({"source": result["source"], "recommendation": result["recommendation"],
           "fields": sorted(result)})
    if result["source"] != "llm":
        print("Live API explanation unavailable; deterministic fallback was used.")


if __name__ == "__main__":
    main()
