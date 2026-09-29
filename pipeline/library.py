import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

import config

# Slot ids: dotted, lowercase, optional @layer and #switch — e.g. veh.auto.engine@idle, npc.bark.panic#female
ID_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+(@[a-z0-9_]+)?(#[a-z0-9_]+)?$")


def validate_id(slot_id: str) -> str:
    slot_id = (slot_id or "").strip().lower()
    if not ID_PATTERN.match(slot_id):
        raise ValueError(
            f"Invalid slot id '{slot_id}'. Use dotted lowercase words, optional @layer / #switch, "
            f"e.g. veh.auto.engine@idle or npc.vendor.call#male")
    return slot_id


def domain_of(slot_id: str) -> str:
    return slot_id.split(".")[0]


def candidate_dir(slot_id: str) -> Path:
    return config.CANDIDATES_DIR / domain_of(slot_id) / slot_id


def _next_index(folder: Path, pattern: str) -> int:
    existing = list(folder.glob(pattern)) if folder.exists() else []
    return len(existing) + 1


def save_candidate(slot_id: str, audio: np.ndarray, sr: int, meta: dict) -> Path:
    folder = candidate_dir(slot_id)
    folder.mkdir(parents=True, exist_ok=True)

    index = _next_index(folder, f"{slot_id}__c*.wav")
    path = folder / f"{slot_id}__c{index:02d}.wav"
    sf.write(path, audio, sr, subtype="PCM_16")

    log_path = folder / "candidates.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    log.append({"file": path.name, "created": datetime.now().isoformat(timespec="seconds"), **meta})
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def list_slots() -> list:
    if not config.CANDIDATES_DIR.exists():
        return []
    return sorted(p.name for p in config.CANDIDATES_DIR.glob("*/*") if p.is_dir())


def list_candidates(slot_id: str) -> list:
    folder = candidate_dir(slot_id)
    return sorted(str(p) for p in folder.glob(f"{slot_id}__c*.wav")) if folder.exists() else []


def list_finals(slot_id: str) -> list:
    folder = config.FINAL_DIR / domain_of(slot_id)
    return sorted(str(p) for p in folder.glob(f"{slot_id}__v*.wav")) if folder.exists() else []


def approve(slot_id: str, candidate_path: str) -> Path:
    folder = config.FINAL_DIR / domain_of(slot_id)
    folder.mkdir(parents=True, exist_ok=True)

    index = _next_index(folder, f"{slot_id}__v*.wav")
    target = folder / f"{slot_id}__v{index:02d}.wav"
    shutil.copy2(candidate_path, target)

    if config.UNITY_AUDIO_DIR:
        unity_folder = Path(config.UNITY_AUDIO_DIR) / domain_of(slot_id)
        unity_folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, unity_folder / target.name)

    return target
