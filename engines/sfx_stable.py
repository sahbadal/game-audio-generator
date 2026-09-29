import random

import numpy as np
import torch

REPO = "stabilityai/stable-audio-open-1.0"
MAX_PER_CALL = 4  # waveforms per call; more at once costs VRAM for little speed gain


class SfxEngine:
    """Stable Audio Open. Loaded on first use and kept in VRAM."""

    def __init__(self):
        self.pipe = None

    def _load(self):
        if self.pipe is not None:
            return
        from diffusers import StableAudioPipeline

        self.pipe = StableAudioPipeline.from_pretrained(REPO, torch_dtype=torch.float16).to("cuda")

    @property
    def sample_rate(self) -> int:
        self._load()
        return self.pipe.vae.sampling_rate

    def generate(self, prompt: str, negative: str, seconds: float, count: int,
                 steps: int, seed: int) -> list:
        """Returns a list of (audio [samples, channels] float32, seed)."""
        self._load()
        if seed < 0:
            seed = random.randint(0, 2**31 - 1)

        results = []
        remaining = count
        batch = 0

        while remaining > 0:
            n = min(MAX_PER_CALL, remaining)
            batch_seed = seed + batch
            generator = torch.Generator("cuda").manual_seed(batch_seed)

            audios = self.pipe(
                prompt,
                negative_prompt=negative or None,
                num_inference_steps=steps,
                audio_end_in_s=float(seconds),
                num_waveforms_per_prompt=n,
                generator=generator,
            ).audios

            for a in audios:
                results.append((a.T.float().cpu().numpy().astype(np.float32), batch_seed))

            remaining -= n
            batch += 1

        return results
