"""Téléchargement, cache local et mise à jour du modèle depuis Hugging Face.

Organisation sur disque :
    models/<org>--<nom>/state.json      révision active, dates de vérification
    models/<org>--<nom>/<sha>/           fichiers du modèle pour cette révision

Seuls appels réseau de l'application : HfApi.model_info (version distante)
et snapshot_download (fichiers du modèle), tous deux vers huggingface.co.
"""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from . import MODELS_DIR, config


class HubUnreachable(Exception):
    """Hugging Face injoignable (hors ligne, proxy, DNS…)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _file_size(path: str) -> int:
    # Sous Windows, la taille lue dans le répertoire reste figée tant que le fichier
    # est ouvert en écriture : on la lit via un descripteur ouvert.
    fd = os.open(path, os.O_RDONLY)
    try:
        return os.fstat(fd).st_size
    finally:
        os.close(fd)


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += _file_size(os.path.join(root, name))
            except OSError:
                pass  # fichier renommé pendant le parcours
    return total


class ModelManager:
    def __init__(self, repo_id: str = config.MODEL_ID, root: Path = MODELS_DIR):
        self.repo_id = repo_id
        self.base = root / repo_id.replace("/", "--")
        self.state_file = self.base / "state.json"
        self.api = HfApi()
        self._download_lock = threading.Lock()
        self.progress: dict | None = None  # {"done": octets, "total": octets}

    # --- état local -------------------------------------------------------

    def state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_state(self, **changes) -> dict:
        new_state = {**self.state(), "repo_id": self.repo_id, **changes}
        self.base.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(new_state, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)
        return new_state

    def local_path(self) -> Path | None:
        revision = self.state().get("revision")
        if not revision:
            return None
        path = self.base / revision
        return path if (path / "config.json").exists() else None

    def update_available(self) -> bool:
        s = self.state()
        return bool(s.get("remote_revision")) and s.get("remote_revision") != s.get("revision")

    # --- Hugging Face ------------------------------------------------------

    def check_remote(self) -> dict:
        """Lit la dernière révision publiée. Lève HubUnreachable si hors ligne."""
        try:
            info = self.api.model_info(self.repo_id, timeout=config.HUB_TIMEOUT_SECONDS)
        except Exception as exc:  # réseau, proxy, 5xx : on garde le modèle local
            self._save_state(last_check=_now(), last_check_ok=False)
            raise HubUnreachable(f"Hugging Face injoignable : {exc.__class__.__name__}") from exc
        date = info.last_modified.isoformat() if info.last_modified else None
        self._save_state(last_check=_now(), last_check_ok=True,
                         remote_revision=info.sha, remote_date=date)
        return {"revision": info.sha, "date": date}

    def _expected_size(self, revision: str) -> int:
        info = self.api.model_info(self.repo_id, revision=revision, files_metadata=True,
                                   timeout=config.HUB_TIMEOUT_SECONDS)
        return sum(
            (s.size or 0) for s in info.siblings
            if any(fnmatch.fnmatch(s.rfilename, p) for p in config.ALLOW_PATTERNS)
        )

    def download(self, revision: str) -> Path:
        """Télécharge une révision précise dans models/…/<sha>/ (reprend si interrompu)."""
        if not self._download_lock.acquire(blocking=False):
            raise RuntimeError("Un téléchargement est déjà en cours.")
        target = self.base / revision
        stop = threading.Event()
        try:
            try:
                total = self._expected_size(revision)
            except Exception as exc:
                raise HubUnreachable(f"Hugging Face injoignable : {exc.__class__.__name__}") from exc
            target.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(target).free
            if free < total - _dir_size(target) + 500 * 1024 * 1024:
                raise RuntimeError(
                    f"Espace disque insuffisant : {total / 1e9:.1f} Go nécessaires, "
                    f"{free / 1e9:.1f} Go libres.")
            self.progress = {"done": _dir_size(target), "total": total}

            def watch() -> None:
                while not stop.wait(1.0):
                    self.progress = {"done": min(_dir_size(target), total), "total": total}

            threading.Thread(target=watch, daemon=True).start()
            try:
                snapshot_download(self.repo_id, revision=revision, local_dir=target,
                                  allow_patterns=config.ALLOW_PATTERNS)
            except Exception as exc:
                raise HubUnreachable(f"Téléchargement interrompu : {exc.__class__.__name__}: {exc}") from exc
            # Le cache de reprise de huggingface_hub n'est plus utile une fois fini.
            shutil.rmtree(target / ".cache", ignore_errors=True)
            return target
        finally:
            stop.set()
            self.progress = None
            self._download_lock.release()

    @property
    def downloading(self) -> bool:
        return self._download_lock.locked()

    def activate(self, revision: str, revision_date: str | None) -> str | None:
        """Bascule sur une révision téléchargée ; renvoie l'ancienne."""
        previous = self.state().get("revision")
        self._save_state(revision=revision, revision_date=revision_date, downloaded_at=_now())
        return previous

    def remove_revision(self, revision: str) -> None:
        if revision and revision != self.state().get("revision"):
            shutil.rmtree(self.base / revision, ignore_errors=True)
