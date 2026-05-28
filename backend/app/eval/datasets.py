import json
from pathlib import Path


def load_suite(file_path: str) -> dict:
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def list_suites() -> list[str]:
    # Placeholder for listing available benchmark files
    p = Path("data/benchmarks")
    if p.exists():
        return [f.name for f in p.glob("*.json")]
    return []
