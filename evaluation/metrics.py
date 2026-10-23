"""Compute basic agent-evaluation metrics from a JSONL results file."""
import json
import sys
from pathlib import Path


def summarize(path: str) -> dict:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return {"total": 0, "successes": 0, "task_success_rate": 0.0, "mean_latency_ms": 0.0}
    successes = sum(bool(row.get("success")) for row in rows)
    latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    return {"total": len(rows), "successes": successes,
            "task_success_rate": round(successes / len(rows), 4),
            "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m evaluation.metrics evaluation/results/results.jsonl")
    print(json.dumps(summarize(sys.argv[1]), indent=2))
