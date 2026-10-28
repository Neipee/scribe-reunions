"""Serveur local : interface web + API de transcription + gestion du modèle."""

from __future__ import annotations

import json
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import DATA_DIR, config
from .asr import AudioError, Transcriber, is_memory_error, read_wav
from .model_manager import HubUnreachable, ModelManager

STATIC_DIR = Path(__file__).parent / "static"
LANGUAGE_RE = re.compile(r"^(auto|[a-z]{2}(-[A-Z]{2})?)$")

# Jeton d'accès, posé par run.py en mode réseau local (--lan). None = pas de contrôle.
ACCESS_TOKEN: str | None = None
# Noms d'hôte acceptés (anti « DNS rebinding ») ; run.py ajoute les IP locales en mode --lan.
ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
MAX_PENDING_JOBS = 1

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
manager = ModelManager()
transcriber = Transcriber()

# Phase du modèle affichée dans l'interface : init, downloading, loading, ready, absent, error
status = {"phase": "init", "message": "Démarrage…", "notice": ""}
jobs: dict[str, dict] = {}
_update_lock = threading.Lock()


def _set(phase: str | None = None, message: str | None = None, notice: str | None = None) -> None:
    if phase is not None:
        status["phase"] = phase
    if message is not None:
        status["message"] = message
    if notice is not None:
        status["notice"] = notice


def _load(path: Path) -> None:
    _set("loading", "Chargement du modèle en mémoire…")
    try:
        transcriber.load(path)
    except Exception as exc:
        transcriber.unload()
        if is_memory_error(exc):
            raise RuntimeError("Mémoire insuffisante pour charger le modèle (~3 Go de RAM libre "
                               "nécessaires). Fermez des applications puis relancez.") from exc
        raise
    _set("ready", "Prêt.")


def _install_latest() -> None:
    """Télécharge la dernière révision si elle diffère de la locale, puis la charge."""
    remote = manager.check_remote()
    local = manager.state().get("revision") if manager.local_path() else None
    if remote["revision"] == local:
        _set(notice="Le modèle est à jour.")
        return
    first_install = local is None
    if first_install:
        _set("downloading", "Premier lancement : téléchargement du modèle depuis Hugging Face…")
    else:
        _set(notice="Téléchargement de la nouvelle révision en arrière-plan ; "
                    "l'ancienne reste utilisable en attendant.")
    path = manager.download(remote["revision"])
    snapshot = manager.state()
    manager.activate(remote["revision"], remote["date"])
    try:
        _load(path)
    except Exception:
        manager.restore(snapshot)  # retour arrière sur la révision qui marchait
        manager.remove_revision(remote["revision"])
        if local:
            _load(manager.local_path())
        raise
    if local:
        manager.remove_revision(local)
    _set(notice="Modèle mis à jour." if not first_install else "Modèle téléchargé.")


def _run_update() -> None:
    if not _update_lock.acquire(blocking=False):
        return
    try:
        _install_latest()
    except HubUnreachable as exc:
        if transcriber.ready:
            _set(notice=f"Vérification impossible ({exc}). Le modèle local reste utilisé.")
        else:
            _set("absent", "Modèle absent et Hugging Face injoignable. Connectez-vous à Internet "
                           "puis cliquez sur « Télécharger le modèle ».")
    except Exception as exc:
        if transcriber.ready:
            _set(notice=f"Échec de la mise à jour : {exc}")
        else:
            _set("error", f"Erreur : {exc}")
    finally:
        _update_lock.release()


def _bootstrap() -> None:
    local = manager.local_path()
    if local is None:
        _run_update()
        return
    try:
        _load(local)
    except Exception as exc:
        _set("error", f"Erreur au chargement du modèle : {exc}")
        return
    if config.AUTO_UPDATE == "off":
        return
    try:
        manager.check_remote()
    except HubUnreachable:
        _set(notice="Hors ligne : vérification de mise à jour impossible, modèle local utilisé.")
        return
    if manager.update_available():
        if config.AUTO_UPDATE == "download":
            _run_update()
        else:
            _set(notice="Une nouvelle révision du modèle est disponible.")


@app.on_event("startup")
def _startup() -> None:
    threading.Thread(target=_bootstrap, daemon=True, name="bootstrap").start()


@app.middleware("http")
async def _check_access(request: Request, call_next):
    # Empêche une autre page web ouverte dans le navigateur d'utiliser l'API locale.
    host = request.headers.get("host", "")
    if urlsplit("//" + host).hostname not in ALLOWED_HOSTS:
        return PlainTextResponse("Hôte non autorisé.", status_code=403)
    origin = request.headers.get("origin")
    if request.method != "GET" and origin and urlsplit(origin).netloc != host:
        return PlainTextResponse("Origine non autorisée.", status_code=403)
    if not ACCESS_TOKEN:
        return await call_next(request)
    supplied = request.query_params.get("t") or request.cookies.get("scribe_token") or ""
    if not secrets.compare_digest(supplied.encode(), ACCESS_TOKEN.encode()):
        return PlainTextResponse("Accès refusé : ouvrez l'adresse complète affichée dans la "
                                 "console du PC (avec ?t=…).", status_code=403)
    response = await call_next(request)
    if request.query_params.get("t"):
        response.set_cookie("scribe_token", ACCESS_TOKEN, httponly=True, secure=True,
                            samesite="strict")
    return response


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/status")
def get_status() -> dict:
    s = manager.state()
    return {
        **status,
        "busy": manager.downloading or _update_lock.locked(),
        "progress": manager.progress,
        "auto_update": config.AUTO_UPDATE,
        "language": config.LANGUAGE,
        "model": {
            "repo_id": manager.repo_id,
            "revision": s.get("revision"),
            "revision_date": s.get("revision_date"),
            "downloaded_at": s.get("downloaded_at"),
            "last_check": s.get("last_check"),
            "last_check_ok": s.get("last_check_ok"),
            "remote_revision": s.get("remote_revision"),
            "update_available": manager.update_available(),
        },
    }


@app.post("/api/model/update")
def update_model() -> dict:
    if _update_lock.locked():
        return {"started": False, "message": "Une vérification ou un téléchargement est déjà en cours."}
    _set(notice="Vérification de la dernière révision sur Hugging Face…")
    threading.Thread(target=_run_update, daemon=True).start()
    return {"started": True}


def _run_job(job: dict, audio, folder: Path, language: str) -> None:
    job["status"] = "running"
    start = time.perf_counter()
    try:
        text = transcriber.transcribe(audio, language,
                                      on_progress=lambda i, n: job.update(done=i, total=n))
        elapsed = time.perf_counter() - start
        seconds = len(audio) / config.SAMPLE_RATE
        meta = {
            "model": manager.repo_id,
            "revision": manager.state().get("revision"),
            "language": language,
            "audio_seconds": round(seconds, 2),
            "processing_seconds": round(elapsed, 2),
            "rtf": round(elapsed / seconds, 3) if seconds else None,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (folder / "transcript.txt").write_text(text + "\n", encoding="utf-8")
        (folder / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    except Exception as exc:
        job["status"] = "error"
        job["error"] = ("Mémoire insuffisante pendant la transcription : fermez des applications "
                        "ou faites des enregistrements plus courts." if is_memory_error(exc)
                        else f"Erreur de transcription : {exc}")
        return
    job.update(status="done", text=text, meta=meta, folder=folder.name)


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form(config.LANGUAGE)) -> dict:
    if not transcriber.ready:
        raise HTTPException(503, "Le modèle n'est pas prêt : " + status["message"])
    if not LANGUAGE_RE.match(language):
        raise HTTPException(400, "Code de langue invalide.")
    if sum(j["status"] in ("queued", "running") for j in jobs.values()) >= MAX_PENDING_JOBS:
        raise HTTPException(429, "Une transcription est déjà en cours : attendez qu'elle se termine.")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Enregistrement trop volumineux.")
    try:
        audio = await run_in_threadpool(read_wav, data)
    except AudioError as exc:
        raise HTTPException(400, str(exc)) from exc
    if len(audio) < config.SAMPLE_RATE // 2:
        raise HTTPException(400, "Enregistrement trop court (moins d'une demi-seconde).")

    folder = DATA_DIR / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "audio.wav").write_bytes(data)

    job_id = uuid.uuid4().hex
    job = {"id": job_id, "status": "queued", "done": 0, "total": 0,
           "audio_seconds": round(len(audio) / config.SAMPLE_RATE, 1)}
    jobs[job_id] = job
    threading.Thread(target=_run_job, args=(job, audio, folder, language), daemon=True).start()
    return {"job_id": job_id, "audio_seconds": job["audio_seconds"]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Transcription inconnue.")
    return job
