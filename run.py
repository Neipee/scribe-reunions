"""Lance Scribe réunions (PoC).

    python run.py              PC seul : http://127.0.0.1:8765 (le micro marche sur localhost)
    python run.py --lan        PC + téléphone sur le même réseau : HTTPS auto-signé + jeton d'accès
"""

import argparse
import secrets

import uvicorn

import scribe  # pose les variables d'environnement Hugging Face avant tout le reste
from scribe import server
from scribe.certs import ensure_certificate, lan_addresses


def main() -> None:
    parser = argparse.ArgumentParser(description="Scribe réunions — PoC de transcription locale")
    parser.add_argument("--lan", action="store_true",
                        help="écoute sur le réseau local (HTTPS + jeton) pour l'accès depuis un téléphone")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--new-cert", action="store_true",
                        help="régénère le certificat (si l'adresse IP du PC a changé)")
    args = parser.parse_args()

    options = {"host": "127.0.0.1", "port": args.port, "log_level": "warning"}
    if args.lan:
        cert, key = ensure_certificate(force=args.new_cert)
        server.ACCESS_TOKEN = secrets.token_urlsafe(12)
        options.update(host="0.0.0.0", ssl_certfile=str(cert), ssl_keyfile=str(key))
        print("\nAccès depuis un téléphone sur le même réseau (accepter l'avertissement de certificat) :")
        for ip in lan_addresses() or ["<adresse-IP-du-PC>"]:
            print(f"   https://{ip}:{args.port}/?t={server.ACCESS_TOKEN}")
        print(f"Sur ce PC : https://localhost:{args.port}/?t={server.ACCESS_TOKEN}\n")
    else:
        print(f"\nOuvrir http://127.0.0.1:{args.port} dans le navigateur.\n")
    print(f"Données : {scribe.DATA_DIR}\nModèles : {scribe.MODELS_DIR}\nCtrl+C pour arrêter.\n")
    uvicorn.run(server.app, **options)


if __name__ == "__main__":
    main()
