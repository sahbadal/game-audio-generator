from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Where generated audio goes.
#   output/candidates/<domain>/<slot_id>/<slot_id>__c01.wav   every take, for review
#   output/final/<domain>/<slot_id>__v01.wav                  approved takes, ready for Unity
OUTPUT_DIR = ROOT / "output"
CANDIDATES_DIR = OUTPUT_DIR / "candidates"
FINAL_DIR = OUTPUT_DIR / "final"
TEMP_DIR = OUTPUT_DIR / "_tmp"

# Optional: approved files are also copied here, e.g.
#   Path(r"C:\Projects\Dreamscape\Assets\_Project\Audio\Generated")
# Leave as None to copy by hand.
UNITY_AUDIO_DIR = None

# Speech runs in its own venv (Parler needs older transformers than Stable Audio).
SPEECH_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
SPEECH_WORKER = ROOT / "engines" / "speech_worker.py"

# Character voices (Chatterbox) run in a third venv. Each character has a reference clip in
# voices/, e.g. voices/sofia_ref.wav — every line is spoken in that voice.
VOICE_PYTHON = ROOT / "venv_voice" / "Scripts" / "python.exe"
VOICE_WORKER = ROOT / "engines" / "voice_worker.py"
VOICES_DIR = ROOT / "voices"

DEFAULT_MANIFEST = ROOT / "audio_manifest.json"

# Stable Audio Open limit.
SFX_MAX_SECONDS = 47

# How many takes to generate per variation the manifest asks for, so there is a choice.
CANDIDATES_PER_VARIATION = 2

# Integrated loudness targets (LUFS) per category, from the audio architecture doc.
LOUDNESS = {
    "dialogue": -18.0,
    "npc_voice": -20.0,
    "npc_action": -18.0,
    "footstep": -24.0,
    "vehicle": -17.0,
    "world": -20.0,
    "spot": -22.0,
    "ambience": -26.0,
    "music": -18.0,
    "ui": -20.0,
}
DEFAULT_LOUDNESS = -20.0

CATEGORIES = list(LOUDNESS.keys())

DEFAULT_NEGATIVE = "music, speech, low quality, distortion, clipping, noise"