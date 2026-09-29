"""AudioGen — local sound generation for the game.

Run from the SFX venv:
    source venv_sfx/Scripts/activate
    python app.py
Then open http://127.0.0.1:7860
"""

import shutil
import uuid
from pathlib import Path

import gradio as gr
import soundfile as sf

import config
from engines.sfx_stable import SfxEngine
from engines.speech_client import speech_client, voice_client
from pipeline import library, manifest, post

MAX_PREVIEW = 8

sfx = SfxEngine()
speech = speech_client()
voice = voice_client()


# ---------- helpers ----------

def _previews(paths: list) -> list:
    updates = []
    for i in range(MAX_PREVIEW):
        if i < len(paths):
            updates.append(gr.update(value=paths[i], visible=True, label=Path(paths[i]).name))
        else:
            updates.append(gr.update(value=None, visible=False))
    return updates


def _loudness(category: str) -> float:
    return config.LOUDNESS.get(category, config.DEFAULT_LOUDNESS)


def _run_sfx(slot_id, category, prompt, negative, seconds, count, steps, seed, loop, mono) -> list:
    slot_id = library.validate_id(slot_id)
    if not prompt.strip():
        raise ValueError("Prompt is empty.")

    seconds = min(float(seconds), config.SFX_MAX_SECONDS)
    takes = sfx.generate(prompt, negative, seconds, int(count), int(steps), int(seed))
    sr = sfx.sample_rate

    paths = []
    for audio, take_seed in takes:
        audio = post.process(audio, sr, _loudness(category), loop=bool(loop), mono=bool(mono))
        path = library.save_candidate(slot_id, audio, sr, {
            "model": "stable-audio-open", "category": category, "prompt": prompt,
            "negative": negative, "seconds": seconds, "steps": int(steps), "seed": take_seed,
            "loop": bool(loop), "mono": bool(mono)})
        paths.append(str(path))
    return paths


def _run_speech(slot_id, category, lines, voice, count, seed) -> list:
    slot_id = library.validate_id(slot_id)
    texts = [t.strip() for t in lines.splitlines() if t.strip()]
    if not texts:
        raise ValueError("Add at least one line of text.")
    if not voice.strip():
        raise ValueError("Describe the voice.")

    tmp = config.TEMP_DIR / uuid.uuid4().hex
    try:
        result = speech.run({"texts": texts, "voice": voice, "count": int(count),
                             "seed": int(seed), "out_dir": str(tmp)})
        sr = result["sample_rate"]

        paths = []
        for item in result["files"]:
            audio, _ = sf.read(item["path"], dtype="float32")
            audio = post.process(audio, sr, _loudness(category), loop=False, mono=True)
            path = library.save_candidate(slot_id, audio, sr, {
                "model": "indic-parler-tts", "category": category, "text": item["text"],
                "voice": voice, "seed": item["seed"]})
            paths.append(str(path))
        return paths
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _voices() -> list:
    config.VOICES_DIR.mkdir(exist_ok=True)
    return sorted(p.name for p in config.VOICES_DIR.glob("*.wav"))


def _run_voice(slot_id, category, lines, ref_name, exaggeration, cfg_weight, count, seed,
               speed=1.0, pause_scale=1.0) -> list:
    slot_id = library.validate_id(slot_id)
    texts = [t.strip() for t in lines.splitlines() if t.strip()]
    if not texts:
        raise ValueError("Add at least one line of text.")
    if not ref_name:
        raise ValueError("Pick a reference voice from voices/.")

    ref = config.VOICES_DIR / ref_name
    tmp = config.TEMP_DIR / uuid.uuid4().hex
    try:
        result = voice.run({"texts": texts, "ref": str(ref), "exaggeration": float(exaggeration),
                            "cfg_weight": float(cfg_weight), "speed": float(speed),
                            "pause_scale": float(pause_scale),
                            "count": int(count), "seed": int(seed), "out_dir": str(tmp)})
        sr = result["sample_rate"]

        paths = []
        for item in result["files"]:
            audio, _ = sf.read(item["path"], dtype="float32")
            audio = post.process(audio, sr, _loudness(category), loop=False, mono=True)
            path = library.save_candidate(slot_id, audio, sr, {
                "model": "chatterbox", "category": category, "text": item["text"],
                "ref": ref_name, "exaggeration": float(exaggeration),
                "cfg_weight": float(cfg_weight), "speed": float(speed), "seed": item["seed"]})
            paths.append(str(path))
        return paths
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- tab handlers ----------

def on_sfx(slot_id, category, prompt, negative, seconds, count, steps, seed, loop, mono):
    try:
        paths = _run_sfx(slot_id, category, prompt, negative, seconds, count, steps, seed, loop, mono)
        return [f"Saved {len(paths)} take(s) to {library.candidate_dir(slot_id.strip().lower())}"] + _previews(paths)
    except Exception as error:
        return [f"**Error:** {error}"] + _previews([])


def on_speech(slot_id, category, lines, voice, count, seed):
    try:
        paths = _run_speech(slot_id, category, lines, voice, count, seed)
        return [f"Saved {len(paths)} take(s) to {library.candidate_dir(slot_id.strip().lower())}"] + _previews(paths)
    except Exception as error:
        return [f"**Error:** {error}"] + _previews([])


def on_voice(slot_id, category, lines, ref_name, exaggeration, cfg_weight, speed, pause_scale, count, seed):
    try:
        paths = _run_voice(slot_id, category, lines, ref_name, exaggeration, cfg_weight, count, seed,
                           speed, pause_scale)
        return [f"Saved {len(paths)} take(s) to {library.candidate_dir(slot_id.strip().lower())}"] + _previews(paths)
    except Exception as error:
        return [f"**Error:** {error}"] + _previews([])


def on_refresh_slots():
    return gr.update(choices=library.list_slots(), value=None)


def on_pick_slot(slot_id):
    if not slot_id:
        return gr.update(choices=[], value=None), None, ""
    candidates = library.list_candidates(slot_id)
    finals = library.list_finals(slot_id)
    return (gr.update(choices=candidates, value=candidates[0] if candidates else None),
            candidates[0] if candidates else None,
            _finals_text(finals))


def on_pick_candidate(path):
    return path


def on_approve(slot_id, path):
    if not slot_id or not path:
        return "Pick a slot and a take first."
    target = library.approve(slot_id, path)
    return f"Approved → {target}\n\n" + _finals_text(library.list_finals(slot_id))


def _finals_text(finals: list) -> str:
    if not finals:
        return "No approved takes yet."
    return "**Approved:**\n" + "\n".join(f"- {Path(f).name}" for f in finals)


def on_batch(manifest_path, only_status, steps, progress=gr.Progress()):
    path = Path(manifest_path)
    if not path.exists():
        return f"Manifest not found: {path}"

    data = manifest.load(path)
    slots = [s for s in data["slots"] if s.get("status", "todo") == only_status]
    if not slots:
        return f"No slots with status '{only_status}'."

    log = []
    for index, slot in enumerate(slots):
        progress(index / len(slots), desc=slot.get("id", "?"))
        try:
            count = int(slot.get("variations", 1)) * config.CANDIDATES_PER_VARIATION
            category = slot.get("category", "world")
            made = 0

            for job in manifest.expand(slot):
                if slot.get("model") == "voice":
                    spec = slot.get("speech", {})
                    made += len(_run_voice(job["id"], category, "\n".join(spec.get("text", [])),
                                           spec.get("ref", ""), spec.get("exaggeration", 0.6),
                                           spec.get("cfg_weight", 0.35), count,
                                           int(spec.get("seed", -1)), spec.get("speed", 1.0),
                                           spec.get("pause_scale", 1.0)))
                elif slot.get("model") == "speech":
                    spec = slot.get("speech", {})
                    made += len(_run_speech(job["id"], category, "\n".join(spec.get("text", [])),
                                            spec.get("voice", ""), count, int(spec.get("seed", -1))))
                else:
                    made += len(_run_sfx(job["id"], category, job.get("prompt", ""),
                                         slot.get("negative_prompt", config.DEFAULT_NEGATIVE),
                                         slot.get("duration_s", 5), count, steps, -1,
                                         loop=slot.get("type") == "loop",
                                         mono=slot.get("spatial", "3d") == "3d"))

            slot["status"] = "generated"
            log.append(f"OK   {slot['id']}: {made} take(s)")
        except Exception as error:
            log.append(f"FAIL {slot.get('id', '?')}: {error}")

        manifest.save(path, data)

    progress(1.0)
    return "\n".join(log)


# ---------- UI ----------

def build() -> gr.Blocks:
    with gr.Blocks(title="AudioGen") as app:
        gr.Markdown("# AudioGen\nGenerate, review and approve game audio. "
                    "Takes land in `output/candidates`, approved files in `output/final`.")

        with gr.Tab("Sound effect"):
            with gr.Row():
                sfx_id = gr.Textbox(label="Slot id", placeholder="veh.auto.engine@idle")
                sfx_cat = gr.Dropdown(config.CATEGORIES, value="vehicle", label="Category")
            sfx_prompt = gr.Textbox(label="Prompt", lines=3,
                                    placeholder="auto rickshaw two-stroke engine idling, busy Mumbai street, close perspective")
            sfx_neg = gr.Textbox(label="Negative prompt", value=config.DEFAULT_NEGATIVE)
            with gr.Row():
                sfx_sec = gr.Slider(1, config.SFX_MAX_SECONDS, value=5, step=0.5, label="Seconds")
                sfx_count = gr.Slider(1, MAX_PREVIEW, value=4, step=1, label="Takes")
                sfx_steps = gr.Slider(25, 150, value=100, step=5, label="Steps (quality)")
                sfx_seed = gr.Number(value=-1, label="Seed (-1 = random)", precision=0)
            with gr.Row():
                sfx_loop = gr.Checkbox(value=False, label="Loop (crossfade ends)")
                sfx_mono = gr.Checkbox(value=True, label="Mono (3D sounds)")
            sfx_go = gr.Button("Generate", variant="primary")
            sfx_status = gr.Markdown()
            sfx_out = [gr.Audio(type="filepath", visible=False, interactive=False) for _ in range(MAX_PREVIEW)]
            sfx_go.click(on_sfx,
                         [sfx_id, sfx_cat, sfx_prompt, sfx_neg, sfx_sec, sfx_count, sfx_steps, sfx_seed, sfx_loop, sfx_mono],
                         [sfx_status] + sfx_out)

        with gr.Tab("Speech"):
            with gr.Row():
                sp_id = gr.Textbox(label="Slot id", placeholder="npc.vendor.call#male")
                sp_cat = gr.Dropdown(config.CATEGORIES, value="npc_voice", label="Category")
            sp_lines = gr.Textbox(label="Lines (one per line; Hindi, Marathi or English)", lines=4,
                                  placeholder="चाय, गरम चाय!\nकटिंग चाय!")
            sp_voice = gr.Textbox(label="Voice description", lines=2,
                                  value="A middle-aged male street vendor calls out loudly and energetically, "
                                        "outdoors, moderate speed, slight background noise.")
            with gr.Row():
                sp_count = gr.Slider(1, 4, value=2, step=1, label="Takes per line")
                sp_seed = gr.Number(value=-1, label="Seed (-1 = random)", precision=0)
            sp_go = gr.Button("Generate", variant="primary")
            sp_status = gr.Markdown()
            sp_out = [gr.Audio(type="filepath", visible=False, interactive=False) for _ in range(MAX_PREVIEW)]
            sp_go.click(on_speech, [sp_id, sp_cat, sp_lines, sp_voice, sp_count, sp_seed], [sp_status] + sp_out)

        with gr.Tab("Character voice"):
            gr.Markdown("Lines spoken in a character's voice (Chatterbox). Put a 10–15 s reference "
                        "clip in `voices/` (e.g. `sofia_ref.wav`, made with `make_ref.py`).")
            with gr.Row():
                cv_id = gr.Textbox(label="Slot id", placeholder="story.sofia.s1_01_greet")
                cv_cat = gr.Dropdown(config.CATEGORIES, value="dialogue", label="Category")
            with gr.Row():
                cv_ref = gr.Dropdown(choices=_voices(), label="Reference voice (voices/)")
                cv_ref_refresh = gr.Button("Refresh voices")
            cv_lines = gr.Textbox(label="Lines (one per line). Write normally — she pauses after . ? ! and ...", lines=4,
                                  placeholder="Excuse me? Hi. Sorry, I don't mean to bother you.")
            with gr.Row():
                cv_exag = gr.Slider(0.25, 1.5, value=0.45, step=0.05, label="Expressiveness")
                cv_cfg = gr.Slider(0.1, 1.0, value=0.25, step=0.05, label="Pacing (lower = slower, more natural)")
                cv_speed = gr.Slider(0.75, 1.1, value=0.85, step=0.01, label="Speed (pitch kept)")
                cv_pause = gr.Slider(0.0, 2.0, value=1.0, step=0.1, label="Pause length between sentences")
                cv_count = gr.Slider(1, 4, value=2, step=1, label="Takes per line")
                cv_seed = gr.Number(value=42, label="Seed (-1 = random)", precision=0)
            cv_go = gr.Button("Generate", variant="primary")
            cv_status = gr.Markdown()
            cv_out = [gr.Audio(type="filepath", visible=False, interactive=False) for _ in range(MAX_PREVIEW)]
            cv_ref_refresh.click(lambda: gr.update(choices=_voices()), None, cv_ref)
            cv_go.click(on_voice, [cv_id, cv_cat, cv_lines, cv_ref, cv_exag, cv_cfg, cv_speed, cv_pause, cv_count, cv_seed],
                        [cv_status] + cv_out)

        with gr.Tab("Review"):
            with gr.Row():
                rv_slot = gr.Dropdown(choices=library.list_slots(), label="Slot")
                rv_refresh = gr.Button("Refresh")
            rv_take = gr.Dropdown(choices=[], label="Take")
            rv_audio = gr.Audio(type="filepath", interactive=False, label="Preview")
            rv_approve = gr.Button("Approve this take", variant="primary")
            rv_status = gr.Markdown()
            rv_refresh.click(on_refresh_slots, None, rv_slot)
            rv_slot.change(on_pick_slot, rv_slot, [rv_take, rv_audio, rv_status])
            rv_take.change(on_pick_candidate, rv_take, rv_audio)
            rv_approve.click(on_approve, [rv_slot, rv_take], rv_status)

        with gr.Tab("Batch (manifest)"):
            bt_path = gr.Textbox(label="Manifest path", value=str(config.DEFAULT_MANIFEST))
            with gr.Row():
                bt_status = gr.Dropdown(["todo", "generated"], value="todo", label="Run slots with status")
                bt_steps = gr.Slider(25, 150, value=100, step=5, label="Steps (SFX quality)")
            bt_go = gr.Button("Run batch", variant="primary")
            bt_log = gr.Textbox(label="Log", lines=16)
            bt_go.click(on_batch, [bt_path, bt_status, bt_steps], bt_log)

    return app


if __name__ == "__main__":
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    try:
        build().queue().launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
    finally:
        speech.close()
        voice.close()