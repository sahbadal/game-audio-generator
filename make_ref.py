"""One-time: make a character's reference voice with Kokoro (Apache 2.0), no recording needed.
Run in venv_voice:
    python make_ref.py                      -> voices/sofia_ref.wav with bf_emma
    python make_ref.py bf_isabella sofia    -> try another British voice
British female voices: bf_emma, bf_isabella, bf_alice, bf_lily. British male: bm_george, bm_lewis.
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

VOICE = sys.argv[1] if len(sys.argv) > 1 else "bf_emma"
NAME = sys.argv[2] if len(sys.argv) > 2 else "sofia"

# The clone copies the reference's rhythm as well as its voice. A relaxed, chatty reference
# with pauses gives chatty lines; a read-aloud reference gives read-aloud lines.
TEXT = ("Oh, hello! So, um... I only got here this morning. And honestly? "
        "Everything feels so new... the streets, the colours, the sea. "
        "It's a bit much, you know... but I think I love it already.")

lang = "b" if VOICE.startswith("b") else "a"  # b = British, a = American
pipeline = KPipeline(lang_code=lang)

chunks = []
for _, _, audio in pipeline(TEXT, voice=VOICE, speed=0.88):
    chunks.append(audio.cpu().numpy() if hasattr(audio, "cpu") else np.asarray(audio))

out = Path(__file__).resolve().parent / "voices" / f"{NAME}_ref.wav"
out.parent.mkdir(exist_ok=True)
sf.write(out, np.concatenate(chunks), 24000)
print(f"saved {out}")