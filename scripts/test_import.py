"""Tests réels de l'import de fichiers audio.

Les fichiers de test sont générés à la volée dans un dossier temporaire à partir de
tests/samples/reunion_fr.wav (voir scripts/make_sample.ps1) : rien n'est ajouté au dépôt.

  Partie A (serveur réel déjà lancé, modèle chargé) :
      .venv\\Scripts\\python scripts\\test_import.py http://127.0.0.1:8765
  Partie B (serveur de test local, sans modèle, limite de 1 Mo : refus et sécurité) :
      .venv\\Scripts\\python scripts\\test_import.py --refus

Les fichiers importés par la partie A sont enregistrés dans data/ comme tout import.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

import av

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "tests" / "samples" / "reunion_fr.wav"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'OK' if ok else 'ÉCHEC'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    return ok


# --- Génération des fichiers de test -----------------------------------------------------------
def encode(dst: Path, codec: str, fmt: str | None = None, rate: int = 16000, layout: str = "mono",
           with_video: bool = False) -> Path:
    with av.open(str(SAMPLE)) as src, av.open(str(dst), "w", format=fmt) as out:
        audio = out.add_stream(codec, rate=rate)
        audio.layout = layout
        if codec == "wmav2":
            audio.bit_rate = 128_000  # l'encodeur WMA refuse de s'ouvrir sans débit
        video = None
        if with_video:
            video = out.add_stream("libx264", rate=2)
            video.width, video.height, video.pix_fmt = 64, 64, "yuv420p"
        resampler = av.AudioResampler(format="fltp" if codec in {"aac", "libopus", "wmav2", "flac"}
                                      else "s16p", layout=layout, rate=rate)
        for frame in src.decode(audio=0):
            for f in resampler.resample(frame):
                f.pts = None
                out.mux(audio.encode(f))
        out.mux(audio.encode(None))
        if video:
            for i in range(150):  # 75 s à 2 images/s
                img = av.VideoFrame(64, 64, "yuv420p")
                img.pts = i
                out.mux(video.encode(img))
            out.mux(video.encode(None))
    return dst


def make_files(folder: Path) -> dict[str, Path]:
    specs = {
        "wav": lambda p: p.write_bytes(SAMPLE.read_bytes()),
        "wav-44k-stereo": lambda p: encode(p, "pcm_s16le", "wav", 44100, "stereo"),
        "mp3": lambda p: encode(p, "libmp3lame", None, 44100, "stereo"),
        "m4a": lambda p: encode(p, "aac", "ipod", 44100, "stereo"),
        "aac": lambda p: encode(p, "aac", "adts", 44100, "stereo"),
        "ogg": lambda p: encode(p, "libopus", None, 48000, "stereo"),
        "opus": lambda p: encode(p, "libopus", "ogg", 48000, "mono"),
        "flac": lambda p: encode(p, "flac", None, 16000, "mono"),
        "webm": lambda p: encode(p, "libopus", "webm", 48000, "mono"),
        "wma": lambda p: encode(p, "wmav2", "asf", 44100, "stereo"),
        "mp4": lambda p: encode(p, "aac", "mp4", 44100, "stereo", with_video=True),
    }
    files = {}
    for ext, build in specs.items():
        path = folder / f"reunion.{ext.split('-')[0]}" if "-" not in ext else folder / f"{ext}.wav"
        try:
            build(path)
            files[ext] = path
        except Exception as exc:  # encodeur absent : on le dit, on ne l'invente pas
            print(f"[NON TESTÉ] {ext} : encodeur indisponible ({exc})")
    return files


# --- Client HTTP minimal -----------------------------------------------------------------------
class Client:
    def __init__(self, base: str) -> None:
        self.parts = urlsplit(base)

    def request(self, method, path, body=None, headers=None, chunked=False):
        conn = http.client.HTTPConnection(self.parts.hostname, self.parts.port, timeout=600)
        try:
            conn.request(method, path, body=body, headers=headers or {}, encode_chunked=chunked)
            res = conn.getresponse()
            raw = res.read()
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"raw": raw.decode("utf-8", "replace")}
            return res.status, data
        finally:
            conn.close()

    def upload(self, path: Path | None, name: str | None = None, data: bytes | None = None,
               extra: dict | None = None, query: str = ""):
        payload = data if data is not None else path.read_bytes()
        headers = {"X-Filename": quote(name or path.name), "Content-Type": "application/octet-stream",
                   "Content-Length": str(len(payload)), **(extra or {})}
        return self.request("POST", "/api/import" + query, body=payload, headers=headers)

    def wait(self, job_id: str, timeout: float = 3600):
        start = time.time()
        while time.time() - start < timeout:
            status, job = self.request("GET", "/api/jobs/" + job_id)
            if status != 200 or job["status"] in ("done", "error"):
                return job
            time.sleep(1)
        raise TimeoutError(job_id)


def words(text: str) -> list[str]:
    """Mots sans ponctuation ni casse : les formats avec perte changent parfois un « . » en « , »."""
    return re.findall(r"\w+", text.lower())


# --- Partie A : serveur réel ---------------------------------------------------------------------
def part_a(base: str) -> None:
    client = Client(base)
    status, st = client.request("GET", "/api/status")
    if st.get("phase") != "ready":
        sys.exit(f"Le modèle n'est pas prêt ({st.get('message')}).")
    print("Limites :", st["import"]["max_bytes"] // 2**20, "Mo,", st["import"]["max_seconds"] / 3600, "h")

    folder = Path(tempfile.mkdtemp(prefix="scribe-test-"))
    print("Fichiers de test dans", folder)
    files = make_files(folder)

    reference = None
    rows = []
    for key, path in files.items():
        t0 = time.perf_counter()
        status, body = client.upload(path)
        if status != 200:
            check(f"import {key}", False, f"HTTP {status} {body}")
            continue
        job = client.wait(body["job_id"])
        total = time.perf_counter() - t0
        if job["status"] != "done":
            check(f"import {key}", False, job.get("error", "?"))
            continue
        if key == "wav":
            reference = job["text"]
        same = reference is not None and job["text"] == reference
        rows.append((key, path.stat().st_size, body["audio_seconds"], job["meta"]["audio_seconds"],
                     total, same, job["text"]))
    print("\nformat | taille | durée (sonde) | durée (décodée) | temps total | texte = WAV ?")
    for key, size, probe, dec, total, same, _ in rows:
        print(f"{key:15s} | {size / 1024:8.0f} Ko | {probe} s | {dec} s | {total:5.1f} s | {'oui' if same else 'NON'}")
    for key, *_, same, text in rows:
        if key != "wav" and reference:
            ref, got = words(reference), words(text)
            common = sum(a == b for a, b in zip(ref, got))
            check(f"mots identiques au WAV : {key}", ref == got,
                  ("texte strictement identique" if same else "mêmes mots, ponctuation/majuscules différentes")
                  if ref == got else f"{common}/{len(ref)} mots identiques")
    if reference:
        print("\nTexte WAV (import) :", reference[:200], "…")

    # Dossier d'archive : original + transcript + meta
    status, job = client.request("GET", "/api/jobs/" + body["job_id"])
    check("archive dans data/", (ROOT / "data" / job["folder"] / job["meta"]["audio_file"]).is_file()
          and (ROOT / "data" / job["folder"] / "transcript.txt").is_file(), job["folder"])

    # Refus
    status, body = client.upload(None, "vide.mp3", data=b"")
    check("fichier vide refusé (400)", status == 400, f"{status} {body.get('detail')}")
    status, body = client.upload(None, "note.mp3", data=b"Ceci n'est pas de l'audio.\n" * 200)
    check("texte renommé .mp3 refusé (415)", status == 415, f"{status} {body.get('detail')}")
    status, body = client.upload(None, "fichier.xyz", data=b"abc")
    check("extension inconnue refusée (415)", status == 415, f"{status} {body.get('detail')}")
    status, body = client.upload(None, "tronque.mp3", data=files["mp3"].read_bytes()[:20000])
    check("mp3 tronqué : pas de plantage", status in (200, 400, 415), f"{status}")
    if status == 200:
        job = client.wait(body["job_id"])
        print("   mp3 tronqué ->", job["status"], job.get("error") or job["text"][:60])
    # Fichier dont le contenu est du WAV mais dont l'extension est .mp3 : accepté (contenu détecté)
    status, body = client.upload(files["wav"], "wav-deguise.mp3")
    check("WAV nommé .mp3 : contenu détecté", status == 200, f"{status}")
    if status == 200:
        client.wait(body["job_id"])

    # Deux imports simultanés : le second est refusé
    status1, body1 = client.upload(files["wav"])
    status2, body2 = client.upload(files["wav"])
    check("deux imports simultanés : le second refusé (429)", status1 == 200 and status2 == 429,
          f"{status1} puis {status2} {body2.get('detail')}")
    if status1 == 200:
        client.wait(body1["job_id"])
    # /api/transcribe pendant un import
    status1, body1 = client.upload(files["wav"])
    boundary = "x"
    multipart = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
                 "Content-Type: audio/wav\r\n\r\n").encode() + SAMPLE.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    status2, body2 = client.request("POST", "/api/transcribe", body=multipart, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"})
    check("enregistrement refusé pendant un import (429)", status1 == 200 and status2 == 429,
          f"{status1} puis {status2}")
    if status1 == 200:
        client.wait(body1["job_id"])


# --- Partie B : refus et sécurité sur un serveur de test sans modèle ------------------------------
def part_b() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    data_dir = Path(tempfile.mkdtemp(prefix="scribe-test-data-"))
    code = (
        "import sys, uvicorn; sys.path.insert(0, r'%s'); import scribe; "
        "scribe.DATA_DIR = __import__('pathlib').Path(r'%s'); "
        "from scribe import server; server.DATA_DIR = scribe.DATA_DIR; "
        "server._bootstrap = lambda: None; server.transcriber.model = object(); "
        "uvicorn.run(server.app, host='127.0.0.1', port=%d, log_level='warning')" % (ROOT, data_dir, port))
    env = {**os.environ, "SCRIBE_MAX_IMPORT_MB": "1"}
    proc = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT)
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        client = Client(f"http://127.0.0.1:{port}")
        small = b"x" * 1000

        status, body = client.upload(None, "a.mp3", data=b"x" * (2 * 2**20))
        check("trop gros, avec Content-Length : refusé (413)", status == 413, f"{status} {body.get('detail')}")

        def gen():
            for _ in range(3):
                yield b"x" * 2**20
        status, body = client.request("POST", "/api/import", body=gen(), chunked=True, headers={
            "X-Filename": "a.mp3", "Content-Type": "application/octet-stream"})
        check("trop gros, en flux sans Content-Length : refusé (413)", status == 413,
              f"{status} {body.get('detail')}")
        check("aucun reste dans data/ après refus", not any(data_dir.iterdir()), str(list(data_dir.iterdir())))

        status, body = client.upload(None, "a.mp3", data=small, extra={"Host": "evil.example"})
        check("nom d'hôte étranger refusé (403)", status == 403, str(status))
        status, body = client.upload(None, "a.mp3", data=small, extra={"Origin": "http://evil.example"})
        check("origine étrangère refusée (403)", status == 403, str(status))

        hls = b"#EXTM3U\n#EXT-X-TARGETDURATION:5\n#EXTINF:5,\nhttp://127.0.0.1:9/x.ts\n#EXT-X-ENDLIST\n"
        status, body = client.upload(None, "liste.mp3", data=hls)
        check("liste HLS renommée .mp3 refusée sans accès réseau", status == 415, f"{status} {body.get('detail')}")

        wav = SAMPLE.read_bytes()[:900_000]  # < 1 Mo (limite du serveur de test)
        status, body = client.upload(None, "../../evil/..\\..\\x.wav", data=wav)
        sys.path.insert(0, str(ROOT))
        from scribe.server import _safe_name
        names = [_safe_name(n) for n in ("../../evil/..\\..\\x.wav", "C:\\Windows\\a.mp3", "réunion été.M4A")]
        outside = (data_dir.parent / "evil").exists() or (ROOT / "evil").exists()
        flat = all(re.fullmatch(r"\d{8}-\d{6}-\d{6}", d.name) for d in data_dir.iterdir())
        check("nom avec traversée de chemin : nettoyé, rien hors de data/",
              status == 200 and not outside and flat and names[0] == ("x.wav", ".wav")
              and names[1] == ("a.mp3", ".mp3"), f"{status} {names}")
        time.sleep(2)
    finally:
        proc.terminate()
        proc.wait(timeout=15)


if __name__ == "__main__":
    if "--refus" in sys.argv:
        part_b()
    else:
        part_a(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765")
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} vérifications réussies")
    sys.exit(1 if failed else 0)
