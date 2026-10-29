# Appli Android « Scribe » (client du PoC)

Identifiant `com.neipee.scribe`, Android 8.0 (API 26) ou plus récent, cible API 35.
Code : [`android/`](../android). Compilation et publication : [`.github/workflows/android.yml`](../.github/workflows/android.yml).

## Architecture

```
Téléphone : appli Scribe                PC : accès téléphone ouvert (bouton) ou run.py --lan
┌──────────────────────────────┐   HTTPS, réseau local    ┌──────────────────────────┐
│ SetupActivity                │ ───────────────────────▶ │ FastAPI + Nemotron ASR   │
│  adresse + jeton, empreinte  │   certificat épinglé     │ interface web (static/)  │
│ WebActivity (WebView)        │ ◀─────────────────────── │ certificat auto-signé    │
│  interface du PoC, micro     │                          └──────────────────────────┘
└──────────────────────────────┘
```

L'appli n'embarque pas d'interface propre. Elle affiche, dans une WebView plein écran, la page servie
par le PC (`scribe/static/`). Elle ajoute ce qu'un navigateur fait mal : mémoriser l'adresse, vérifier
le certificat auto-signé sans avertissement à contourner, demander le micro proprement, garder l'écran
allumé et afficher des erreurs lisibles.

| Fichier | Rôle |
|---|---|
| `ServerAddress.kt` | Lecture de la saisie : adresse complète `https://IP:8765/?t=…` ou adresse + jeton ; port 8765 par défaut ; HTTPS obligatoire. |
| `Tls.kt` | Lecture de l'empreinte du certificat, connexion avec certificat épinglé, test du jeton (`/api/status?t=…`), messages d'erreur. |
| `SetupActivity.kt` | Écran de configuration, confirmation de l'empreinte, mémorisation. |
| `WebActivity.kt` | WebView, filtrage des requêtes, certificat, micro, sélecteur de fichiers, écran allumé. |
| `Prefs.kt` | Stockage privé (`SharedPreferences`) et marges des barres système (Android 15). |

## Décisions de sécurité

**Certificat auto-signé : épinglage confirmé par l'utilisateur.** Au premier raccordement, l'appli ouvre
une connexion TLS vers le PC, lit le certificat, puis interrompt la poignée de main. Aucune donnée n'est
donc envoyée à un serveur non vérifié, et surtout pas le jeton. Elle affiche l'empreinte SHA-256, que
le panneau « Connecter le téléphone » du PC affiche aussi (et la console en mode `run.py --lan` ;
fonction `fingerprint` de `scribe/certs.py`). Si
l'utilisateur confirme, l'empreinte est enregistrée pour ce couple hôte:port. Ensuite :

- la vérification native (`checkAccess`) n'accepte que ce certificat exact (`PinnedTrustManager`) ;
- la WebView (`onReceivedSslError`) n'appelle `proceed()` que si l'URL a l'origine configurée **et** que
  l'empreinte est identique ; sinon `cancel()` et message d'erreur ;
- si le certificat change (`--new-cert`), l'appli le signale et redemande une comparaison.

Aucun `TrustManager` n'accepte tout, et aucune autorité n'est ajoutée au magasin de confiance.

**Une seule destination réseau.**

- `shouldOverrideUrlLoading` et `shouldInterceptRequest` bloquent toute URL qui n'a pas exactement
  l'origine `https://<hôte>:<port>` saisie. Seuls `data:` et `blob:` restent permis : ils sont locaux.
- L'adresse doit être sur le réseau local, ce qui est vérifié après résolution DNS : IP privées
  (10/8, 172.16/12, 192.168/16), lien-local, boucle locale ou IPv6 ULA.
- Safe Browsing et les statistiques d'usage de la WebView sont désactivés (manifeste et réglages) :
  la WebView ne contacte pas Google.
- Aucune dépendance : ni AndroidX, ni Firebase, ni services Google, ni bibliothèque de mesure ou de
  rapport de plantage. Seuls le framework Android et la bibliothèque standard Kotlin sont utilisés.
- Le bloc de métadonnées de dépendances destiné à Google Play n'est pas inclus dans l'APK.

**Trafic en clair interdit** (`usesCleartextTraffic="false"`, `network_security_config.xml`). Le PoC
sert déjà en HTTPS en mode `--lan`, le HTTP n'est donc jamais nécessaire.

**Import de fichier.** L'appli n'a pas d'écran d'import : c'est le `<input type="file">` de la page
du PC. `onShowFileChooser` ouvre le sélecteur de documents d'Android (`ACTION_GET_CONTENT`, sans filtre de
type, car certains formats audio n'ont pas de type MIME connu du téléphone : la page vérifie l'extension).
Le fichier choisi est lu par la WebView et envoyé uniquement au PC (`/api/import`). Aucune permission
de stockage n'est demandée. `allowContentAccess` reste désactivé : il concerne le chargement d'URL
`content://` par la page, pas la lecture du fichier choisi (à confirmer sur téléphone, voir plus bas).

**Micro.** `RECORD_AUDIO` est demandé à l'exécution, au premier appui sur Enregistrer.
`onPermissionRequest` n'accorde que `RESOURCE_AUDIO_CAPTURE`, et seulement à l'origine configurée.
Toute autre demande (caméra, autre origine) est refusée. Si le micro est refusé définitivement, l'appli
propose d'ouvrir les paramètres.

**Données locales.** Adresse, jeton et empreintes sont dans le stockage privé de l'appli. Ils sont
exclus des sauvegardes cloud et des transferts d'appareil (`allowBackup="false"`,
`data_extraction_rules.xml`). Le débogage de la WebView est désactivé.

## Signature

Le dépôt est public : aucune clé privée n'y est commitée. Par défaut, le workflow génère à chaque
exécution une **clé de TEST** (`keytool`, RSA 3072, dans le runner), signe l'APK, puis supprime le
fichier. Chaque version a donc une signature différente, et Android refuse de l'installer par-dessus
la précédente. **Il faut désinstaller l'ancienne version avant d'installer la nouvelle**, ce qui efface
l'adresse et l'empreinte enregistrées.

Alternative écartée : commiter un keystore de test « non secret ». Les mises à jour seraient possibles
sans désinstaller, mais n'importe qui pourrait signer avec cette clé une fausse mise à jour. Elle
s'installerait par-dessus Scribe et récupérerait son stockage (jeton, empreintes).

Amélioration possible, sans secret dans le dépôt : le propriétaire crée une clé stable sur une machine
de confiance et l'ajoute dans les **secrets GitHub Actions** du dépôt (`SCRIBE_KEYSTORE_BASE64`,
`SCRIBE_KEYSTORE_PASSWORD`, `SCRIBE_KEY_ALIAS`, `SCRIBE_KEY_PASSWORD`). Le workflow l'utilise alors
automatiquement, et les versions suivantes s'installent par-dessus.

La release indique l'empreinte SHA-256 de l'APK et celle du certificat de signature.

## Côté PC : le panneau « Connecter le téléphone »

L'appli n'a pas besoin de connaître autre chose que ce que le panneau affiche. Le serveur se lance
normalement (`run.py`, page sur `http://127.0.0.1:8765`, rien d'exposé). **Un clic** sur le bouton de
la page du PC appelle `POST /api/phone/enable` (`scribe/server.py`, `scribe/phone_access.py`), qui ouvre
l'accès téléphone sans redémarrage, puis affiche :

- **QR code** de l'adresse complète, en SVG généré par `segno` (bibliothèque Python pure, installée dans le
  `.venv`). Le scan n'est pas pris en charge par l'appli : on lit le QR avec l'appareil photo du téléphone et
  on colle le lien dans l'appli.
- **Adresse complète** `https://<ip-privée>:<port>/?t=<jeton>` : exactement le format lu par
  `ServerAddress.parse` (HTTPS, hôte privé, jeton `[A-Za-z0-9_-]{8,128}`). Aucune modification de l'appli
  n'a été nécessaire : elle acceptait déjà l'adresse complète dans un seul champ.
- **Empreinte SHA-256** du certificat réellement présenté (même format `AB:CD:…` que `Tls.forDisplay`) ;
  le PC la vérifie en se connectant à sa propre adresse juste après l'ouverture.

Ouverture à chaud (`PhoneAccess` dans `scribe/phone_access.py`) :

- un second `uvicorn.Server` démarre dans un fil d'exécution du même processus : même application, même
  modèle déjà chargé (pas de rechargement, `lifespan="off"`) ;
- il écoute sur **une seule adresse privée** choisie parmi les interfaces du PC (jamais `0.0.0.0`, adresses
  non privées refusées), en HTTPS avec le certificat de `certs/` (recréé, comme `--new-cert`, si l'adresse
  n'y figure pas), sur le port de la page si possible, sinon sur un port libre proche
  (`SO_EXCLUSIVEADDRUSE`, pour ne jamais partager un port pris) ;
- jeton tiré à l'ouverture (`secrets.token_urlsafe`), gardé en mémoire seulement ; journal d'accès coupé ;
- arrêt après 30 min (`SCRIBE_PHONE_MINUTES`), sur « Arrêter l'accès téléphone » ou à l'arrêt du serveur ;
  « Prolonger » repousse l'échéance. Après l'arrêt, les connexions sont refusées.

Les requêtes de ce second point d'accès sont marquées dans le scope ASGI (marque posée côté serveur, que
le client ne peut pas imiter). Elles doivent avoir le jeton, l'hôte exact `<ip>` et une origine cohérente,
et seules ces routes y répondent : `/`, `/static/*`, `/api/status`, `/api/transcribe`, `/api/import`,
`/api/jobs/*`.

**Accès au panneau restreint au PC.** Les routes `/api/phone*` (`GET /api/phone`, `POST
/api/phone/enable|extend|disable|token`) refusent toute requête arrivée par le point d'accès téléphone,
dont l'adresse du client n'est pas `127.0.0.1`/`::1`, ou dont l'en-tête `Host` n'est pas
`localhost`/`127.0.0.1` (`uvicorn` tourne avec `proxy_headers=False`, donc `X-Forwarded-For` est ignoré).
Réponses en `Cache-Control: no-store`. En mode `run.py --lan`, le bouton n'ouvre rien de plus : il affiche
directement le lien du serveur déjà joignable.

Effet côté appli : l'empreinte est épinglée par couple hôte:port. Si l'accès s'ouvre sur un autre port
(port de la page déjà pris) ou si le certificat est recréé, l'appli redemande la comparaison.

## Compilation

- Déclenchement : push d'un tag `vX.Y.Z`, qui publie la release « Scribe vX.Y.Z (PoC) » avec
  `scribe-vX.Y.Z.apk` et son `.sha256`. `workflow_dispatch` compile sans publier.
- Deux jobs :
  - `build` (lecture seule du dépôt) compile, lance le lint Android et signe ;
  - `release`, seul job avec `contents: write`, publie avec le `GITHUB_TOKEN` et l'outil `gh` du runner.
- Versions : Gradle 8.11.1, Android Gradle Plugin 8.7.3, Kotlin 2.0.21, JDK 17. Le wrapper est vérifié
  par `gradle/actions/wrapper-validation`, la distribution par SHA-256. Cette combinaison a été choisie
  pour sa stabilité plutôt que pour sa nouveauté.
- `versionName` vient du tag, `versionCode` du numéro d'exécution du workflow.

Compiler localement, si un JDK 17 et le SDK Android sont disponibles : `cd android && ./gradlew assembleRelease`.
Sans variables `SCRIBE_KEYSTORE*`, l'APK produit n'est pas signé.

## Limites

- **Écran éteint.** `FLAG_KEEP_SCREEN_ON` garde l'écran allumé tant que la page est affichée. Si l'écran
  est verrouillé ou l'appli mise en arrière-plan, Android peut couper le micro de la WebView.
  L'enregistrement en arrière-plan (service au premier plan) est hors périmètre.
- **Jeton.** Il change à chaque ouverture de l'accès téléphone (et à chaque lancement de `run.py --lan`) :
  il faut recoller le lien dans l'appli. L'accès s'arrête au bout de 30 min sauf prolongation.
- **Pare-feu Windows.** À la première ouverture, Windows peut demander d'autoriser Python sur le réseau
  (administrateur parfois nécessaire sur un poste d'entreprise). Le PC ne peut pas détecter ce blocage.
- **Même réseau.** Les Wi-Fi d'entreprise ou invités isolent souvent les appareils (voir le README).
- **Pas de mode hors ligne.** Sans le PC, l'appli n'a aucune fonction.

## À tester sur un vrai téléphone

Rien de ce qui suit n'a pu être testé ici : il n'y a ni téléphone ni émulateur sur le poste.

1. Installation de l'APK depuis la page Releases (autorisation de la source, Play Protect).
2. Clic sur « Connecter le téléphone » sur le PC, lecture du QR code avec l'appareil photo, collage du
   lien dans l'appli ; puis saisie de l'adresse et du jeton séparés. Invite du pare-feu Windows au
   premier raccordement.
3. Affichage de l'empreinte et égalité avec celle du panneau.
4. Chargement de l'interface dans la WebView après confirmation : le certificat épinglé est-il bien
   accepté par `onReceivedSslError`, sans écran blanc ?
5. Micro : demande Android, puis Enregistrer / Arrêter et transcription affichée. Vérifier que
   l'AudioWorklet fonctionne dans la WebView.
6. Import : toucher la zone « Importer un fichier audio » ouvre le sélecteur Android, le nom et la taille s'affichent, la durée
   est lue, puis « Transcrire ce fichier » envoie le fichier avec la barre de progression. Si le fichier
   n'est pas lisible par la WebView, activer `allowContentAccess` est la piste à tester en premier.
7. Erreurs :
   - PC éteint : « PC injoignable » ;
   - mauvais jeton : « Jeton refusé » ;
   - micro refusé ;
   - PC relancé avec `--new-cert` : « Certificat du PC changé » ;
   - accès téléphone arrêté (bouton ou échéance) : « PC injoignable » ; rouvert : « Jeton refusé »
     tant que le nouveau lien n'est pas collé.
8. Rotation de l'écran pendant un enregistrement (elle ne doit pas l'interrompre) ; écran qui reste allumé.
9. Android 15 : marges des barres système (contenu non masqué).
