"""Runs in the speech venv (Parler). Reads one JSON job per line on stdin, writes raw wavs,
answers with one '@@RESULT {json}' line per job. Anything else on stdout is ignored by the app."""

import json
import os
import sys

import soundfile as sf
import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer

REPO = "ai4bharat/indic-parler-tts"

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")


def emit(payload: dict) -> None:
    sys.stdout.write("@@RESULT " + json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # bf16 halves the memory with no audible difference; full precision when memory is not a concern.
    low_vram = os.environ.get("AUDIOGEN_LOW_VRAM") == "1" and device == "cuda"
    dtype = torch.bfloat16 if low_vram else torch.float32
    model = ParlerTTSForConditionalGeneration.from_pretrained(REPO, torch_dtype=dtype).to(device)
    tokenizer = AutoTokenizer.from_pretrained(REPO)
    desc_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
    sample_rate = model.config.sampling_rate

    emit({"ready": True, "sample_rate": sample_rate})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            job = json.loads(line)
            out_dir = job["out_dir"]
            os.makedirs(out_dir, exist_ok=True)

            description = desc_tokenizer(job["voice"], return_tensors="pt").to(device)
            files = []

            for text in job["texts"]:
                prompt = tokenizer(text, return_tensors="pt").to(device)

                for _ in range(int(job.get("count", 1))):
                    seed = int(job.get("seed", 0)) + len(files)
                    torch.manual_seed(seed)

                    audio = model.generate(
                        input_ids=description.input_ids,
                        attention_mask=description.attention_mask,
                        prompt_input_ids=prompt.input_ids,
                        prompt_attention_mask=prompt.attention_mask,
                        do_sample=True,
                    )

                    path = os.path.join(out_dir, f"raw_{len(files):03d}.wav")
                    sf.write(path, audio.float().cpu().numpy().squeeze(), sample_rate)
                    files.append({"path": path, "text": text, "seed": seed})

            if device == "cuda":
                torch.cuda.empty_cache()
            emit({"ok": True, "sample_rate": sample_rate, "files": files})

        except Exception as error:
            emit({"ok": False, "error": str(error)})


if __name__ == "__main__":
    main()
