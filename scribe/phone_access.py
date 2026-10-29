"""Accès téléphone activé à chaud depuis la page du PC, sans redémarrer le serveur.

Au clic sur « Connecter le téléphone », un second serveur uvicorn démarre dans le même processus
(même application, même modèle déjà chargé), dans son propre fil d'exécution :
- lié à UNE adresse privée du PC (jamais 0.0.0.0), choisie parmi `lan_candidates()` ;
- en HTTPS avec le certificat auto-signé de certs/ (régénéré si l'adresse n'y figure pas) ;
- protégé par un jeton tiré à l'activation, jamais écrit dans un journal ni un fichier ;
- arrêté à la demande, à l'échéance (30 min par défaut, prolongeable) et à l'arrêt du serveur.

Les requêtes de ce second serveur portent la marque `PHONE_SCOPE_KEY` dans leur scope ASGI : le
contrôle d'accès de server.py s'en sert pour exiger le jeton et n'ouvrir que les routes utiles au
téléphone (jamais le panneau ni /api/phone*). Le client ne peut pas poser cette marque.
"""

from __future__ import annotations

import asyncio
import errno
import ipaddress
import secrets
import socket
import ssl
import threading
import time

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from .certs import certificate_ips, ensure_certificate, fingerprint
from .phone import lan_candidates

PHONE_SCOPE_KEY = "scribe.phone"
PORT_ATTEMPTS = 20          # ports essayés au-dessus du port de départ s'il est pris
START_TIMEOUT_SECONDS = 10
GRACEFUL_STOP_SECONDS = 5   # une requête en cours (envoi d'audio) a ce délai pour finir
WATCH_INTERVAL_SECONDS = 1


class PhoneAccessError(Exception):
    """Échec d'activation, avec un message prêt à afficher (en français)."""


def _bind(ip: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Sous Windows, SO_EXCLUSIVEADDRUSE garantit qu'on ne partage pas un port déjà pris par un
    # autre programme (ce que SO_REUSEADDR permettrait) : on détecte ainsi « port occupé ».
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind((ip, port))
        sock.listen(64)
    except OSError:
        sock.close()
        raise
    return sock


def _is_addr_in_use(exc: OSError) -> bool:
    # 10013 : port réservé par Windows (plages exclues d'Hyper-V…) ; on passe au suivant aussi.
    return (exc.errno in (errno.EADDRINUSE, errno.EACCES)
            or getattr(exc, "winerror", None) in (10048, 10013))


def presented_fingerprint(ip: str, port: int) -> str | None:
    """Empreinte SHA-256 du certificat réellement présenté à cette adresse (contrôle après démarrage)."""
    try:
        pem = ssl.get_server_certificate((ip, port), timeout=3)
    except (OSError, ssl.SSLError):
        return None
    cert = x509.load_pem_x509_certificate(pem.encode())
    return ":".join(f"{b:02X}" for b in cert.fingerprint(hashes.SHA256()))


class PhoneAccess:
    def __init__(self, app, minutes: int) -> None:
        self._app = app
        self.default_minutes = minutes
        self._lock = threading.RLock()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.token: str | None = None
        self.ip: str | None = None
        self.port: int | None = None
        self.expires_at = 0.0
        self.fingerprint: str | None = None
        self.verified = False
        self.cert_regenerated = False
        self.stopped_reason = ""  # "", "stopped" (bouton), "expired" (échéance)

    @property
    def active(self) -> bool:
        server, thread = self._server, self._thread
        return bool(server and thread and thread.is_alive() and server.started
                    and not server.should_exit)

    def check_token(self, supplied: str) -> bool:
        token = self.token
        return bool(token) and secrets.compare_digest(supplied.encode(), token.encode())

    async def _asgi(self, scope, receive, send):
        """Application servie par l'écouteur téléphone : l'appli commune, requêtes marquées."""
        if scope["type"] in ("http", "websocket"):
            scope = {**scope, PHONE_SCOPE_KEY: True}
        await self._app(scope, receive, send)

    def enable(self, ip: str | None, preferred_port: int, minutes: int | None = None) -> None:
        """Active l'accès, ou le déplace sur une autre adresse. Sans effet s'il tourne déjà là."""
        with self._lock:
            candidates = lan_candidates()
            if not candidates:
                raise PhoneAccessError(
                    "Aucune adresse réseau privée trouvée : ce PC n'est relié à aucun réseau local "
                    "(Wi-Fi ou Ethernet). Connectez-le au même Wi-Fi que le téléphone (ou au partage "
                    "de connexion du téléphone), puis réessayez.")
            was_active = self.active
            if ip is None:
                ip = self.ip if was_active else candidates[0]["ip"]
            if ip not in {c["ip"] for c in candidates}:
                raise PhoneAccessError("Adresse refusée : seules les adresses privées de ce PC sont "
                                       "acceptées.")
            addr = ipaddress.IPv4Address(ip)
            if not addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
                raise PhoneAccessError("Adresse refusée : elle n'est pas privée.")
            if was_active and self.ip == ip:
                return
            port_hint = self.port if was_active else preferred_port
            # Changement d'adresse : même jeton (le téléphone n'a qu'à changer d'adresse).
            token = self.token if was_active and self.token else secrets.token_urlsafe(12)
            self._stop_locked("")
            cert, key = self._certificate(ip)
            sock, port = self._bind_free_port(ip, port_hint)
            config = uvicorn.Config(self._asgi, interface="asgi3", lifespan="off", log_level="warning",
                                    access_log=False, proxy_headers=False, server_header=False,
                                    ssl_certfile=str(cert), ssl_keyfile=str(key),
                                    timeout_graceful_shutdown=GRACEFUL_STOP_SECONDS)
            try:
                config.load()
            except Exception as exc:
                sock.close()
                raise PhoneAccessError(f"Certificat HTTPS illisible ({exc}). Supprimez le dossier "
                                       "certs/ puis réessayez.") from exc
            server = uvicorn.Server(config)
            self.token, self.ip, self.port = token, ip, port
            self.fingerprint = fingerprint(cert)
            self.expires_at = time.time() + 60 * (minutes or self.default_minutes)
            self.stopped_reason = ""
            self._server = server
            self._thread = threading.Thread(target=self._run, args=(server, sock), daemon=True,
                                            name="phone-listener")
            self._thread.start()
            deadline = time.monotonic() + START_TIMEOUT_SECONDS
            while not server.started and self._thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                self._stop_locked("failed")
                raise PhoneAccessError("Le serveur téléphone n'a pas pu démarrer.")
            # Contrôle : l'adresse répond en HTTPS avec le certificat dont on affiche l'empreinte.
            self.verified = presented_fingerprint(ip, port) == self.fingerprint

    def _certificate(self, ip: str):
        try:
            cert, key = ensure_certificate()
            self.cert_regenerated = False
            if ip not in certificate_ips(cert):
                # Comme `--new-cert` : le nouveau certificat couvre les adresses actuelles du PC.
                cert, key = ensure_certificate(force=True)
                self.cert_regenerated = True
            return cert, key
        except Exception as exc:
            raise PhoneAccessError(f"Impossible de générer le certificat HTTPS : {exc}") from exc

    @staticmethod
    def _bind_free_port(ip: str, start: int) -> tuple[socket.socket, int]:
        last = min(start + PORT_ATTEMPTS, 65535)
        for port in range(start, last + 1):
            try:
                return _bind(ip, port), port
            except OSError as exc:
                if _is_addr_in_use(exc):
                    continue
                raise PhoneAccessError(f"Impossible d'écouter sur {ip} : {exc.strerror or exc}. "
                                       "L'adresse a peut-être changé : rouvrez le panneau.") from exc
        raise PhoneAccessError(f"Aucun port libre entre {start} et {last} : fermez le programme "
                               "qui les occupe, puis réessayez.")

    def _run(self, server: uvicorn.Server, sock: socket.socket) -> None:
        async def main() -> None:
            task = asyncio.create_task(server.serve(sockets=[sock]))
            while not task.done():
                if time.time() >= self.expires_at and not server.should_exit:
                    self.stopped_reason = "expired"
                    server.should_exit = True
                await asyncio.wait({task}, timeout=WATCH_INTERVAL_SECONDS)
        try:
            asyncio.run(main())
        except (Exception, SystemExit):
            pass  # échec de démarrage : signalé par enable(), server.started restant faux
        finally:
            sock.close()

    def extend(self, minutes: int | None = None) -> None:
        with self._lock:
            if not self.active:
                raise PhoneAccessError("L'accès téléphone n'est pas activé.")
            self.expires_at = time.time() + 60 * (minutes or self.default_minutes)

    def new_token(self) -> None:
        with self._lock:
            if not self.active:
                raise PhoneAccessError("L'accès téléphone n'est pas activé.")
            self.token = secrets.token_urlsafe(12)

    def stop(self, reason: str = "stopped") -> None:
        with self._lock:
            self._stop_locked(reason)

    def _stop_locked(self, reason: str) -> None:
        server, thread = self._server, self._thread
        if server is not None:
            server.should_exit = True
        if thread is not None and thread is not threading.current_thread():
            thread.join(GRACEFUL_STOP_SECONDS + 3)
        self._server = self._thread = None
        if reason:
            self.stopped_reason = reason
            self.token = None
