import json
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.setdefault("slots", [])
    return data


def save(path: Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def expand(slot: dict) -> list:
    """One job per layer. A slot with layers ['idle', 'fast'] becomes id@idle and id@fast,
    with {layer} in the prompt replaced by the layer name."""
    layers = slot.get("layers") or [None]
    jobs = []
    for layer in layers:
        job = dict(slot)
        if layer:
            job["id"] = f"{slot['id']}@{layer}"
            job["prompt"] = slot.get("prompt", "").replace("{layer}", layer)
        jobs.append(job)
    return jobs
