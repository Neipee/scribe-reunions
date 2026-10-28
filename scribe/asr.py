"""Chargement du modèle Nemotron ASR (Transformers, CPU) et transcription."""

from __future__ import annotations

import gc
import io
import os
import threading
import warnings
import wave
from pathlib import Path
from typing import Callable

import av

import numpy as np

from . import config

# Avertissement générique de Transformers (longueur max par défaut), sans effet ici.
warnings.filterwarnings("ignore", message="Using the model-agnostic default `max_length`")
av.logging.set_level(av.logging.ERROR)  # pas de bruit FFmpeg dans la console


class AudioError(ValueError):
    """Fichier audio illisible ou inutilisable."""


def read_wav(data: bytes) -> np.ndarray:
    """WAV PCM 16 bits (mono ou stéréo, toute fréquence) -> float32 mono 16 kHz."""
    try:
        with wave.open(io.BytesIO(data)) as wav:
            channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as exc:
        raise AudioError(f"Fichier WAV illisible : {exc}") from exc
    if width != 2:
        raise AudioError("Seul le WAV PCM 16 bits est accepté.")
    if not 8_000 <= rate <= 192_000 or not 1 <= channels <= 8:
        raise AudioError("En-tête WAV invalide (fréquence ou nombre de canaux).")
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != config.SAMPLE_RATE and len(audio):
        duration = len(audio) / rate
        positions = np.linspace(0, len(audio) - 1, int(duration * config.SAMPLE_RATE))
        audio = np.interp(positions, np.arange(len(audio)), audio).astype(np.float32)
    return audio


# Conteneurs acceptés à l'import (noms FFmpeg). Tout le reste (listes de lecture HLS, concat,
# images…) est refusé, même si l'extension du fichier est trompeuse.
IMPORT_FORMATS = {"mp3", "wav", "mov,mp4,m4a,3gp,3g2,mj2", "ogg", "flac", "matroska,webm",
                  "asf", "aac", "aiff", "amr", "caf"}
# Seul le protocole « file » est autorisé : un fichier importé ne peut pas déclencher d'accès réseau.
_OPEN_OPTIONS = {"protocol_whitelist": "file"}


def _open_audio(path: Path):
    """Ouvre un fichier audio/vidéo avec PyAV ; renvoie (conteneur, flux audio)."""
    try:
        container = av.open(str(path), mode="r", options=_OPEN_OPTIONS)
    except (av.error.FFmpegError, OSError, ValueError) as exc:
        raise AudioError("Format non pris en charge, ou fichier corrompu.") from exc
    try:
        if container.format.name not in IMPORT_FORMATS:
            raise AudioError("Format non pris en charge.")
        if not container.streams.audio:
            raise AudioError("Ce fichier ne contient pas de piste audio.")
    except BaseException:
        container.close()
        raise
    return container, container.streams.audio[0]


def probe_audio(path: Path) -> dict:
    """Vérifie rapidement qu'un fichier est lisible ; renvoie sa durée (None si inconnue)."""
    container, _ = _open_audio(path)
    with container:
        duration = container.duration / av.time_base if container.duration else None
        return {"duration": duration, "container": container.format.name}


def decode_audio(path: Path, max_seconds: float,
                 on_progress: Callable[[float], None] | None = None) -> np.ndarray:
    """Décode un fichier audio (ou l'audio d'une vidéo) -> int16 mono 16 kHz.

    L'int16 divise par deux la mémoire d'un long fichier ; Transcriber convertit segment par segment.
    """
    container, stream = _open_audio(path)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=config.SAMPLE_RATE)
    raw, samples = bytearray(), 0

    def collect(frames) -> None:
        nonlocal samples
        for frame in frames:
            chunk = frame.to_ndarray().reshape(-1)
            raw.extend(chunk.tobytes())
            samples += len(chunk)
        if samples > max_seconds * config.SAMPLE_RATE:
            raise AudioError(f"Fichier trop long (maximum {max_seconds / 3600:g} h).")
        if on_progress:
            on_progress(samples / config.SAMPLE_RATE)

    try:
        with container:
            for frame in container.decode(stream):
                collect(resampler.resample(frame))
            collect(resampler.resample(None))
    except (av.error.FFmpegError, OSError, ValueError) as exc:
        if isinstance(exc, AudioError):
            raise
        raise AudioError("Fichier audio corrompu ou illisible.") from exc
    return np.frombuffer(raw, dtype="<i2")


def split_segments(audio: np.ndarray, sr: int, target_s: int, search_s: int = 5,
                   window_s: float = 0.1) -> list[tuple[int, int]]:
    """Découpe en segments d'au plus target_s secondes, en coupant sur le passage
    le plus silencieux des search_s dernières secondes (pour ne pas couper un mot)."""
    n, start, segments = len(audio), 0, []
    win = int(window_s * sr)
    while n - start > target_s * sr:
        lo, hi = start + (target_s - search_s) * sr, start + target_s * sr
        frames = audio[lo:hi][: (hi - lo) // win * win].reshape(-1, win).astype(np.float32)
        cut = lo + int((frames ** 2).mean(axis=1).argmin()) * win + win // 2
        segments.append((start, cut))
        start = cut
    segments.append((start, n))
    return segments


def is_memory_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return isinstance(exc, MemoryError) or "out of memory" in text or "not enough memory" in text \
        or "can't allocate" in text or "defaultcpuallocator" in text


class Transcriber:
    def __init__(self) -> None:
        self.model = None
        self.processor = None
        self.path: Path | None = None
        self.lock = threading.Lock()  # une seule transcription / un seul chargement à la fois

    @property
    def ready(self) -> bool:
        return self.model is not None

    def unload(self) -> None:
        self.model = self.processor = self.path = None
        gc.collect()

    def load(self, path: Path) -> None:
        import torch
        from transformers import AutoModelForRNNT, AutoProcessor

        with self.lock:
            self.unload()  # libère l'ancienne révision avant de charger la nouvelle
            torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
            # local_files_only : garantit qu'aucun appel réseau n'est fait au chargement.
            self.processor = AutoProcessor.from_pretrained(path, local_files_only=True)
            self.model = AutoModelForRNNT.from_pretrained(path, local_files_only=True).eval()
            self.path = path

    def transcribe(self, audio: np.ndarray, language: str = config.LANGUAGE,
                   on_progress: Callable[[int, int], None] | None = None) -> str:
        import torch

        with self.lock:
            if self.model is None:
                raise RuntimeError("Modèle non chargé.")
            sr = config.SAMPLE_RATE
            segments = [s for s in split_segments(audio, sr, config.SEGMENT_SECONDS)
                        if s[1] - s[0] > sr // 10]
            texts = []
            for i, (a, b) in enumerate(segments, start=1):
                chunk = audio[a:b]
                if chunk.dtype == np.int16:  # audio importé : conversion segment par segment
                    chunk = chunk.astype(np.float32) / 32768.0
                inputs = self.processor(chunk, sampling_rate=sr, language=language,
                                        return_tensors="pt")
                inputs = inputs.to(self.model.device, dtype=self.model.dtype)
                with torch.inference_mode():
                    out = self.model.generate(**inputs, return_dict_in_generate=True)
                text = self.processor.decode(out.sequences, skip_special_tokens=True)
                if isinstance(text, list):
                    text = " ".join(text)
                texts.append(text.strip())
                if on_progress:
                    on_progress(i, len(segments))
            return " ".join(" ".join(texts).split())
