# Scribe réunions — PoC

Preuve de concept : on appuie sur **Enregistrer**, puis sur **Arrêter**, et la transcription s'affiche.
Le modèle de reconnaissance vocale est **NVIDIA Nemotron 3.5 ASR Streaming 0.6B**, téléchargé une
fois depuis Hugging Face puis gardé dans `models/`.

- L'audio et le texte restent sur le PC, dans `data/`.
- Le seul trafic réseau de l'application va vers Hugging Face (`huggingface.co` et ses serveurs de fichiers `*.hf.co`), pour télécharger le modèle et vérifier sa version.
- Il n'y a ni télémétrie ni service tiers.

Le modèle tourne sur le PC. Le téléphone sert seulement de micro et d'écran, via son navigateur
ou l'appli Android « Scribe » (voir « Installer l'APK sur le téléphone » et les limites plus bas). Décisions et mesures : [docs/POC.md](docs/POC.md).

## Prérequis

- Windows 10/11, macOS ou Linux, avec Python 3.11 à 3.13. Testé : Windows 11 et Python 3.13.
- Environ 3,5 Go de RAM libre et 4 Go d'espace disque :
  - modèle : 2,55 Go ;
  - environnement Python : 1,3 Go.
- Pas de GPU nécessaire : le modèle tourne sur le processeur.
- Internet seulement au premier lancement, pour télécharger le modèle (2,55 Go).
- Aucun droit administrateur : tout s'installe dans le dossier du projet (`.venv/`, `models/`, `data/`).

## Installation (une fois)

```powershell
cd scribe-reunions
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install --no-cache-dir -r requirements.txt
```

(macOS/Linux : `python3 -m venv .venv` puis `.venv/bin/python …`.)

## Lancer sur le PC

```powershell
.venv\Scripts\python run.py
```

Ouvrir <http://127.0.0.1:8765> dans le navigateur.

Au premier lancement, le modèle se télécharge. Une barre de progression s'affiche, l'opération prend environ 1 à 3 minutes selon le débit, puis le chargement environ 20 s.

Ensuite :

1. Appuyer sur **Enregistrer**.
2. Parler.
3. Appuyer sur **Arrêter**.

Chaque enregistrement est gardé dans `data/<date-heure>/` :

- `audio.wav` : l'audio ;
- `transcript.txt` : le texte ;
- `meta.json` : les durées et la révision du modèle.

## Lancer pour l'utiliser depuis un téléphone

Le navigateur d'un téléphone n'autorise le micro qu'en HTTPS. Le mode `--lan` génère un certificat
auto-signé local dans `certs/` et un jeton d'accès :

```powershell
.venv\Scripts\python run.py --lan
```

La console affiche une adresse du type `https://192.168.x.y:8765/?t=XXXX` :

1. Ouvrir cette adresse complète sur le téléphone, connecté au **même réseau** que le PC.
2. Accepter l'avertissement de certificat (« Avancé » → « Continuer »).
3. Autoriser le micro.

Sans le jeton, l'accès est refusé.

Points à connaître :

- **Pare-feu Windows.** Au premier lancement en `--lan`, Windows peut demander d'autoriser Python sur le réseau. Sur un poste d'entreprise, cela peut exiger un administrateur. Sans cette autorisation, le téléphone n'atteint pas le PC.
- **Réseau d'entreprise.** Les réseaux Wi-Fi d'entreprise ou invités isolent souvent les appareils entre eux. Le plus simple : un partage de connexion du téléphone vers le PC, ou un réseau domestique.
- **Changement d'adresse IP.** Si l'adresse IP du PC change, relancer avec `--lan --new-cert`.
- **Écran du téléphone.** Il doit rester allumé et la page ouverte pendant l'enregistrement. La page demande de garder l'écran actif quand le navigateur le permet.
- **Empreinte du certificat.** La console affiche aussi l'« Empreinte SHA-256 du certificat ». L'appli Android la montre au premier raccordement pour comparaison.

## Installer l'APK sur le téléphone

Une appli Android « Scribe » remplace le navigateur côté téléphone. C'est un simple client : le modèle
tourne toujours sur le PC, et l'appli ne contacte que l'adresse du PC saisie. Elle est compilée par
GitHub Actions à chaque tag `v*` ([workflow](.github/workflows/android.yml)). Détails techniques et choix
de sécurité : [docs/APK.md](docs/APK.md).

**Dernière version :** <https://github.com/Neipee/scribe-reunions/releases/latest>

1. Sur le téléphone, ouvrir le lien ci-dessus et télécharger le fichier `scribe-vX.Y.Z.apk`
   (rubrique « Assets »).
2. Ouvrir le fichier téléchargé. Android demande d'autoriser l'installation depuis cette source
   (le navigateur ou l'appli Fichiers) : l'autoriser, puis revenir et appuyer sur « Installer ».
   Play Protect peut avertir d'une appli inconnue : choisir « Installer quand même ».
3. Sur le PC, lancer `.venv\Scripts\python run.py --lan`. Noter l'adresse
   `https://192.168.x.y:8765/?t=…` et l'empreinte SHA-256 affichées.
4. Dans l'appli, saisir l'adresse complète (le jeton `?t=…` est extrait automatiquement), ou
   l'adresse et le jeton séparément, puis appuyer sur **Se connecter**.
5. Au premier raccordement, l'appli affiche l'empreinte du certificat du PC. La comparer avec celle
   de la console (au moins les premiers et derniers groupes), puis appuyer sur
   **Identiques, faire confiance**. Ne pas accepter si elles diffèrent.
6. Appuyer sur **Enregistrer** et autoriser le micro quand Android le demande.

Facultatif : comparer l'empreinte SHA-256 de l'APK avec celle indiquée dans la release (fichier
`.sha256`).

Limites :

- **PC allumé, même réseau.** Le PC doit être allumé, lancé avec `--lan`, et le téléphone sur le
  même réseau Wi-Fi (ou partage de connexion). Le pare-feu Windows doit autoriser Python.
- **Jeton à chaque lancement.** Le jeton change à chaque démarrage du PC : il faut le ressaisir
  (l'appli garde l'adresse et l'empreinte, le message « Jeton refusé » le signale).
- **Certificat auto-signé.** L'appli ne l'accepte que s'il a l'empreinte que vous avez confirmée.
  Après `--new-cert`, elle signale le changement et redemande la comparaison.
- **Pas d'enregistrement écran éteint.** L'appli garde l'écran allumé tant qu'elle est au premier
  plan. Si l'écran est verrouillé ou si l'on change d'appli, l'enregistrement peut s'interrompre.
  L'enregistrement en arrière-plan est hors du périmètre de ce PoC.
- **Clé de signature de test.** Chaque compilation est signée avec une clé de test différente,
  générée puis jetée par le workflow. Pour installer une nouvelle version, **désinstaller d'abord
  l'ancienne** (sinon Android refuse : « conflit avec un package existant »).
- **Non testée sur un vrai téléphone** à ce stade (voir docs/APK.md, « À tester »).

## Mise à jour du modèle

- **Bouton « Mettre à jour le modèle ».** Il compare la révision locale à la dernière révision publiée sur Hugging Face, et ne télécharge que si elles diffèrent. L'ancienne révision reste utilisable pendant le téléchargement, puis elle est supprimée après la bascule.
- **Vérification automatique au démarrage.** Elle ne bloque pas l'application. Hors ligne, le modèle local est utilisé et un message l'indique. Variable `SCRIBE_AUTO_UPDATE` :
  - `check` (défaut) : signale qu'une mise à jour existe ;
  - `download` : télécharge et installe automatiquement ;
  - `off` : désactive la vérification.

  ```powershell
  $env:SCRIBE_AUTO_UPDATE = "download"; .venv\Scripts\python run.py
  ```

- L'interface affiche le nom du modèle, sa révision, sa date de publication et la date de la dernière vérification.

Autres réglages :

- `SCRIBE_LANGUAGE` : `fr-FR` par défaut, ou `auto` pour la détection.
- `SCRIBE_MODEL_ID` : un autre dépôt compatible Transformers.

## Mesurer

```powershell
powershell -ExecutionPolicy Bypass -File scripts\make_sample.ps1
.venv\Scripts\python scripts\bench.py tests\samples\reunion_fr.wav tests\samples\reunion_fr.txt
```

Le premier script génère un échantillon français avec la voix Windows locale « Hortense ». Le second affiche le temps de chargement, le temps de transcription, la mémoire et le taux d'erreur.

## Limites connues

- **Le modèle ne tourne pas sur le téléphone.** Le téléphone envoie l'audio au PC par le réseau local. Ce PoC ne prouve donc pas la transcription embarquée sur mobile (voir docs/POC.md).
- **Pas de texte en direct.** La transcription se fait à l'arrêt de l'enregistrement. Comptez environ 0,3 × la durée de l'audio sur un i7 portable de 2021, soit environ 18 min pour 1 h.
- **Mémoire.** Il faut environ 3,1 Go de RAM pour le modèle, et l'enregistrement est gardé en mémoire dans le navigateur, environ 115 Mo par heure.
- **Navigateur.** Si l'onglet est fermé ou rechargé pendant l'enregistrement, l'audio est perdu.
- **Format.** Seul le WAV PCM 16 bits est accepté par le serveur. La page web le produit elle-même.
- **Qualité.** Elle n'a été mesurée que sur une voix de synthèse propre. Elle reste à évaluer sur de vraies réunions : bruit, plusieurs voix, micro de téléphone.
- **Fonctions absentes.** Il n'y a ni synthèse, ni historique, ni identification des intervenants, ni comptes (hors du périmètre du PoC).
