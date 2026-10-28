"""Mesure : temps de chargement, temps de transcription, mémoire, WER.

    python scripts/bench.py tests/samples/reunion_fr.wav tests/samples/reunion_fr.txt

Utilise le modèle déjà téléchargé dans models/ (aucun appel réseau).
"""

import json
import re
import sys
import threading
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil  # noqa: E402

from scribe.asr import Transcriber, read_wav  # noqa: E402
from scribe.model_manager import ModelManager  # noqa: E402


def words(text: str) -> list[str]:
    """Normalisation simple : minuscules, sans ponctuation ; accents conservés."""
    text = unicodedata.normalize("NFC", text.lower()).replace("'", "' ").replace("-", " ")
    return re.findall(r"[\w']+", text)


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = words(reference), words(hypothesis)
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return row[-1] / max(1, len(ref))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    wav_path = Path(sys.argv[1])
    reference = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else None
    path = ModelManager().local_path()
    if path is None:
        sys.exit("Modèle absent : lancez d'abord l'application (python run.py) pour le télécharger.")

    proc = psutil.Process()
    peak = {"rss": proc.memory_info().rss}
    stop = threading.Event()

    def sample() -> None:
        while not stop.wait(0.2):
            peak["rss"] = max(peak["rss"], proc.memory_info().rss)

    threading.Thread(target=sample, daemon=True).start()
    rss_start = proc.memory_info().rss
    t0 = time.perf_counter()
    transcriber = Transcriber()
    transcriber.load(path)
    load_s = time.perf_counter() - t0
    rss_loaded = proc.memory_info().rss

    audio = read_wav(wav_path.read_bytes())
    runs = []
    for _ in range(2):  # 1er passage = « à froid », 2e = régime établi
        t0 = time.perf_counter()
        text = transcriber.transcribe(audio)
        runs.append(time.perf_counter() - t0)
    stop.set()

    seconds = len(audio) / 16000
    result = {
        "model_path": str(path),
        "audio_seconds": round(seconds, 1),
        "load_seconds": round(load_s, 1),
        "transcribe_seconds": [round(r, 1) for r in runs],
        "rtf": [round(r / seconds, 3) for r in runs],
        "rss_mb": {"start": rss_start >> 20, "after_load": rss_loaded >> 20, "peak": peak["rss"] >> 20},
        "private_mb_end": proc.memory_full_info().private >> 20 if hasattr(proc.memory_full_info(), "private") else None,
        "wer": round(wer(reference, text), 4) if reference else None,
        "text": text,
    }
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
