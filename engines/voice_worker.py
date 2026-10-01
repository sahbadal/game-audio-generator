"""Runs in the voice venv (Chatterbox). Speaks each line in the voice of a reference clip.
Reads one JSON job per line on stdin; answers with one '@@RESULT {json}' line per job.

Simple version: the whole line is spoken in one pass, no splitting, no time-stretching.
Anything in square brackets is removed so it is never read aloud."""

import json
import os
import random
import re
import sys

import soundfile as sf
import torch
from chatterbox.tts import ChatterboxTTS

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

BRACKETS = re.compile(r"\[[^\]]*\]")


def emit(payload: dict) -> None:
    sys.stdout.write("@@RESULT " + json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", BRACKETS.sub(" ", text)).strip()


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxTTS.from_pretrained(device=device)
    print("[voice] worker v1 ready — whole line, no stretching", file=sys.stderr, flush=True)
    emit({"ready": True, "sample_rate": model.sr})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            job = json.loads(line)
            out_dir = job["out_dir"]
            os.makedirs(out_dir, exist_ok=True)

            ref = job.get("ref") or None
            if ref and not os.path.exists(ref):
                raise FileNotFoundError(f"Reference voice not found: {ref}")

            exaggeration = float(job.get("exaggeration", 0.5))
            cfg_weight = float(job.get("cfg_weight", 0.35))
            files = []

            for text in job["texts"]:
                for _ in range(int(job.get("count", 1))):
                    seed = int(job.get("seed", 0)) + len(files)
                    torch.manual_seed(seed)
                    random.seed(seed)

                    wav = model.generate(clean(text), audio_prompt_path=ref,
                                         exaggeration=exaggeration, cfg_weight=cfg_weight)

                    path = os.path.join(out_dir, f"raw_{len(files):03d}.wav")
                    sf.write(path, wav.squeeze(0).cpu().numpy(), model.sr)
                    files.append({"path": path, "text": text, "seed": seed})

            if device == "cuda":
                torch.cuda.empty_cache()
            emit({"ok": True, "sample_rate": model.sr, "files": files})

        except Exception as error:
            emit({"ok": False, "error": str(error)})


if __name__ == "__main__":
    main()
