"""Réglages du PoC, modifiables par variables d'environnement."""

import os

# Dépôt Hugging Face du modèle. Seuls les fichiers Transformers sont téléchargés
# (safetensors + json), pas le .nemo ni le .gguf.
MODEL_ID = os.environ.get("SCRIBE_MODEL_ID", "nvidia/nemotron-3.5-asr-streaming-0.6b")
ALLOW_PATTERNS = ["*.json", "*.safetensors"]

# Vérification de mise à jour au démarrage :
#   off      : jamais
#   check    : vérifie et signale (par défaut), l'utilisateur clique pour télécharger
#   download : vérifie et télécharge/installe automatiquement la nouvelle révision
AUTO_UPDATE = os.environ.get("SCRIBE_AUTO_UPDATE", "check").lower()
if AUTO_UPDATE not in {"off", "check", "download"}:
    AUTO_UPDATE = "check"

LANGUAGE = os.environ.get("SCRIBE_LANGUAGE", "fr-FR")

# Découpage des longs enregistrements (secondes) pour borner la mémoire.
SEGMENT_SECONDS = int(os.environ.get("SCRIBE_SEGMENT_SECONDS", "30"))

SAMPLE_RATE = 16_000
MAX_UPLOAD_BYTES = 600 * 1024 * 1024  # ~5 h de WAV 16 kHz mono 16 bits
HUB_TIMEOUT_SECONDS = 15

# Import d'un fichier audio/vidéo existant : limites configurables.
MAX_IMPORT_BYTES = int(float(os.environ.get("SCRIBE_MAX_IMPORT_MB", "500")) * 1024 * 1024)
MAX_IMPORT_SECONDS = int(float(os.environ.get("SCRIBE_MAX_IMPORT_HOURS", "4")) * 3600)
IMPORT_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac", ".webm",
                     ".wma", ".aiff", ".aif", ".amr", ".mp4", ".m4v", ".mov", ".mkv", ".3gp")

# Accès téléphone activé depuis la page du PC (bouton « Connecter le téléphone ») : durée avant
# arrêt automatique, en minutes. Le panneau permet de prolonger d'autant.
PHONE_ACCESS_MINUTES = max(1, int(float(os.environ.get("SCRIBE_PHONE_MINUTES", "30"))))
