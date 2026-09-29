import numpy as np
import pyloudnorm as pyln

PEAK_CEILING = 0.891  # -1 dBFS


def to_mono(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 1 else x.mean(axis=1)


def trim_silence(x: np.ndarray, sr: int, threshold_db: float = -50.0, pad_ms: float = 20.0) -> np.ndarray:
    level = np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=1)
    threshold = 10 ** (threshold_db / 20.0)
    loud = np.where(level > threshold)[0]
    if loud.size == 0:
        return x

    pad = int(sr * pad_ms / 1000.0)
    start = max(0, loud[0] - pad)
    end = min(len(x), loud[-1] + pad)
    return x[start:end]


def fade(x: np.ndarray, sr: int, in_ms: float = 5.0, out_ms: float = 30.0) -> np.ndarray:
    x = x.copy()
    n_in = min(len(x) // 2, int(sr * in_ms / 1000.0))
    n_out = min(len(x) // 2, int(sr * out_ms / 1000.0))

    if n_in > 0:
        ramp = np.linspace(0.0, 1.0, n_in)
        x[:n_in] *= ramp if x.ndim == 1 else ramp[:, None]
    if n_out > 0:
        ramp = np.linspace(1.0, 0.0, n_out)
        x[-n_out:] *= ramp if x.ndim == 1 else ramp[:, None]
    return x


def loop_crossfade(x: np.ndarray, sr: int, ms: float = 400.0) -> np.ndarray:
    """Blend the tail into the head so the file loops without a click."""
    n = int(sr * ms / 1000.0)
    if len(x) <= 2 * n:
        return x

    body = x[:-n].copy()
    tail = x[-n:]
    fade_in = np.linspace(0.0, 1.0, n)
    fade_out = 1.0 - fade_in
    if x.ndim > 1:
        fade_in = fade_in[:, None]
        fade_out = fade_out[:, None]

    body[:n] = body[:n] * fade_in + tail * fade_out
    return body


def normalize(x: np.ndarray, sr: int, target_lufs: float) -> np.ndarray:
    try:
        meter = pyln.Meter(sr)
        loudness = meter.integrated_loudness(x)
        if np.isfinite(loudness):
            x = pyln.normalize.loudness(x, loudness, target_lufs)
    except ValueError:
        # Clip shorter than the loudness window: fall back to peak level.
        peak = np.abs(x).max()
        if peak > 0:
            x = x * (0.5 / peak)

    peak = np.abs(x).max()
    if peak > PEAK_CEILING:
        x = x * (PEAK_CEILING / peak)
    return x.astype(np.float32)


def process(x: np.ndarray, sr: int, target_lufs: float, loop: bool, mono: bool) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if mono:
        x = to_mono(x)

    if loop:
        x = loop_crossfade(x, sr)
    else:
        x = trim_silence(x, sr)
        x = fade(x, sr)

    return normalize(x, sr, target_lufs)
