import json
import os
import random
import subprocess
import threading
from pathlib import Path

import config


class WorkerClient:
    """Starts a generation worker in its own venv on first use and keeps it running, so the
    model loads once. Jobs go in as one JSON line; the answer is one '@@RESULT {json}' line."""

    def __init__(self, python_exe: Path, script: Path, name: str):
        self.python_exe = Path(python_exe)
        self.script = Path(script)
        self.name = name
        self.proc = None
        self.lock = threading.Lock()

    def _start(self):
        if not self.python_exe.exists():
            raise RuntimeError(f"{self.name} venv not found: {self.python_exe}")

        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen(
            [str(self.python_exe), "-u", str(self.script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        ready = self._read_result()
        if not ready.get("ready"):
            raise RuntimeError(f"{self.name} worker failed to start: {ready}")

    def _read_result(self) -> dict:
        for line in self.proc.stdout:
            if line.startswith("@@RESULT "):
                return json.loads(line[len("@@RESULT "):])
        raise RuntimeError(f"{self.name} worker stopped. Check the console for its error.")

    def run(self, job: dict) -> dict:
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()

            if int(job.get("seed", -1)) < 0:
                job["seed"] = random.randint(0, 2**31 - 1)

            self.proc.stdin.write(json.dumps(job, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()

            result = self._read_result()
            if not result.get("ok"):
                raise RuntimeError(result.get("error", f"unknown {self.name} error"))
            return result

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def speech_client() -> WorkerClient:
    return WorkerClient(config.SPEECH_PYTHON, config.SPEECH_WORKER, "Speech (Parler)")


def voice_client() -> WorkerClient:
    return WorkerClient(config.VOICE_PYTHON, config.VOICE_WORKER, "Voice (Chatterbox)")