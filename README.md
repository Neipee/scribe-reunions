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

Raccourci Windows : `scripts\lancer-scribe.bat` (double-clic) lance le serveur s'il ne tourne pas déjà,
attend qu'il réponde, puis ouvre le navigateur. Il utilise des chemins relatifs au dépôt.

Au premier lancement, le modèle se télécharge. Une barre de progression s'affiche, l'opération prend environ 1 à 3 minutes selon le débit, puis le chargement environ 20 s.

Ensuite :

1. Appuyer sur **Enregistrer**.
2. Parler.
3. Appuyer sur **Arrêter**.

Chaque enregistrement est gardé dans `data/<date-heure>/` :

- `audio.wav` : l'audio ;
- `transcript.txt` : le texte ;
- `meta.json` : les durées et la révision du modèle.

## Importer un fichier audio

Au lieu d'enregistrer, on peut transcrire un fichier existant (enregistrement d'un dictaphone, d'un
téléphone, d'une visioconférence…) :

1. Dans la carte **Importer un fichier audio**, glisser le fichier dans la zone en pointillés, ou cliquer dessus pour le choisir.
2. La page affiche le nom, la taille et la durée. Appuyer sur **Transcrire ce fichier**.
3. La progression s'affiche (envoi, décodage, puis segment par segment), puis le texte, comme pour un enregistrement.

- **Formats.** mp3, wav, m4a, aac, ogg, oga, opus, flac, webm, wma, aiff, aif, amr, 3gp, et l'audio d'une vidéo (mp4, m4v, mov, mkv). Le format est reconnu d'après le contenu du fichier, pas d'après son extension ; en cas de doute, le serveur refuse le fichier avec un message clair.
- **Limites** (réglables par variables d'environnement) : `SCRIBE_MAX_IMPORT_MB` (500 Mo par défaut) et `SCRIBE_MAX_IMPORT_HOURS` (4 h par défaut). Exemple : `$env:SCRIBE_MAX_IMPORT_MB = "1000"; .venv\Scripts\python run.py`. Un fichier de 4 h demande environ 0,5 Go de RAM de plus pour le décodage, et environ 70 min de calcul (0,3 × la durée).
- **Une seule transcription à la fois**, enregistrement ou import : un second envoi est refusé avec un message.
- **Stockage.** Le fichier d'origine est copié dans `data/<date-heure>/original.<extension>`, à côté de `transcript.txt` et `meta.json` (qui garde le nom d'origine, nettoyé). Si le fichier est illisible, le dossier est supprimé.
- **Décodage.** Bibliothèque [PyAV](https://pyav.basswood.io) (`av`, licence BSD-3), installée dans `.venv/` avec les autres dépendances. Ses roues Windows embarquent FFmpeg : il n'y a rien à installer sur le système. Ce FFmpeg est compilé avec des composants GPL (x264, x265) : sans conséquence pour un usage local, mais à vérifier avant toute redistribution de l'application.
- **Sécurité.** Mêmes contrôles que pour l'enregistrement (nom d'hôte, origine, jeton en mode `--lan`). Le nom envoyé n'est jamais utilisé comme chemin ; le contenu n'est jamais exécuté ; seul le protocole `file` est autorisé au décodage, donc un fichier piégé (liste de lecture HLS, etc.) ne peut déclencher aucun accès réseau.
- **Qualité.** Les formats avec perte (mp3, aac, opus…) peuvent changer un mot ou la ponctuation par rapport au WAV d'origine. Mesures dans docs/POC.md.

Tests (serveur lancé, modèle chargé) : `.venv\Scripts\python scripts\test_import.py` ; refus et sécurité sans modèle : `.venv\Scripts\python scripts\test_import.py --refus`. Les fichiers de test sont générés à la volée dans un dossier temporaire.

## Lancer pour l'utiliser depuis un téléphone

Le navigateur d'un téléphone n'autorise le micro qu'en HTTPS. Le mode `--lan` génère un certificat
auto-signé local dans `certs/` et un jeton d'accès :

```powershell
.venv\Scripts\python run.py --lan
```

La console affiche une adresse du type `https://192.168.x.y:8765/?t=XXXX`. L'interface web du PC propose
aussi un bouton qui rassemble tout ce qu'il faut (voir ci-dessous).

### Bouton « Connecter le téléphone »

Sur le PC, la page de Scribe a un bouton **Connecter le téléphone** (en haut à droite). Il ouvre un
panneau avec, pour chaque élément, un bouton **Copier** :

1. l'**adresse complète** `https://192.168.x.y:8765/?t=…` : c'est ce qu'il faut coller dans l'appli
   Android (le jeton est dedans, l'appli l'extrait toute seule) ;
2. l'**empreinte SHA-256** du certificat, à comparer avec celle que l'appli affiche au premier
   raccordement ;
3. en repliable : le **QR code** de l'adresse complète (à lire avec l'appareil photo du téléphone, puis
   copier le lien affiché et le coller dans l'appli ; l'appli ne scanne pas les QR), et la saisie en deux
   champs (adresse seule + jeton).

Si le PC a plusieurs adresses (Wi-Fi, Ethernet, VPN, adaptateurs virtuels), une liste permet de choisir ;
la plus probable (Wi-Fi/Ethernet réel, route par défaut) est proposée en premier. Choisir celle du réseau
auquel le téléphone est connecté.

- **Mode local seulement.** Si le serveur a été lancé sans `--lan`, le panneau l'indique et donne la
  commande `.venv\Scripts\python run.py --lan` à lancer (avec un bouton Copier). Il n'y a pas de bouton de
  redémarrage automatique : un serveur relancé en arrière-plan n'aurait plus de fenêtre pour l'arrêter.
  En mode `--lan`, ouvrir sur le PC l'adresse « Sur ce PC » de la console (`https://localhost:8765/?t=…`,
  avec l'avertissement de certificat à accepter), puis cliquer sur le bouton.
- **Régénérer le jeton.** Le bouton du panneau remplace le jeton : l'ancien cesse de marcher tout de suite
  et tout téléphone connecté doit coller la nouvelle adresse. La page du PC reste connectée.
- **Sécurité.** Le panneau et ses routes (`/api/phone`) ne répondent qu'aux requêtes venant du PC lui-même
  (connexion et nom d'hôte locaux, vérifiés côté serveur) : le téléphone ou un autre appareil du réseau
  reçoit un refus, même avec le bon jeton. Les réponses ne sont jamais mises en cache, le jeton n'est écrit
  dans aucun fichier ni journal, et le QR code est dessiné sur le PC (aucun service externe).

Pour utiliser le navigateur du téléphone plutôt que l'appli :

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
3. Sur le PC, lancer `.venv\Scripts\python run.py --lan`, ouvrir l'adresse « Sur ce PC » de la console,
   puis cliquer sur **Connecter le téléphone** (voir plus haut) : le panneau donne l'adresse complète
   `https://192.168.x.y:8765/?t=…` et l'empreinte SHA-256, avec un bouton **Copier** chacune. (Les mêmes
   informations sont aussi affichées dans la console.)
4. Envoyer l'adresse copiée au téléphone (messagerie à soi-même, QR code lu avec l'appareil photo…),
   la coller dans le champ **Adresse** de l'appli (le jeton `?t=…` est extrait automatiquement ; sinon,
   saisir l'adresse et le jeton séparément), puis appuyer sur **Se connecter**.
5. Au premier raccordement, l'appli affiche l'empreinte du certificat du PC. La comparer avec celle
   du panneau ou de la console (au moins les premiers et derniers groupes), puis appuyer sur
   **Identiques, faire confiance**. Ne pas accepter si elles diffèrent.
6. Appuyer sur **Enregistrer** et autoriser le micro quand Android le demande. L'import d'un
   fichier audio de la page passe par le sélecteur de fichiers d'Android.

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
- **Format.** L'enregistrement est envoyé en WAV PCM 16 bits, produit par la page elle-même. Les fichiers importés peuvent être dans les formats listés plus haut.
- **Qualité.** Elle n'a été mesurée que sur une voix de synthèse propre. Elle reste à évaluer sur de vraies réunions : bruit, plusieurs voix, micro de téléphone.
- **Fonctions absentes.** Il n'y a ni synthèse, ni historique, ni identification des intervenants, ni comptes (hors du périmètre du PoC).
