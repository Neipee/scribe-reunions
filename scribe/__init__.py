"""Scribe réunions — PoC : enregistrer puis transcrire en local avec Nemotron ASR.

Les variables d'environnement Hugging Face doivent être posées AVANT tout import
de huggingface_hub / transformers : c'est fait ici, au chargement du paquet.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"
CERTS_DIR = ROOT / "certs"

# Tout le cache Hugging Face reste dans le projet (rien dans le profil utilisateur).
os.environ.setdefault("HF_HOME", str(MODELS_DIR / ".hf-home"))
# Aucune télémétrie, téléchargement HTTP classique (pas de cache de blocs Xet en double).
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("TORCH_HOME", str(MODELS_DIR / ".torch-home"))
