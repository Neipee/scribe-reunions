# 01 - Que trouve-t-on déjà ? (étude de l'existant)

Date de l'étude : 2026-10-27. Étude documentaire uniquement : rien n'a été installé ni exécuté.
Les chiffres GitHub (étoiles, licence, dernier push) viennent de l'API GitHub interrogée le jour même ; les autres informations viennent des README, docs et pages web citées. Tout ce qui n'a pas pu être confirmé est marqué « non vérifié ».

## 1. Rappel des contraintes à satisfaire

| Réf. | Contrainte |
|---|---|
| C1 | Application mobile Android (iOS idéalement) |
| C2 | Enregistrement de la réunion |
| C3 | Transcription sur l'appareil (cible : nemotron-3.5-asr-streaming-0.6b, ou alternative locale) |
| C4 | Résumé par OpenAI ou Anthropic (clé API de l'utilisateur, ou abonnement Claude/ChatGPT) |
| C5 | Plusieurs formats de résumé + résumés personnalisés (modèles de prompt ou « skills ») |
| C6 | Plusieurs résumés par réunion |
| C7 | Historique de chaque création / modification / suppression |
| C8 | Données uniquement locales ; rien ne sort sauf vers OpenAI / Anthropic |

## 2. Le modèle cible : état des lieux

- Le modèle [nvidia/nemotron-3.5-asr-streaming-0.6b](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b) est multilingue (40 paires langue/pays annoncées d'après la recherche, détection automatique), de dernière mise à jour 2026-09-10 d'après l'[API Hugging Face](https://huggingface.co/api/models/nvidia/nemotron-3.5-asr-streaming-0.6b). Licence déclarée : `openmdw-1.1` ([texte](https://openmdw.ai/license/1-1/)) ; les conséquences juridiques exactes pour une application distribuée sont non vérifiées.
- sherpa-onnx (Apache-2.0) le prend en charge : la [page NeMo de la doc](https://k2-fsa.github.io/sherpa/onnx/nemo/index.html) liste `sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11 (Multilingual)`. Cette page ne mentionne pas Android pour ce modèle. Les [APK de démo](https://k2-fsa.github.io/sherpa/onnx/android/apk.html) cités par la recherche concernent le modèle anglais ; une build QNN (NPU Qualcomm) Android existe ([miroir SourceForge](https://sourceforge.net/projects/sherpa-onnx.mirror/files/asr-models-qnn-3/sherpa-onnx-qnn-nemotron-3.5-asr-streaming-0.6b-320s-android-aarch64.tar.bz2/download)). Le support multilingue (entrée `prompt_index`) a fait l'objet de l'[issue #3664](https://github.com/k2-fsa/sherpa-onnx/issues/3664) ; la [discussion HF](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/discussions/1) indique qu'il est maintenant dans master. Fonctionnement réel sur téléphone (latence, RAM) : non vérifié.
- Un [article arXiv](https://arxiv.org/pdf/2604.14493) sur l'ASR streaming embarqué recommande Nemotron-0.6B en int4 (retard algorithmique 0,56 s, WER streaming 7,28 %) : chiffre rapporté par la recherche, non relu dans le papier.
- Alternative éprouvée sur Android : Parakeet TDT 0.6B int8 via sherpa-onnx (utilisée par HearoPilot et Private Meeting Notes, voir plus bas), ou Whisper via whisper.cpp / [whisper.rn](https://github.com/mybigday/whisper.rn) (MIT ; gère aussi Parakeet d'après la recherche).
- Briques de développement : [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (15 549 étoiles, Apache-2.0, activité du 2026-10-27, Android/iOS/Flutter via le paquet [sherpa_onnx](https://pub.dev/packages/sherpa_onnx) Apache-2.0), [react-native-sherpa-onnx](https://github.com/XDcobra/react-native-sherpa-onnx) (licence et activité non vérifiées).

## 3. Applications mobiles (priorité)

### 3.1 Open source, Android

**Private Meeting Notes** ([dépôt](https://github.com/matthesschramm/private-meeting-notes))
- Plateforme : Android 15+, ARM64, Kotlin / Jetpack Compose. Testé uniquement sur Pixel 11. Pas d'iOS.
- Transcription : locale, NVIDIA Parakeet TDT 0.6B (pas Nemotron streaming) + diarisation Nemotron 3 Diarization (anglais seulement).
- LLM : Gemma 4 locale (GPU du téléphone) pour notes (aperçu, points clés, décisions, questions ouvertes, actions) ; questions-réponses sur réunions et documents. Aucun LLM cloud : l'application n'a volontairement aucune permission réseau, un script vérifie le manifeste (`scripts/check-manifest.sh`). Les modèles sont copiés par USB.
- Formats de résumé : un format structuré fixe + « notes en prose sur demande », export Markdown. Modèles personnalisés, plusieurs résumés, historique de modifications : non mentionnés dans le README (non vérifié).
- Licence : Apache-2.0. Créé le 2026-10-19, dernier push 2026-10-19, 0 étoile, 0 release publiée : très jeune, projet personnel.
- Perfs annoncées (Pixel 11) : réunion synthétique de 60 min traitée en 16,4 min ; réunion réelle de 3 h 09 en environ 55 min. Environ 15 Go d'espace requis.

**HearoPilot** ([dépôt Helldez](https://github.com/Helldez/HearoPilot-App), [fiche Play Store](https://play.google.com/store/apps/details?id=com.hearopilot.app&hl=en), [présentation sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/discussions/3470))
- Plateforme : Android (API 30+, Kotlin ; la présentation dans la discussion Meetily parle de Kotlin Multiplatform, donc iOS possible mais non vérifié).
- Transcription : locale et temps réel, sherpa-onnx + Parakeet TDT 0.6B int8 (~670 Mo) avec VAD Silero.
- LLM : local uniquement (llama.cpp, Gemma 3 1B quantifié) ; « 100 % hors-ligne, aucun appel réseau pendant l'enregistrement ». Pas de clé API.
- Formats : 4 modes d'enregistrement (écoute simple, réunion courte, réunion longue, traduction temps réel) qui fixent le contenu produit (résumé, tâches, suggestions). Pas de modèles personnalisés d'après le README.
- Historique : sessions persistantes (base Room), recherche plein texte, édition en ligne des segments, des insights et des tâches. Pas de journal d'audit des modifications d'après le README (non vérifié dans le code).
- Licence : Apache-2.0. 105 étoiles, dernier push 2026-06-10 (donc inactif depuis ~4,5 mois). Dérivés : [MeetMind Assistant](https://github.com/jimmycuong1412/meetmind-assistant) (4 étoiles, Apache-2.0, push 2026-10-24), [fork chunblo](https://github.com/chunblo/HearoPilot-App).
- Retour d'expérience utile : Android tue le service pendant l'inférence LLM, l'auteur a dû écrire un gestionnaire de RAM ([discussion Meetily #445](https://github.com/Zackriya-Solutions/meetily/discussions/445)).

**Android-Offline-AI-Recorder-Whisper-LLM-On-Device** ([dépôt](https://github.com/yamanobora/Android-Offline-AI-Recorder-Whisper-LLM-On-Device-))
- Android, whisper.cpp + llama.cpp (modèle HACHI-Summary japonais 0,5 B), 100 % local. Expérimental, 6 étoiles, dernier push 2026-03-28. Le README annonce MIT, mais l'API GitHub ne détecte aucune licence (pas de fichier LICENSE : non vérifié). Pas de cloud, pas de modèles, pas d'historique. Intérêt : démonstrateur uniquement.

**Transcription for Android** ([dépôt totec448-spec](https://github.com/totec448-spec/Transcription))
- Android, Kotlin, Apache-2.0, 7 étoiles, push 2026-10-24. Fonctionne avec clés API de l'utilisateur, stockées chiffrées (Keystore).
- Transcription : cloud (OpenRouter, ElevenLabs, AssemblyAI) : contraire à C3 et C8. Nettoyage par LLM via OpenRouter avec plusieurs modes à prompt éditable (Clean, Polish, Concise, Formal, Casual, Notes, Prompt), historique local avec audio.
- Intérêt : patron d'UX pour « clé API de l'utilisateur » et « modes à prompt éditable ». Pas un outil de réunion.

**Applications de dictée Android** (clavier / service de saisie vocale, pas des outils de réunion)
- [Transcribro](https://github.com/soupslurpr/Transcribro) : whisper.cpp + Silero VAD, ISC, 761 étoiles, push 2026-09-29. Dictée uniquement.
- [WhisperIME](https://github.com/woheller69/whisperIME) (« Whisper » sur [F-Droid](https://f-droid.org/packages/org.woheller69.whisper/)) : IME + appli autonome, MIT, 653 étoiles, push 2026-10-12, version 3.8 du 2026-10-14. Dictée uniquement.
- [FUTO Voice Input](https://github.com/futo-org/voice-input) : miroir de sources, licence signalée « NOASSERTION » par GitHub (licence FUTO « source-first » probable, non vérifié), 342 étoiles. Dictée.
- [Voxscribe](https://f-droid.org/packages/org.y20k.voxscribe/) (MIT) et Scrib (GPL-3.0-or-later) sur F-Droid : dictée / transcription locale, sans résumé (selon la fiche F-Droid ; Scrib non relu en détail).

### 3.2 Open source, mobile + bureau

**Anarlog** (ex-Hyprnote ; [dépôt fastrepl/anarlog](https://github.com/fastrepl/anarlog), [doc modèles et fournisseurs](https://docs.anarlog.so/models-and-providers), [FAQ](https://docs.anarlog.so/help))
- Plateformes : macOS, Windows, Linux (bureau) + dossier `apps/mobile` (iOS et Android, bêta TestFlight / Google Play interne ; changelog « Mobile v0.1.5 », 2026-10-11). Le mobile est présenté comme compagnon de consultation et de synchronisation ; la transcription locale est documentée pour le bureau seulement (Apple Silicon : Soniqo Parakeet, Apple Speech, whisper.cpp). Transcription locale sur mobile : non vérifié (probablement absente).
- Données : SQLite locale + fichiers ; mais synchronisation « CloudSync » optionnelle et offre Anarlog Cloud (routée via OpenRouter) : à désactiver pour respecter C8.
- LLM : le plus proche de C4. Clés API ou points de terminaison compatibles OpenAI, abonnements Claude et ChatGPT (ainsi que Grok, GitHub Copilot, Kimi Code), serveurs locaux (Ollama, LM Studio, Unsloth), Apple Intelligence (expérimental).
- Modèles et historique : interface de résumés/chat ; modèles personnalisés et versions multiples non documentés dans les pages lues (non vérifié).
- Licence : MIT pour l'application communautaire ; composants `enterprise/` sous licence commerciale. 9 611 étoiles, push 2026-10-27 (très actif). L'équipe développe désormais [char](https://char.com) en parallèle, sans arrêter anarlog.
- Pile : Tauri / Rust / TypeScript, mobile en Expo / React Native (déduit des fichiers `app.config.ts`, `eas.json` : non vérifié).

**Amical** ([dépôt](https://github.com/amicalhq/amical)) : MIT, 1 572 étoiles, push 2026-10-26. Dictée IA locale surtout ; page [amical.ai/android](https://amical.ai/android) renvoie vers une fiche Google Play (`ai.amical.app`) et le README propose une bêta iOS. Fonctions mobiles, moteur et résumés : non vérifiés.

**Vibe** ([dépôt](https://github.com/thewh1teagle/vibe)) : bureau (macOS/Windows/Linux). Whisper local, résumés via API Claude ou Ollama, diarisation. Un téléphone iOS/Android peut enregistrer via un QR code mais la transcription se fait sur l'ordinateur. MIT, 7 923 étoiles, push 2026-10-06.

**Scriberr** ([dépôt](https://github.com/rishikanthc/Scriberr)) : serveur auto-hébergé (Go, SQLite, Docker) avec application web PWA utilisable sur téléphone. Transcription locale sur le serveur, résumés et chat via Ollama ou API compatible OpenAI. MIT, 3 117 étoiles, push 2026-09-20. Ce n'est pas une transcription sur le téléphone.

### 3.3 Applications fermées / propriétaires sur mobile (référence)

| Produit | Plateformes | Transcription | Résumé / LLM | Remarque |
|---|---|---|---|---|
| Google Recorder ([blog Android](https://android-developers.googleblog.com/2024/08/recorder-app-on-pixel-sees-boost-in-engagement-with-gemini-nano.html)) | Pixel | Locale, temps réel | Gemini Nano local (résumé en puces) | Pas de clé API, formats fixes. Pixel uniquement. |
| Samsung Transcript Assist / Note Assist ([Galaxy AI](https://en.wikipedia.org/wiki/Galaxy_AI)) | Galaxy S24+ | Après enregistrement | Résumé structuré | Traitement 100 % local : non vérifié. |
| Apple Notes / Voice Memos ([support Apple](https://support.apple.com/guide/iphone/summarize-an-audio-recording-iph59143007d/ios)) | iPhone 12+ (transcription), 15 Pro+ (Apple Intelligence) | Locale | Résumé Apple Intelligence local | Pas d'étiquettes de locuteurs, résumé non orientable ([source tierce](https://klu.so/blog/apple-voice-memos-transcription-limits)). |
| [Whisper Notes](https://apps.apple.com/us/app/whisper-notes-ai-note-taker/id6741365337) | iPhone, Mac | Locale (Whisper), diarisation | Résumé annoncé « local » (une des deux fiches) | Source principalement l'éditeur ; fermé. |
| [Aiko](https://sindresorhus.com/aiko) | iOS, macOS | Locale (Whisper) | Aucun | Transcription seule. |
| MacWhisper / Whisper Transcription (iOS) | Mac, iPhone 15+ | Locale | Non vérifié | Fermé. |

### 3.4 Références cloud (hors périmètre, pour comparer les formats)

Otter, Fireflies, Notta, Plaud : transcription et résumé dans le cloud, donc incompatibles avec C3 et C8. Utiles seulement comme référence de formats : Plaud propose une bibliothèque de modèles (compte rendu, actions, etc.), Otter réserve les workflows personnalisés à l'offre Business (19,99 $/utilisateur/mois). Sources : [TechRepublic](https://www.techrepublic.com/article/news-best-ai-meeting-note-takers-2026/), [Plaud](https://www.plaud.ai/blogs/articles/best-ai-note-takers-for-in-person-meetings) (source éditeur). Noota : non vérifié (aucune source trouvée).

## 4. Applications de bureau (référence)

| Projet | Transcription | LLM | Modèles / formats | Données | Licence, activité |
|---|---|---|---|---|---|
| [Meetily](https://github.com/Zackriya-Solutions/meetily) | Locale, Whisper ou Parakeet | Ollama, Claude, Groq, OpenRouter, OpenAI, point de terminaison compatible OpenAI | Modèles personnalisés réservés à l'offre PRO (README) | Locale | MIT, 32 232 étoiles, v0.4.1 du 2026-09-12, push 2026-10-24. macOS/Windows (Linux via compilation). Pas de mobile ([discussion](https://github.com/Zackriya-Solutions/meetily/discussions/445), [comparatif tiers](https://openwhispr.com/compare/meetily)). |
| [OpenWhispr](https://github.com/OpenWhispr/openwhispr) | Locale (Parakeet / Whisper) ou cloud | GPT, Claude, Gemini, Groq, local | Réunions Zoom/Teams, diarisation locale, recherche sémantique | Locale ou cloud au choix | MIT, 10 110 étoiles, push 2026-10-27. Bureau. |
| [Handy](https://github.com/cjpais/Handy) | Locale | Aucun résumé | Dictée + historique | Locale | MIT, 34 870 étoiles, push 2026-10-27. Bureau. |
| [Buzz](https://github.com/chidiwilliams/buzz) | Locale (Whisper) | Plugin « AI summary » | Plugins | Locale | MIT, 22 223 étoiles, push 2026-10-27. Bureau. |
| [Pensieve](https://github.com/lukasbach/pensieve) | Locale | Ollama ou clé OpenAI | Non vérifié | Locale | Aucune licence détectée (donc tous droits réservés par défaut), 117 étoiles, push 2026-05-30. |
| [ownscribe](https://github.com/paberr/ownscribe) | Locale | Local ou compatible OpenAI | CLI | Locale | MIT, 111 étoiles, push 2026-08-14. |
| [Recap](https://github.com/RecapAI/Recap) | Locale (macOS) | Non vérifié | Non vérifié | Locale | MIT, 717 étoiles, dernier push 2026-02-07. |
| [meeting-notes (MrMazzone)](https://github.com/MrMazzone/meeting-notes) | faster-whisper / Whisper | Claude | Non vérifié | Locale | Aucune licence, 0 étoile, Flutter Linux. |
| [Whispering / Epicenter](https://github.com/EpicenterHQ/epicenter) | Locale ou cloud | Non vérifié | Non vérifié | Locale | Licence « NOASSERTION » (non vérifié), 4 826 étoiles. Source : [Slator](https://slator.com/whispering-open%E2%80%91source-local%E2%80%91first-transcription-app/). |

Remarque sur le recouvrement : OpenWhispr, Meetily et Anarlog ont déjà résolu la partie « fournisseurs LLM + modèles + stockage local + diarisation » sur ordinateur ; aucun n'a de version mobile avec transcription locale.

## 5. Tableau comparatif par rapport aux contraintes

Légende : oui = confirmé, partiel = partiellement confirmé, non = absent ou contraire, ? = non vérifié.

| Solution | C1 mobile | C3 STT local | C4 OpenAI/Anthropic (clé ou abonnement) | C5 formats + modèles perso | C6 plusieurs résumés | C7 historique des modifs | C8 rien ne sort | Licence | Maintenance |
|---|---|---|---|---|---|---|---|---|---|
| Private Meeting Notes | Android | oui (Parakeet) | non (LLM local, aucun réseau) | partiel (1 format) | ? | ? | oui | Apache-2.0 | 2026-10-19, 0 étoile |
| HearoPilot | Android (iOS ?) | oui (Parakeet) | non (llama.cpp local) | partiel (4 modes fixes) | ? | partiel (sessions éditables, pas d'audit) | oui | Apache-2.0 | 2026-06-10, 105 étoiles |
| Anarlog | iOS+Android bêta (compagnon), bureau | bureau seulement (Apple Silicon) ; mobile ? | oui (clé, abonnements Claude/ChatGPT, local) | ? | ? | ? | partiel (sync/Cloud optionnels) | MIT (hors `enterprise/`) | 2026-10-27, 9 611 étoiles |
| Meetily | non (bureau) | oui | oui (Claude, OpenAI, etc.) | partiel (modèles perso = PRO) | ? | ? | oui | MIT | 2026-10-24, 32 232 étoiles |
| OpenWhispr | non (bureau) | oui | oui | ? | ? | ? | partiel | MIT | 2026-10-27, 10 110 étoiles |
| Vibe | non (téléphone = micro distant) | oui (bureau) | partiel (Claude, Ollama) | ? | ? | ? | oui | MIT | 2026-10-06, 7 923 étoiles |
| Scriberr | PWA (serveur) | oui (serveur) | oui (OpenAI-compatible, Ollama) | ? | ? | ? | oui | MIT | 2026-09-20, 3 117 étoiles |
| Transcription (totec448) | Android | non (cloud) | partiel (OpenRouter) | partiel (modes à prompt éditable) | non | partiel (historique) | non | Apache-2.0 | 2026-10-24, 7 étoiles |
| Google Recorder / Samsung / Apple | oui | oui | non | non (formats fixes) | non | non | oui (en principe) | fermé | n/a |
| Whisper Notes / Aiko | iOS | oui | non | non | non | non | oui | fermé | n/a |

## 6. Sur l'abonnement Claude / ChatGPT (impact sur C4)

- Anthropic : l'utilisation des jetons OAuth d'un abonnement Claude Free/Pro/Max dans une application tierce est interdite par les conditions d'utilisation grand public ; application effective depuis le 2026-01-09 et clarifiée en février 2026 ([The Register](https://www.theregister.com/software/2026/02/20/anthropic-clarifies-ban-on-third-party-tool-access-to-claude/5014546), [WinBuzzer](https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/)). Un blog tiers daté d'octobre 2026 signale une reformulation de la page officielle mais maintient que les produits tiers ne peuvent pas proposer la connexion Claude.ai ([source tierce](https://yage.ai/share/claude-code-subscription-not-a-developer-credential-en-20260321.html) ; page officielle code.claude.com/docs/en/legal-and-compliance non relue : non vérifié). Conclusion prudente : côté Anthropic, seule la clé API est sûre. Anarlog propose pourtant la connexion abonnement Claude : risque de conformité non vérifié.
- OpenAI : « Sign in with ChatGPT » annoncé le 2026-09-29 permet à des applications tierces d'utiliser le forfait ChatGPT Plus/Pro de l'utilisateur ; les applications open source peuvent s'inscrire en libre-service ([The New Stack](https://thenewstack.io/sign-in-with-chatgpt/), [doc OpenAI](https://developers.openai.com/siwc/token-sharing-open-source), [DEV](https://dev.to/hassann/sign-in-with-chatgpt-for-developers-the-oauth-flow-plan-usage-and-what-it-means-for-your-api-bill-48f7)). Conditions d'une application mobile non encore examinées : non vérifié. Le flux OAuth transite par OpenAI, ce qui reste compatible avec C8.

## 7. Verdict

**Aucune solution ne remplit toutes les contraintes, et aucune n'en remplit la plupart sur mobile.** Chaque projet couvre un sous-ensemble :

- Mobile + transcription locale + enregistrement (C1-C3) : HearoPilot et Private Meeting Notes, mais tous deux avec un LLM local et zéro appel cloud (contraire à C4) et des formats fixes (C5).
- Clé API / abonnement + formats + stockage local (C4, C5, C8) : Anarlog, Meetily, OpenWhispr, Scriberr, mais sur ordinateur ou serveur ; Anarlog mobile n'est qu'un compagnon de synchronisation.
- Historique complet des créations/modifications/suppressions (C7) : non trouvé dans aucun projet examiné (au mieux, historique de sessions éditables). C'est un manque général.
- Plusieurs résumés par réunion (C6) : non confirmé nulle part ; Meetily et les autres n'en parlent pas.
- Modèles personnalisés (C5) : réservés à une offre payante chez Meetily ; non confirmé ailleurs.
- Nemotron 3.5 streaming en production sur téléphone : aucune appli open source vérifiée ne l'utilise (les apps trouvées utilisent Parakeet TDT) ; sherpa-onnx est la voie de support.

### Manques à construire (liste synthétique)

1. Client OpenAI / Anthropic sur mobile (clé stockée dans Keystore / Keychain) avec contrôle strict des destinations réseau.
2. Moteur de modèles de résumé (formats prédéfinis + prompts utilisateur), gestion de plusieurs résumés par réunion.
3. Journal d'historique (événement par création / modification / suppression, éventuellement avec versions) sur le stockage local.
4. Intégration de Nemotron 3.5 streaming via sherpa-onnx sur Android (et iOS), incluant la gestion mémoire en arrière-plan.
5. Politique réseau : aucune permission ni dépendance qui sorte vers un autre hôte que `api.openai.com` / `api.anthropic.com` (Private Meeting Notes a déjà un test de manifeste réutilisable).

## 8. Meilleures bases à forker ou à réutiliser

Toutes ces licences (Apache-2.0, MIT) sont compatibles entre elles et avec un produit fermé ou ouvert, sous réserve de conserver les mentions de licence (analyse juridique non vérifiée).

1. **Private Meeting Notes** (Apache-2.0, Android natif Kotlin/Compose) : meilleure base pour le pipeline Android (enregistrement écran éteint, import, Parakeet, diarisation, export Markdown, banc d'essai, garde-fou « aucun réseau »). À adapter : supprimer le LLM local ou le rendre optionnel, ajouter l'unique permission réseau et un client API. Réserve : projet d'une semaine, un seul développeur, testé sur un seul téléphone, 15 Go d'espace, Android 15 minimum.
2. **HearoPilot** (Apache-2.0, Kotlin, Room, sherpa-onnx) : base plus ancienne et plus simple (API 30+, ~670 Mo de STT), avec persistance de sessions et édition. Réserve : inactif depuis 2026-06-10, 105 étoiles ; réutilisable surtout pour son service d'enregistrement et son gestionnaire de RAM.
3. **Anarlog** (MIT) : à réutiliser comme référence de conception (fournisseurs LLM, modèles, schéma SQLite) plutôt que comme base de fork, car sa pile Tauri/Rust + Expo, sa synchronisation cloud et ses composants `enterprise/` sous licence commerciale compliquent un fork strict.

Pour la transcription, partir de **sherpa-onnx** (Apache-2.0) ou, côté React Native, **whisper.rn** (MIT) plutôt que d'une application complète. Un développement neuf en Kotlin (puis iOS en Swift ou Kotlin Multiplatform) avec ces briques reste plausible si le forfait d'adaptation de Private Meeting Notes s'avère trop lourd.

## 9. Points non vérifiés (récapitulatif)

- Fonctionnement réel de Nemotron 3.5 streaming sur téléphone (latence, mémoire) et implications précises de la licence `openmdw-1.1`.
- Transcription locale dans l'app mobile Anarlog ; existence de modèles personnalisés et de versions multiples dans Anarlog.
- Historique de modifications dans Private Meeting Notes, HearoPilot, Anarlog (code non lu).
- Support iOS de HearoPilot ; licence et activité de react-native-sherpa-onnx ; fonctions mobiles d'Amical.
- Traitement 100 % local chez Samsung ; fonctions de résumé de MacWhisper, Recap, Pensieve, Whispering ; Noota.
- Page officielle Anthropic sur l'authentification par abonnement (relue uniquement via sources tierces) ; conditions d'une application mobile pour « Sign in with ChatGPT ».
- Licence exacte de FUTO Voice Input.
