# PoC Scribe réunions — décisions, mesures, suite

Date : 28/10/2026. Toutes les mesures ci-dessous ont été réellement exécutées sur le poste de
développement. Ce qui n'a pas pu être testé est listé explicitement en section 5.

## 1. Vérifications préalables

### 1.1 Modèles Nemotron ASR sur Hugging Face

Liste interrogée via l'API Hugging Face le 28/10/2026 :

| Modèle | Créé le | Dernière révision | Format | Taille | Français | Licence |
|---|---|---|---|---|---|---|
| `nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B` | 07/10/2026 | 28/10/2026 | safetensors (NeMo) | **67,5 Go** | oui (40 langues) | OpenMDW-1.1 |
| `nvidia/nemotron-labs-unified-asr-0.6b` | 21/08/2026 | 27/10/2026 | **.nemo seulement** | 2,5 Go | oui (25 langues européennes) | OpenMDW-1.1 |
| `nvidia/nemotron-3.5-asr-streaming-0.6b` | 15/05/2026 | 10/09/2026 (`ea30d66`) | safetensors 2,55 Go, .nemo 2,37 Go, **GGUF q8_0 742 Mo** | 5,7 Go au total | oui (35 langues, français en niveau 1) | OpenMDW-1.1 |

**Choix : `nemotron-3.5-asr-streaming-0.6b`.**

- **Le 30B « Transcribe »** est le plus récent, mais il pèse 67,5 Go et cible le GPU. Il est inutilisable ici (16 Go de RAM, pas de GPU), et a fortiori sur un téléphone.
- **Le « labs unified 0.6B »** n'existe qu'au format `.nemo`. Il exige la boîte à outils NVIDIA NeMo, qui n'est pas prise en charge officiellement sous Windows. « labs » signifie expérimental. Sa fiche annonce un WER français moyen de 5,53 hors streaming, moyenne de FLEURS, MCV et MLS, ce qui n'est pas directement comparable au 9,03 sur FLEURS du modèle choisi. C'est un candidat à réévaluer.
- **Le 3.5 streaming 0.6B** fonctionne avec Transformers (≥ 5.13) sur CPU, avec une simple installation pip, sans compilation ni NeMo.

Le gestionnaire de modèle suit toujours **la dernière révision** du dépôt configuré. On change de dépôt avec `SCRIBE_MODEL_ID`.

### 1.2 GGUF : oui, il existe

Contrairement à ce que supposait la demande, le dépôt du 3.5 streaming publie
`nemotron-3.5-asr-streaming-0.6b.q8_0.gguf` (742 Mo). Il est destiné à
[NeMo-Speech.cpp](https://github.com/NVIDIA/NeMo-Speech.cpp) (C++/GGML).

Il n'est pas utilisé dans ce PoC, pour deux raisons :

- il faut compiler un programme C++, ce qui demande une chaîne de compilation que je n'ai pas installée (pas d'installation système) ;
- Transformers est plus simple à mettre en place dans un environnement isolé.

Le GGUF reste intéressant pour la suite : il est 3,4 fois plus petit que le safetensors F32 et GGML tourne sur le processeur d'un téléphone. Cette piste n'a pas été testée.

### 1.3 Matériel de ce poste

| | |
|---|---|
| Processeur | Intel Core i7-1165G7 (4 cœurs / 8 threads, 2021) |
| GPU | Intel Iris Xe uniquement : **pas de GPU NVIDIA, pas de CUDA** (`nvidia-smi` absent) |
| RAM | 15,7 Go, dont 0,6 à 4 Go libres selon le moment |
| Disque | 50 Go libres |
| Python | 3.13.13 |

Conséquence : le modèle tourne en F32 sur le processeur, avec PyTorch 2.15 CPU. C'est suffisant pour transcrire après la réunion (voir mesures). Le GPU n'est pas nécessaire.

## 2. Architecture du PoC

```
Navigateur (PC ou téléphone)                     PC
 ┌───────────────────────────┐   WAV 16 kHz   ┌─────────────────────────────────────┐
 │ Bouton Enregistrer/Arrêter│ ─────────────► │ run.py (FastAPI, Python, .venv/)    │
 │ micro → AudioWorklet      │   (réseau      │  ├ ModelManager → Hugging Face      │
 │ → 16 kHz PCM → WAV        │    local)      │  │  (seul flux sortant)             │
 │ affichage transcription   │ ◄───────────── │  ├ Transcriber : Nemotron, CPU      │
 └───────────────────────────┘    texte       │  └ data/<date>/ audio + texte       │
                                              └─────────────────────────────────────┘
```

Le choix recommandé dans la demande est validé : un serveur Python local et une page web unique, servie au PC (localhost) et au téléphone (HTTPS sur le réseau local).

- **Aucun ffmpeg à installer.** Le navigateur produit lui-même un WAV 16 kHz mono : il capte le micro, rééchantillonne à la volée et encode, en JavaScript. Pour l'import de fichiers (mp3, m4a, ogg, flac, mp4…), le serveur décode avec PyAV, dont les roues embarquent FFmpeg (voir la section 8).
- **Longs enregistrements.** L'audio est découpé en segments d'environ 30 s, coupés sur le passage le plus silencieux, ce qui borne la mémoire de calcul.
- **Une transcription à la fois.** Un deuxième envoi pendant un calcul reçoit un refus explicite.
- **Mode téléphone (`--lan`).** Certificat auto-signé généré en Python (`cryptography`, sans OpenSSL système) et jeton d'accès aléatoire. Par défaut, l'application n'écoute que sur 127.0.0.1.
- **Contrôle d'accès.** Le nom d'hôte et l'origine des requêtes sont vérifiés, pour qu'une autre page web ouverte dans le navigateur ne puisse pas utiliser l'API locale.
- **Mise à jour du modèle.** Chaque révision est rangée dans `models/<dépôt>/<sha>/`. Le passage d'une révision à l'autre est atomique (via `state.json`). Si la nouvelle révision ne se charge pas, l'application revient à l'ancienne et supprime la révision ratée. L'ancienne révision est supprimée après une bascule réussie.
- **Réseau.** Les fichiers du modèle sont servis par les domaines de Hugging Face (`huggingface.co` et ses CDN `*.hf.co`). Une liste blanche de pare-feu doit inclure les deux.

**Ce que le PoC prouve :**

- Nemotron 3.5 transcrit correctement le français sur un PC portable, sans GPU et hors ligne.
- Le parcours « Enregistrer → Arrêter → texte » fonctionne de bout en bout.
- Le modèle est géré par révision, avec mise à jour manuelle ou automatique.

**Ce qu'il ne prouve pas :** la transcription embarquée sur le téléphone. En mode téléphone, l'audio quitte le téléphone pour aller sur le PC, par le réseau local, sans jamais sortir vers Internet. La vitesse, la mémoire, la batterie et la chaleur sur mobile restent inconnues.

## 3. Mesures (réellement exécutées)

Échantillon :

- 75,4 s de parole française, générées par la voix de synthèse Windows locale « Hortense » ;
- texte d'une réunion fictive, dans `tests/samples/reunion_fr.txt` ;
- aucune donnée personnelle.

| Mesure | Résultat |
|---|---|
| Téléchargement du modèle (2,55 Go) | environ 1 min 40 s puis environ 2 min 45 s (2 essais, débit environ 16 à 35 Mo/s) |
| Chargement du modèle en mémoire | 21,9 s (environ 20 s en conditions réelles dans l'application) |
| Transcription de 75,4 s d'audio, banc `scripts/bench.py` | 25,6 s au premier passage, puis 21,8 s, soit un **RTF de 0,34 puis 0,29** |
| Même transcription via l'application (API), 4 essais | 22,1 s, 18,8 s, 15,6 s (le temps varie avec la charge du PC) |
| Même audio passé par le navigateur, en simulation de micro | 1 min 34 s enregistrées (dont environ 18 s de silence final), transcrites en 32,1 s |
| Mémoire du processus, banc | 2,8 Go après chargement, **pic de 3,1 Go**, 3,35 Go en mémoire privée |
| Mémoire du processus, serveur | environ 3,3 Go en mémoire privée |
| **WER sur l'échantillon** | **1,05 %** (2 erreurs sur environ 190 mots, minuscules et sans ponctuation) |
| 2 s de silence | texte vide, aucune hallucination |

Qualité observée :

- **Accords oubliés.** « présent » au lieu de « présents », « prévues » au lieu de « prévu ».
- **Ponctuation perdue.** Deux-points et point d'interrogation disparus (« Avez vous des questions si ce n'est… »).
- **Majuscules.** Une majuscule apparaît parfois après un point manquant.

Le texte reste très lisible.

**Attention :** une voix de synthèse lue proprement est le cas le plus favorable. La fiche officielle donne un WER de 9 à 11 % sur FLEURS français. En vraie réunion (bruit, voix superposées, micro posé sur la table), il faut s'attendre à un taux nettement plus élevé. Ce point n'est pas mesuré.

Extrapolation, non mesurée : 1 h de réunion demanderait environ 15 à 20 min de calcul sur ce PC.

## 4. Ce qui a été testé et fonctionne

- **Installation isolée.** Tout est dans `.venv/` (1,3 Go). Le cache pip est désactivé et le cache Hugging Face redirigé dans `models/`. Rien n'est écrit hors du dossier du projet, ni installé au niveau du système.
- **Premier lancement.** Téléchargement automatique, barre de progression de 0 à 2,55 Go, chargement, puis « Prêt ».
- **Interface web dans Chrome.** Le bouton Enregistrer fonctionne, ainsi que le chronomètre, l'envoi, la progression par segment, l'affichage du texte et l'enregistrement dans `data/`.
- **Bouton « Mettre à jour le modèle ».** Quand le modèle est déjà à jour, il affiche « Le modèle est à jour » et met à jour la date de vérification.
- **Mise à jour automatique (`SCRIBE_AUTO_UPDATE=download`)**, avec une ancienne révision simulée :
  1. l'ancienne révision reste utilisable pendant le téléchargement ;
  2. la nouvelle est téléchargée ;
  3. l'application bascule et recharge le modèle ;
  4. l'ancienne révision est supprimée.
- **Hors ligne, simulé par un proxy injoignable.**
  - Au démarrage, le modèle local est chargé et le message « Hors ligne : vérification impossible » s'affiche.
  - Le bouton de mise à jour donne un message clair.
  - La transcription fonctionne.
- **HTTPS et jeton.**
  - Le certificat généré est valide pour localhost et les IP locales (vérifié, pas contourné).
  - Sans jeton ou avec un mauvais jeton : refus (403).
  - Avec le bon jeton : la page s'ouvre (200) et un cookie est posé.
- **Garde-fous.**
  - Hôte usurpé : refus (403).
  - Envoi depuis une autre origine : refus (403).
  - WAV à en-tête invalide : erreur 400 lisible.
  - Deuxième envoi simultané : 429 avec un message.
  - Les requêtes de la page elle-même passent (200).

Défauts trouvés pendant les tests ou par une relecture du code, puis corrigés :

- **Barre de progression bloquée à 0.** Les fichiers temporaires du hub dépassent la limite Windows de 260 caractères. Correction : chemins longs avec le préfixe `\\?\`.
- **Doubles espaces** entre les segments du texte.
- **API utilisable par n'importe quelle page web ouverte** dans le navigateur. Correction : contrôle de l'hôte et de l'origine.
- **Tâche bloquée en « en cours ».** Elle le restait si l'écriture du texte échouait.
- **En-tête WAV aberrant** qui faisait planter la requête.
- **Retour arrière incomplet** après l'échec de chargement d'une nouvelle révision.
- **Écritures concurrentes** de `state.json`.

## 5. Ce qui n'a PAS été testé

- **Un vrai téléphone.** Ni le mode `--lan` depuis un téléphone, ni le pare-feu Windows (qui peut exiger un administrateur), ni l'isolement du Wi-Fi d'entreprise. J'ai testé HTTPS et le jeton sur 127.0.0.1 pour ne pas déclencher la fenêtre du pare-feu.
- **Un vrai micro.** Le navigateur de test n'en a pas. Le micro a été simulé en injectant l'échantillon audio dans la page. Le code de capture est le même, mais pas la source. Il n'y a donc pas eu de vrai refus de micro : les messages d'erreur (refusé, absent, occupé) sont codés, pas vérifiés.
- **Un enregistrement long** (1 h ou plus). Seules 75 s et 1 min 34 s ont été testées.
- **Le cas « mémoire insuffisante ».** Il est géré par message, mais n'a pas été provoqué.
- **Le retour arrière** après l'échec de chargement d'une nouvelle révision. Il est codé, mais pas provoqué.
- **Firefox et Safari** (iOS ou macOS).
- **Le GGUF et NeMo-Speech.cpp, le modèle « labs unified », l'ONNX et sherpa-onnx.**

## 6. Voie « modèle sur le téléphone » (évaluée, non construite)

| Option | Faisabilité | Remarques |
|---|---|---|
| Nemotron 3.5 via sherpa-onnx | Plausible, non prouvée | sherpa-onnx le prend en charge depuis juin 2026 (master). Les exports ONNX communautaires sont en FP32 (2,59 Go) : **il faut produire un int8 nous-mêmes** (environ 650 à 750 Mo) puis mesurer RTF, RAM et chaleur. |
| Nemotron 3.5 GGUF q8 via NeMo-Speech.cpp | Inconnue | Le fichier de 742 Mo existe. Il faut vérifier que la bibliothèque se compile pour Android (NDK) et que le streaming y fonctionne. |
| **Parakeet TDT 0.6B v3 int8 via sherpa-onnx** | **La plus sûre** | Paquet officiel de 640 Mo, déjà utilisé en production sur Android pour du français. WER français publié meilleur : FLEURS 5,15 contre 9,0 pour Nemotron. Horodatage au mot. |

Coût estimé pour un PoC Android (estimation, non vérifiée) :

- application Flutter ou Kotlin avec `sherpa_onnx` ;
- service de premier plan « micro » ;
- même gestionnaire de modèle (API Hugging Face, révision, mise à jour) ;
- export int8 et mesures sur 2 téléphones.

Total : **environ 2 à 4 semaines** pour une personne. La logique de gestion du modèle et le parcours utilisateur de ce PoC se reprennent tels quels. Seuls le moteur et l'enregistrement changent.

## 7. Décision à prendre

1. **Moteur.**
   - **Rester sur Nemotron**, ce qui implique un export int8 et une mesure sur téléphone ;
   - ou **basculer sur Parakeet v3** : meilleur WER français, déjà empaqueté pour mobile.

   Ma recommandation, cohérente avec l'étude : mesurer les deux sur 3 à 5 vraies réunions enregistrées au téléphone, avec le PoC actuel pour Nemotron, avant de choisir.
2. **Cible.**
   - **Mode PC + téléphone-micro**, ce PoC, utilisable tout de suite ;
   - ou **transcription embarquée sur le téléphone** (section 6).
3. **Données réelles.** Fournir des enregistrements de réunions autorisés pour mesurer la qualité réelle.

## 8. Import d'un fichier audio (ajout)

Ajouté après le PoC : `POST /api/import` reçoit le fichier brut (en flux, écrit sur disque dans `data/` sans le charger en mémoire), le valide (durée et format lus dans l'en-tête), puis le décode et le transcrit en arrière-plan avec le même moteur que l'enregistrement. Mode d'emploi, formats et limites : voir le README.

- **Décodage : PyAV.** Choisi plutôt que soundfile + une autre bibliothèque : une seule dépendance, des roues Windows autonomes (FFmpeg embarqué, aucun droit administrateur), tous les formats courants y compris l'audio d'un mp4. Sortie : int16 mono 16 kHz (460 Mo pour 4 h), converti segment par segment.
- **Mesures** (échantillon de 75 s, i7 portable, CPU) : l'import d'un WAV, mp3, flac, wma, ogg, opus, m4a, aac, webm ou mp4 (avec vidéo) produit les mêmes 181 mots que l'enregistrement. WAV, WAV 44,1 kHz stéréo, mp3, flac et wma donnent un texte strictement identique. Les autres formats ne diffèrent que par la ponctuation ou une majuscule (par exemple « mars. L'équipe » devenu « mars, l'équipe »). Temps de calcul : environ 0,2 à 0,3 × la durée ; le premier import après démarrage est plus lent (échauffement du modèle).
- **Refus vérifiés :** fichier vide, texte renommé en .mp3, extension inconnue, trop gros (avec ou sans `Content-Length`), nom d'hôte ou origine étrangers, liste HLS déguisée en .mp3, nom de fichier avec traversée de chemin, deuxième import ou enregistrement pendant un import.
- **Non testé :** fichiers de plusieurs heures ou de plusieurs centaines de Mo (seuls 75 s ont été importés ; la limite de taille a été testée avec un seuil abaissé à 1 Mo), amr, aiff, 3gp, mov, mkv, oga ; navigateurs autres que Chromium ; glisser-déposer réel (testé par sélecteur de fichier uniquement).
