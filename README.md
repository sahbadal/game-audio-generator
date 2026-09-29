# AudioGen

A local, offline audio generation studio for game development. AudioGen wraps three open-source models in one Gradio web UI so you can **generate, review and approve** game audio, one sound at a time or in bulk from a JSON manifest.

Built for the game **Dreamscape**, but nothing in the tool is game-specific.

## What it does

| Tab | Purpose | Model | Worker | Environment |
|---|---|---|---|---|
| **Sound effect** | Sound effects, ambience, UI sounds, vehicle loops | Stable Audio Open | `engines/sfx_stable.py` | `venv_sfx` |
| **Speech** | Named-speaker voice lines (Hindi, Marathi, English) | Parler-TTS | `engines/speech_worker.py` | `venv` |
| **Character voice** | Lines spoken in a specific character's cloned voice | Chatterbox | `engines/voice_worker.py` | `venv_voice` |
| **Review** | Listen to takes and approve the best one | n/a | `pipeline/library.py` | n/a |
| **Batch (manifest)** | Generate many slots at once from a JSON file | all three | `pipeline/manifest.py` | n/a |

Each model lives in its **own virtual environment** because their dependencies conflict. The main app calls the workers, so you only launch one thing.

## Workflow

```
Generate  ->  output/candidates/  ->  Review tab  ->  output/final/
 (takes)        (all takes)          (listen, pick)    (approved files)
```

1. Generate takes, either one at a time in a tab or many via a manifest.
2. Takes are saved in `output/candidates/<prefix>/<slot id>/`.
3. Open the **Review** tab, pick a slot, listen to each take, and press **Approve this take**.
4. Approved files are copied to `output/final/`.

## Project layout

```
AudioGenModel/
├── app.py                  # Gradio UI, the only file you run
├── config.py               # Paths and defaults
├── make_ref.py             # Builds reference clips for Character voice
├── engines/
│   ├── sfx_stable.py       # Stable Audio Open (sound effects)
│   ├── speech_worker.py    # Parler-TTS worker
│   ├── speech_client.py    # Client used by the app to talk to the worker
│   └── voice_worker.py     # Chatterbox worker
├── pipeline/
│   ├── manifest.py         # Reads and updates manifest files
│   ├── library.py          # Candidate and final file management
│   └── post.py             # Post-processing
├── voices/                 # Reference clips (not committed)
├── output/                 # Generated audio (not committed)
├── audio_manifest_*.json   # Batch manifests
└── requirements_*.txt      # Package lists for each environment
```

## Requirements

- Windows with an NVIDIA GPU (developed on an RTX 5060 Ti, 16 GB VRAM)
- Python 3.11
- [ffmpeg](https://ffmpeg.org/) available on your PATH (for post-processing)
- A Hugging Face account. Some models are gated and need you to accept their terms and log in once with `huggingface-cli login`.

## Setup

Create the three environments and install each one from its requirements file.

```bash
# Speech (Parler-TTS)
python -m venv venv
venv/Scripts/python -m pip install -r requirements_speech.txt

# Character voice (Chatterbox)
python -m venv venv_voice
venv_voice/Scripts/python -m pip install -r requirements_voice.txt

# Sound effects (Stable Audio Open)
python -m venv venv_sfx
venv_sfx/Scripts/python -m pip install -r requirements_sfx.txt
```

Some packages were installed from GitHub rather than PyPI (for example Parler-TTS). If a requirements file misses one, install it manually, for example:

```bash
venv/Scripts/python -m pip install git+https://github.com/huggingface/parler-tts.git
```

## Running

Activate the SFX environment and start the app:

```bash
source venv_sfx/Scripts/activate
python app.py
```

The UI opens at `http://127.0.0.1:7860`.

> **VRAM tip:** all three models can end up in GPU memory at once. If generation becomes slow, close the app, restart it, and use only the tab you need. Watch **Dedicated GPU memory** and **Shared GPU memory** in Task Manager. Shared memory should stay near zero.

## Using each tab

### Sound effect

| Field | Notes |
|---|---|
| Slot id | Name of the sound, for example `veh.hatchback.engine.idle`. The first part becomes the output folder. |
| Category | `dialogue`, `npc_voice`, `npc_action`, `footstep`, `vehicle`, `world`, `spot`, `ambience`, `music`, `ui` |
| Prompt / Negative prompt | What you want and what to avoid |
| Seconds | 1 to 47 |
| Takes | How many variations to generate |
| Steps | Quality vs speed. 70 to 100 is a good range. Higher is slower. |
| Seed | `-1` is random. Fix it to reproduce a sound. |
| Loop | Crossfades the ends so the clip loops cleanly |
| Mono | Use for 3D positional sounds. Turn off for ambience and UI. |

### Speech

Enter one line per row (Hindi, Marathi or English) and a voice description, for example: *"Sanjay speaks in a warm, friendly tone at a moderate pace. The recording is very clear audio, close up, with no background noise."* Use the same speaker name in every slot for one NPC so all their lines match.

### Character voice

Use this tab when a character needs **the same voice across many lines** (for example Sofia or Rajan). Chatterbox copies the voice from a short reference clip, so the reference decides how the character sounds.

**Step 1: Make the reference clip**

1. Take a clean recording of the voice, 10 to 15 seconds long, with no music, no background noise and one speaker only.
2. Run `make_ref.py` on it. It saves the cleaned reference into `voices/`, for example `voices/sofia_ref.wav`. Check the top of `make_ref.py` for its exact arguments.

**Step 2: Listen to the reference first**

Open the `.wav` from `voices/` in any audio player before you use it. The generated voice can only be as good as this clip. If it has noise, echo or several speakers, redo Step 1 with a cleaner source.

**Step 3: Generate lines in that voice**

1. Open the **Character voice** tab and press **Refresh voices**.
2. Choose the clip in **Reference voice**, for example `sofia_ref.wav`.
3. Enter a **Slot id** such as `story.sofia.s1_01_greet` and pick a category (for example `dialogue`).
4. Write one line per row. Write normally: the voice pauses after `.`, `?`, `!` and `...`.
5. Press **Generate**, then listen and approve in the **Review** tab.

| Setting | What it does | Default |
|---|---|---|
| Expressiveness | Higher is more emotional and exaggerated | 0.45 |
| Pacing | Lower is slower and more natural | 0.25 |
| Speed | Playback speed, pitch is kept | 0.85 |
| Pause length | Silence between sentences | 1 |
| Takes per line | Variations to choose from | 2 |
| Seed | `-1` is random. Fix it to repeat a result. | 42 |

Every clip Chatterbox generates carries an inaudible PerTh watermark, so the audio can be identified as AI-generated later.

**Only clone voices you have permission to use.** Use your own recordings, a voice actor who agreed in writing, or a voice you have the rights to. Do not clone real people without their consent.

## Batch manifests

A manifest is a JSON file. Point the **Batch** tab at it, choose which status to run (`todo` or `generated`), and press **Run batch**. Slots run one after another and are marked `generated` when finished.

### SFX slot

```json
{
  "id": "veh.hatchback.engine.idle",
  "category": "vehicle",
  "model": "sfx",
  "prompt": "small hatchback car engine idling, steady low rumble, close mic, dry",
  "negative_prompt": "music, speech, horn, traffic, crowd, reverb, echo, low quality, distortion",
  "type": "loop",
  "duration_s": 8,
  "variations": 3,
  "spatial": "3d",
  "status": "todo"
}
```

| Field | Values |
|---|---|
| `type` | `loop` or `one_shot` |
| `spatial` | `3d` or `2d` |
| `variations` | Number of takes per slot |
| `status` | `todo` runs, `generated` is skipped |

### Speech slot

```json
{
  "id": "npc.bark.greet#sanjay",
  "category": "npc_voice",
  "model": "speech",
  "speech": {
    "text": ["Hello, boss!", "Good morning, ji!"],
    "voice": "Sanjay speaks in a warm, friendly and expressive tone...",
    "seed": 42
  },
  "variations": 1,
  "spatial": "3d",
  "status": "todo"
}
```

The part after `#` in the id is the speaker, so each NPC keeps one voice.

## Prompting tips

These come from real testing with Stable Audio Open.

- **Keep prompts focused.** Words like "busy street" mix in traffic and crowd noise. Ask for the one sound you want.
- **Avoid the word "hum".** It tends to produce a single whistling tone. Use "low rumbling" and "mechanical" instead.
- **Fix whistling and ringing.** Add `high-pitched whine, ringing, whistle, beep, tone` to the negative prompt for engines, then apply a low-pass filter after generation.
- **Do not low-pass** horns, sirens or UI chimes. They need their high frequencies.
- **Test one sound first**, get the prompt right, then copy the pattern to the rest of the batch.
- **Animals, drums and shutters are weak spots.** Always listen before running a full batch.
- Steps above 100 can over-process the audio and add artifacts.

### Low-pass filter for engine sounds

```bash
ffmpeg -i in.wav -af "lowpass=f=6000" out.wav
```

Run it on every engine file in a folder:

```bash
find output/candidates -path "*engine*" -name "*.wav" ! -name "*_lp.wav" | while read f; do ffmpeg -y -i "$f" -af "lowpass=f=6000" "${f%.wav}_lp.wav"; done
```

## Naming convention

Slot ids use dots as separators, and the first part decides the output folder.

| Prefix | Content |
|---|---|
| `veh.` | Vehicles: engines, horns, sirens |
| `amb.` | Ambience loops |
| `act.` and `sport.` | Activity and sports interaction sounds |
| `shop.` | Shop sounds |
| `sea.` | Sea and harbour sounds |
| `misc.` | Birds, bells, train horn and similar |
| `ui.` | UI and system sounds |
| `npc.` | NPC voice lines |

## Troubleshooting

| Problem | Fix |
|---|---|
| Generation is very slow | Check Shared GPU memory in Task Manager. Restart the app and use one tab only. Lower Steps to 70. |
| High-pitched whistle in a sound | Add whistle and ringing terms to the negative prompt, lower Steps to 100 or less, apply a low-pass filter. |
| Category error in a batch | Use a category name from the dropdown list above. |
| `pip freeze` fails with `NotADirectoryError` | An editable package points to a folder that no longer exists. Uninstall it, or use `pip list --format=freeze`. |
| Voice missing in Character voice | Put the `.wav` in `voices/` and press **Refresh voices**. |


## Licenses

### This repository

The code in this repository is the property of its author. If you make the repo public, add a `LICENSE` file (MIT is a common choice). Until then, no license is granted to others.

### Models used

This project only downloads and runs third-party models. Their licenses apply to you as the user.

| Model | License | Commercial use |
|---|---|---|
| Stable Audio Open | Stability AI Community License | Free for research and non-commercial use. Commercial use is free only for individuals or organizations with up to $1M annual revenue. Above that you need an enterprise license from Stability AI. |
| Parler-TTS (Mini v1) | Apache 2.0 | Yes |
| Chatterbox | MIT | Yes |

**Stable Audio Open is the one to check.** If you use its output in a commercial product such as a game, read the license on the model page you accepted (https://huggingface.co/stabilityai/stable-audio-open-1.0) and Stability AI's license page (https://stability.ai/license). Licenses can change, so check them before you ship.

This is not legal advice. For a company project, ask your legal team before release.