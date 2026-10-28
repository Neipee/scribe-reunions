# 02 – Reconnaissance vocale (ASR) sur l'appareil

Étude documentaire, 27/10/2026. Aucun modèle n'a été téléchargé ni testé : tous les chiffres viennent des sources citées. Les mentions « non vérifié » désignent des chiffres de seconde main (blogs, résumés de recherche, échantillons minuscules) ou des déductions de ma part.

## 1. NVIDIA Nemotron 3.5 ASR Streaming 0.6B

Source principale : [fiche du modèle sur Hugging Face](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b).

| Point | Constat |
|---|---|
| Publication | 04/06/2026 sur HF, version `v1` |
| Taille | 600 M paramètres. Fichiers : `model.safetensors` 2,55 Go (F32), `.nemo` 2,37 Go, **GGUF q8_0 742 Mo** ([liste des fichiers](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/tree/main)) |
| Architecture | FastConformer *cache-aware* (24 couches) + décodeur RNNT, conditionné par un vecteur de langue (« prompt »). Conçu pour le **streaming natif** : les états d'attention et de convolution sont mis en cache, rien n'est recalculé |
| Langues | 40 locales en 3 niveaux. **Le français (fr-FR, fr-CA) fait partie du niveau 1, « transcription-ready »** (15 langues). Détection automatique possible (`target_lang=auto`) |
| Ponctuation / majuscules | Oui, intégrées |
| Horodatage | Non documenté (question ouverte, [discussion #14](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/discussions)) |
| Licence | OpenMDW-1.1, « ready for commercial use » selon la fiche |
| Taille de bloc / latence | 80, 160, 320, 560 ou 1 120 ms (`att_context_size` [56, 0/1/3/6/13]) |
| Matériel cible officiel | GPU NVIDIA (Volta à Blackwell, Jetson), Linux. Benchmarks sur H100. **Rien d'officiel sur CPU ni sur mobile** |
| Runtimes | NeMo 26.06, Transformers ≥ 5.13, [NeMo-Speech.cpp](https://github.com/NVIDIA/NeMo-Speech.cpp) (C++/GGML, GGUF) |

### WER sur FLEURS (fiche officielle, mode LangID)

| Langue | 80 ms | 160 ms | 320 ms | 560 ms | 1,12 s |
|---|---|---|---|---|---|
| **Français** | 10,97 | 10,60 | 9,79 | 9,45 | **9,03** |
| Anglais | 9,43 | 8,88 | 8,27 | 7,99 | 7,91 |
| Allemand | 9,81 | 9,21 | 8,83 | 8,42 | 8,31 |

En détection automatique, le français est quasi identique (11,03 → 9,02). La fiche signale que la normalisation du texte est imparfaite et peut gonfler les taux d'erreur.

### Portage hors GPU (ONNX, sherpa-onnx, Apple)

- **ONNX** : export communautaire par altunenes ([parakeet-rs](https://huggingface.co/altunenes/parakeet-rs/tree/main/nemotron-3.5-asr-streaming-0.6b-onnx), [script](https://github.com/altunenes/parakeet-rs/blob/master/scripts/export_nemotron_streaming_multilingual.py)), signalé dans la [discussion #1](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/discussions/1). Autre export : [pantinor/nemotron-3.5-asr-streaming-0.6b-onnx](https://huggingface.co/pantinor/nemotron-3.5-asr-streaming-0.6b-onnx/tree/main), **2,59 Go (FP32, aucune version int8 publiée)**.
- **sherpa-onnx** : pris en charge sur la branche master depuis le 12/06/2026 ([issue #3664](https://github.com/k2-fsa/sherpa-onnx/issues/3664), [PR #3671](https://github.com/k2-fsa/sherpa-onnx/pull/3671)) via le chemin *online transducer NeMo*. La langue se passe en chaîne par flux (chaîne vide = détection auto). À la date de l'issue, aucun paquet int8 officiel k2-fsa n'était cité (non vérifié depuis).
- **CPU** : témoignages « très rapide même sur CPU » ([discussion #1](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/discussions/1)), utilisation dans un assistant vocal hors ligne sur CPU ([discussion #33](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/discussions/33)). Aucune mesure de RTF ni de RAM.
- **iOS** : la [PR communautaire #31](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/discussions/31) décrit une conversion Apple Core AI (`.aimodel`, iOS 27 / macOS 27) : **environ 53 ms par bloc de 320 ms sur iPhone 17 Pro**, soit un RTF d'environ 0,17. Non fusionnée et non vérifiée, iPhone haut de gamme uniquement.
- **Android** : aucun chiffre publié. Une app (Anti-Vocale) l'intègre via le paquet Flutter de sherpa-onnx ([issue #3664](https://github.com/k2-fsa/sherpa-onnx/issues/3664)).

### Faisabilité sur téléphone

- Une **conversion int8 est indispensable**. Pour un modèle de 0,6 B paramètres, on peut s'attendre à environ 650–750 Mo, comme le GGUF q8_0 (742 Mo) ou Parakeet v3 int8 (640 Mo). C'est une estimation, non vérifiée pour un export ONNX int8 de Nemotron.
- RAM probable en fonctionnement : environ 1 Go ou plus (non vérifié).
- C'est plausible sur un téléphone haut ou milieu de gamme récent, mais **rien n'est mesuré sur Android**, et la chaîne d'export est communautaire et récente (juin 2026).

## 2. Alternatives locales

### Tableau comparatif (français)

| Moteur | Paramètres / taille sur disque | WER français publié | Mode | Android | iOS | Licence |
|---|---|---|---|---|---|---|
| **Nemotron 3.5 ASR 0.6B** | 0,6 B ; GGUF q8 742 Mo ; ONNX FP32 2,59 Go | FLEURS **9,0** (1,12 s) à 11,0 (80 ms) | Streaming natif | sherpa-onnx (master, communautaire), sans chiffres | Core AI communautaire (53 ms par bloc de 320 ms, iPhone 17 Pro) | OpenMDW-1.1 (commerciale OK) |
| **Parakeet TDT 0.6B v3** | 0,6 B ; **int8 sherpa-onnx 640 Mo** ; variante int4 environ 410 Mo | FLEURS **5,15** ; MLS 4,97 ; CoVoST 6,05 | Batch (streaming simulé via VAD) ; jusqu'à 3 h en attention locale (GPU) | sherpa-onnx officiel, APK de démo | CoreML (FluidAudio), ONNX | CC-BY-4.0 |
| Canary 180M Flash | 182 M ; int8 environ 154 Mo | MLS 4,75 ; Common Voice 16.1 8,19 | Batch, < 40 s par segment | sherpa-onnx | sherpa-onnx | CC-BY-4.0 |
| Canary 1B v2 | 1 B ; int8 environ 1,4 Go | moyenne 25 langues environ 8,1 (FR dans l'annexe du papier) | Batch | sherpa-onnx (communautaire) | — | CC-BY-4.0 |
| Whisper large-v3-turbo | 809 M ; environ 1,5 Go F16, q5 environ 550 Mo (non vérifié) | FLEURS environ 5,4 (normaliseur Open ASR) ; Québec 8,2 | Batch (fenêtres de 30 s) | whisper.cpp / sherpa-onnx, lent | **WhisperKit** (CoreML compressé 626–954 Mo) | MIT |
| Whisper small | 244 M ; 466 Mo F16, q5_1 181 Mo ; RAM environ 850 Mo | FLEURS environ 15 ; Québec 33 | Batch | whisper.cpp | WhisperKit | MIT |
| Whisper base / tiny | 142 / 75 Mo ; RAM 388 / 273 Mo | nettement plus mauvais (non chiffré ici) | Batch | oui | oui | MIT |
| Voxtral Mini 4B Realtime | environ 4 B ; 9 Go BF16, environ 2,5 Go Q4 | FLEURS 6,42 (480 ms) ; 5,23 (2,4 s) | Streaming | ExecuTorch (lourd) | MLX (lourd) | Apache-2.0 |
| Kyutai STT 1B en_fr | 1 B ; RAM environ 2,5 Go (non vérifié) | FLEURS environ 16,4 (80 clips, non officiel) | Streaming, délai 500 ms | non | MLX | CC-BY-4.0 |
| Vosk fr 0.22 / small fr | 1,4 Go / 41 Mo | CV 14,7 / 24,0 ; MLS 11,6 | Streaming | oui | oui | Apache-2.0 |
| Moonshine | — | **Pas de modèle français officiel** (fine-tune communautaire tiny-fr : 21,8 sur MLS) | Streaming | oui | oui | MIT |
| Android SpeechRecognizer on-device | intégré à l'OS | non publié | Sessions courtes | API 31+, pack fr à télécharger | — | propriétaire |
| Apple SpeechAnalyzer / SpeechTranscriber | intégré à l'OS (iOS 26+) | non publié par Apple | Streaming et fichiers longs | — | **fr-FR, fr-CA, fr-BE, fr-CH** | propriétaire |

Attention : les WER ci-dessus ne sont pas strictement comparables entre eux (normaliseurs différents, ponctuation retirée ou non, jeux de test différents). FLEURS est de la parole lue et propre : en réunion réelle (bruit, chevauchements, micro de téléphone posé sur la table), il faut s'attendre à des taux 2 à 3 fois plus élevés (estimation, non vérifiée).

### Notes par moteur

- **Parakeet TDT 0.6B v3** ([fiche](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), [papier](https://arxiv.org/abs/2509.14128)) : 25 langues européennes, français compris, ponctuation et horodatage au mot. C'est le meilleur WER français publié parmi les modèles légers. Il est empaqueté officiellement par sherpa-onnx ([doc NeMo transducer](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html) : encoder.int8 622 Mo, decoder 12 Mo, joiner 6 Mo) et déjà utilisé en production sur Android par un clavier français ([La Touche Carré](https://huggingface.co/LaToucheCarre/Parakeet-TDT-0.6B-v3-int8-ONNX)). Vitesse sur téléphone : RTF 0,12 sur un téléphone non précisé selon [Soniqo](https://soniqo.audio/guides/parakeet/android) (non vérifié). Sur desktop, environ 16× le temps réel en sherpa-onnx int8 et environ 105× en CoreML (FluidAudio) sur un M5 ([BenchLM](https://benchlm.ai/models/parakeet-tdt-0-6b-v3), non vérifié). Il existe aussi une variante post-entraînée « Parakeet Ultra » (FLEURS fr 9,6 → 7,9 sur 50 clips seulement : [dictus-android #122](https://github.com/getdictus/dictus-android/issues/122), non significatif).
- **Canary** ([180M Flash](https://huggingface.co/nvidia/canary-180m-flash)) : bon en français pour sa taille (MLS 4,75), mais limité à 40 s par segment, ce qui impose un découpage. sherpa-onnx ≤ 1.13.8 n'accepte que en/es/de/fr. Le français fonctionne donc. Canary 1B v2 ([export int8](https://huggingface.co/fussraider/canary-1b-v2-sherpa-onnx-int8)) est trop gros pour un usage mobile courant.
- **Whisper** ([whisper.cpp](https://github.com/ggml-org/whisper.cpp), [poids GGML](https://huggingface.co/ggerganov/whisper.cpp), [turbo](https://huggingface.co/openai/whisper-large-v3-turbo)) : turbo est bon en français (environ 5,4 sur FLEURS selon la [fiche d'un fine-tune](https://huggingface.co/Mathos34400/whisper-large-v3-turbo-french-v6) ; 8,2 sur un corpus québécois de commissions publiques, contre 10,7 pour medium et 33,0 pour small : [arXiv 2508.21193](https://arxiv.org/pdf/2508.21193)). Il est lourd sur Android, faute d'accélération NPU standard dans whisper.cpp. Sur iOS, [WhisperKit / argmax-oss-swift](https://github.com/argmaxinc/argmax-oss-swift) le fait tourner sur l'ANE (environ 2,4× à 5,5× le temps réel sur iPhone 15 Pro Max selon la variante, chiffres Argmax 2024). La v1.1.0 (08/2026) réduit de plus de 70 % la mémoire de pointe sur des fichiers de 3 h. Les hallucinations de Whisper sur les silences et les répétitions sont un risque connu pour les longues réunions (non vérifié ici). Small, base et tiny sont trop faibles en français pour des comptes rendus.
- **Voxtral Mini 4B Realtime** ([fiche](https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602)) : excellent en français (6,42 à 480 ms), Apache-2.0, mais environ 4 B paramètres (environ 2,5 Go en Q4). Pas réaliste sur un téléphone moyen en 2026 pour 1 à 2 h d'audio. Voxtral 3 (10/2026) est disponible uniquement par API ([Mistral](https://mistral.ai/news/voxtral-3/)).
- **Kyutai STT 1B en_fr** ([Kyutai](https://kyutai.org/stt/), [dépôt](https://github.com/kyutai-labs/delayed-streams-modeling/)) : bilingue anglais et français, streaming avec VAD sémantique. Côté appareil, il ne fonctionne qu'en MLX (Apple). Un seul chiffre français, non officiel : 16,4 sur 80 clips ([port MLX](https://huggingface.co/aufklarer/Kyutai-STT-1B-MLX-FP16)). Non retenu.
- **Vosk** ([modèle français](https://alphacephei.com/nsh/2020/10/21/french.html), [WER et tailles](https://whipscribe.com/tools/vosk)) : léger (41 Mo) et vraiment hors ligne, mais nettement moins précis (24 sur Common Voice pour le petit modèle). Pas de ponctuation (non vérifié). Utile seulement comme secours de très bas niveau.
- **Moonshine** ([papier v2](https://arxiv.org/html/2602.12241v1)) : la v2 est en anglais uniquement, et les modèles monolingues ne couvrent pas le français. Fine-tune communautaire [moonshine-tiny-fr](https://huggingface.co/Cornebidouil/moonshine-tiny-fr) à 21,8 sur MLS. Non retenu.
- **Android SpeechRecognizer on-device** ([API](https://developer.android.com/reference/android/speech/SpeechRecognizer)) : `createOnDeviceSpeechRecognizer` (API 31+). Le pack français doit être installé, sinon l'appel échoue ([nitro-speech #15](https://github.com/NotGeorgeMessier/nitro-speech/issues/15)). L'API est conçue pour des sessions courtes, pas pour l'écoute continue, et ne transcrit pas de fichier ([Picovoice](https://picovoice.ai/blog/android-speech-recognition/)). La qualité varie selon le constructeur. **Inadapté à une réunion de 1 à 2 h.**
- **Apple SpeechAnalyzer / SpeechTranscriber** (iOS 26+) : entièrement local, le modèle de langue étant téléchargé à la demande via AssetInventory. Le français est pris en charge (fr-FR, fr-CA, fr-BE, fr-CH selon [Callstack](https://www.callstack.com/blog/on-device-speech-transcription-with-apple-speechanalyzer) et [Anton Gubarenko](https://antongubarenko.substack.com/p/ios-26-speechanalyzer-guide)), à vérifier avec `supportedLocales`. Pas de détection de langue. Conçu pour l'audio long et coûte zéro octet dans l'app. Apple ne publie aucun WER : un comparatif indépendant juge Whisper plus précis sur certains cas ([LoroNote](https://loronote.com/en/blog/apple-speechanalyzer-vs-whisper), non vérifié).

## 3. Streaming en direct ou traitement par lots, batterie, durée

| | Streaming en direct | Batch après la réunion |
|---|---|---|
| Intérêt | Texte visible pendant la réunion, résultat quasi immédiat à la fin | Meilleure qualité (contexte complet), choix d'un modèle plus gros, diarisation globale |
| Modèles adaptés | Nemotron (natif), Apple SpeechTranscriber, Vosk, Voxtral Realtime (trop lourd) | Parakeet v3, Canary, Whisper turbo / WhisperKit |
| Coût | Le CPU ou NPU tourne pendant toute la réunion. Échauffement prolongé, téléphone souvent branché | Pic de calcul concentré : 1 h d'audio à RTF 0,1–0,2 donne environ 6–12 min de calcul (estimation, non vérifiée sur téléphone) |
| Risque | Service en avant-plan obligatoire (Android : `foregroundServiceType=microphone` ; iOS : mode audio en arrière-plan), sinon l'OS coupe | L'OS peut tuer une tâche longue. Il faut un traitement reprenable, segment par segment, et lancer de préférence en charge |

Recommandations pour les enregistrements de 1 à 2 h :

- **Toujours enregistrer l'audio brut d'abord** (16 kHz mono ; Opus ou AAC environ 30–60 Mo/h, WAV PCM16 environ 115 Mo/h). La transcription devient une étape séparée qu'on peut relancer.
- **Découper avec un VAD** (Silero VAD, intégré à sherpa-onnx) en segments de 10–30 s coupés sur les silences, avec un léger chevauchement si on coupe sans silence. Cela évite la limite de 40 s de Canary et la fenêtre de 30 s de Whisper, borne la RAM, et permet de sauvegarder la progression après chaque segment.
- Parakeet v3 : l'attention complète est limitée à environ 24 min sur un A100 80 Go. Sur téléphone, il faut impérativement des segments courts.
- Thermique : sur un traitement de plusieurs minutes, les SoC mobiles réduisent leur fréquence. Il faut prévoir une file reprenable, une barre de progression et une option « transcrire en charge / la nuit ». Aucune mesure de batterie publiée n'a été trouvée pour ces modèles (non vérifié).

### Diarisation (qui parle ?) sur l'appareil

- **sherpa-onnx offline speaker diarization** : segmentation pyannote 3.0 en ONNX (environ 6,6–7 Mo) plus un embedding de locuteur (3D-Speaker CAM++ environ 28 Mo, ou WeSpeaker ResNet34 environ 26 Mo), puis un clustering. Total d'environ 35–45 Mo, CPU, Android et iOS ([exemple Python](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-speaker-diarization.py), [OpenWhispr](https://openwhispr.com/blog/local-speaker-diarization), [miroir des modèles](https://huggingface.co/kouhxp/sherpa-onnx-diarization-models/tree/main)). La segmentation pyannote ne dépend pas de la langue. Elle convient donc au français, mais ses performances en réunion française réelle n'ont pas été mesurées (non vérifié). Des écarts avec pyannote PyTorch ont été signalés ([issue #1708](https://github.com/k2-fsa/sherpa-onnx/issues/1708)).
- Il faut fixer le nombre de locuteurs quand il est connu : le clustering à seuil donne souvent des locuteurs en trop ou en moins.
- Ce traitement se fait **en batch après la réunion**, puis les tours de parole sont alignés sur les horodatages ASR. Parakeet fournit des horodatages au mot, Nemotron n'en documente pas, ce qui est un argument de plus pour Parakeet.
- iOS : SpeakerKit (Argmax, [argmax-oss-swift](https://github.com/argmaxinc/argmax-oss-swift)) ou FluidAudio en CoreML (non vérifié en détail).
- NVIDIA publie aussi des modèles de diarisation ([blog Nemotron diarization](https://huggingface.co/blog/nvidia/nemotron-diarization)), orientés GPU (non étudié).
- Alternative : laisser le LLM de synthèse (OpenAI/Anthropic) déduire les intervenants à partir du contenu. C'est moins fiable, mais sans coût sur l'appareil.

## 4. Recommandation

**Moteur principal (Android et iOS) : Parakeet TDT 0.6B v3 int8 via sherpa-onnx, en batch après la réunion.**
- Meilleur WER français publié pour un modèle de taille mobile : FLEURS 5,15, MLS 4,97, soit environ 40 % d'erreurs en moins que Nemotron (9,0).
- 640 Mo sur disque, à télécharger au premier lancement et non embarqué dans l'APK. Variante int4 environ 410 Mo.
- Ponctuation et horodatage au mot (utile pour la diarisation), licence CC-BY-4.0, un seul SDK (sherpa-onnx) pour ASR, VAD et diarisation sur les deux plateformes. Déjà en production sur Android pour du français.
- Sur iOS, FluidAudio (CoreML/ANE) est une option plus rapide pour le même modèle (non vérifié).

**iOS, option native : Apple SpeechTranscriber (iOS 26+).** Aucun modèle à embarquer, prévu pour l'audio long, français pris en charge. Il sert d'aperçu en direct pendant la réunion, ou de secours si l'appareil est trop juste en RAM. Sa qualité doit être comparée à Parakeet sur nos propres enregistrements.

**Secours :**
- Android bas de gamme (moins de 4 Go de RAM) : Canary 180M Flash int8 (environ 154 Mo, MLS fr 4,75), avec des segments VAD de moins de 40 s.
- iOS : WhisperKit large-v3-turbo compressé (626 Mo).
- Ultime recours si l'appareil ne suit pas : envoyer l'audio à une API de transcription. Cela sort du principe « sur l'appareil » et doit être soumis au consentement de l'utilisateur.
- Écartés pour le français : Vosk, Moonshine, Kyutai, Android SpeechRecognizer et Whisper ≤ small.

**Nemotron 3.5 ASR : à garder en option, non retenu comme moteur principal.**
- Pour : il gère le français (niveau 1), il est conçu pour le streaming natif à faible latence, sa licence permet l'usage commercial, et il est pris en charge par sherpa-onnx (master, juin 2026).
- Contre : WER français nettement moins bon que Parakeet v3 (9,0 contre 5,15 sur FLEURS), cible officielle GPU/Linux uniquement, export ONNX communautaire en FP32 (2,59 Go) sans int8 publié, aucune mesure Android, horodatage non documenté.
- À réévaluer si l'on veut une **transcription en direct de qualité sur Android**. Dans ce cas, il faudrait faire un prototype sherpa-onnx int8 et mesurer le RTF, la RAM et la température sur 1 h d'audio réel. Pour un compte rendu après la réunion, il n'apporte rien face à Parakeet.

**Prochaine étape conseillée** : constituer un petit corpus de 3 à 5 vraies réunions françaises enregistrées au téléphone et mesurer le WER, le RTF, la RAM et la batterie de Parakeet v3 int8, Canary 180M, Apple SpeechTranscriber et Nemotron int8 sur un téléphone Android milieu de gamme et un iPhone.
