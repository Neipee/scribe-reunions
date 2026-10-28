# 06 - Faisabilité, arbitrages et plan de réalisation

Date : 2026-10-27. Étude documentaire, sans code. Cette note tranche les points laissés ouverts ou contradictoires dans les notes 01 à 05 et en tire un chiffrage et un plan.
Aucune nouvelle recherche web n'a été faite. Les affirmations qui ne figurent pas dans les notes 01 à 05 viennent de connaissances générales : elles sont marquées **non vérifié**. Les chiffrages sont des estimations d'architecte : aucune mesure ne les étaye.

---

## 0. Synthèse des décisions

| Sujet | Décision | Condition de révision |
|---|---|---|
| Stack | **Kotlin natif (Jetpack Compose) pour Android**, avec un module de domaine en Kotlin pur, sans dépendance Android, prêt pour KMP. iOS, s'il est lancé : KMP pour la logique partagée, SwiftUI et briques natives Swift pour l'audio, l'ASR et le stockage. | Si, à la fin de la phase 0, iOS devient une exigence ferme de la V1 **et** que l'équipe maîtrise Dart, on bascule sur Flutter. Le service micro Kotlin du spike est réutilisable comme module natif Flutter. |
| Base de code | **Nouveau dépôt construit de zéro**, qui reprend des **composants** de Private Meeting Notes et de HearoPilot (Apache-2.0, mentions de licence conservées). Pas de fork. Anarlog sert de référence de conception uniquement. | Si la lecture du code en phase 0 montre que le service d'enregistrement de Private Meeting Notes est réutilisable presque tel quel, on le reprend en bloc. |
| ASR | **Parakeet TDT 0.6B v3 int8 via sherpa-onnx, en batch après la réunion**, avec un découpage VAD (Silero). Repli bas de gamme : Canary 180M Flash. Nemotron 3.5 reste une option, évaluée en phase 0 uniquement si la transcription en direct est demandée. | Nemotron passe devant si la transcription en direct devient obligatoire et qu'il passe les seuils de la phase 0. |
| Connexion LLM | MVP : **clé API OpenAI et/ou Anthropic d'un projet d'organisation**, saisie dans l'appli, avec appel direct, `store:false` et aucun endpoint à état. Mode **« local seulement »** au choix pour chaque réunion. Interdits : la connexion Claude.ai, la réutilisation de jetons et MCP. | « Partager vers l'appli officielle » : V1, derrière une politique d'entreprise. « Sign in with ChatGPT » : V2, et seulement après une réponse écrite d'OpenAI. |
| Plateformes | **Android d'abord.** iOS est faisable, mais on le décide après la V1 Android : go/no-go à la fin de la phase 0 et à la fin de la V1. | Voir section 2. |

---

## 1. Arbitrages

### 1.1 Stack : Kotlin natif plutôt que Flutter

**Constat sur l'existant.** Les deux meilleures bases Android sont en Kotlin. Private Meeting Notes est en Kotlin / Jetpack Compose, Android 15+, sans iOS. HearoPilot est en Kotlin avec Room ; il est présenté comme Kotlin Multiplatform, ce qui n'est pas vérifié (cf. 01, §3.1). Aucune des deux n'apporte de code Flutter réutilisable.

**Position de 04.** La note 04 recommande Flutter comme compromis « Android obligatoire, iOS si possible ». Elle retient Kotlin natif « si seul Android compte réellement » ou « si l'équipe est déjà Kotlin », et ne connaît pas les compétences de l'équipe (cf. 04, §0, §1.4).

**Décision : Kotlin natif.** Raisons :
1. **Seul Android est obligatoire.** iOS est « souhaité si faisable », et ses conditions (Mac, canal de distribution, MDM) ne sont pas connues (section 2, section 6). On n'optimise pas la pile pour une plateforme qui n'est pas confirmée.
2. **Les parties risquées sont natives de toute façon.** Le service de premier plan de type micro, la mémoire de l'ASR et la reprise après un arrêt forcé exigent un module Kotlin, même sous Flutter (cf. 04, §0 et §1.2). La note 01 rapporte qu'Android tue le service pendant l'inférence et qu'il a fallu écrire un gestionnaire de RAM (cf. 01, HearoPilot). En Kotlin, tout cela est du code de premier rang.
3. **Réutilisation directe** de composants Kotlin (cf. 01, §8) : service d'enregistrement, gestionnaire de RAM, script de contrôle du manifeste « aucun réseau », banc d'essai.
4. **Confidentialité plus facile à prouver.** En Kotlin, on peut avoir un client OkHttp unique avec un `Dns` fermé (cf. 05, §1.4 B), Room avec `sqlcipher-android` (noté « ++ » en 04, §1.3) et le Keystore en direct. Le comportement réseau du framework Flutter dans l'appli compilée n'est pas vérifié (cf. 05, §1.4 A) : c'est une inconnue de plus à lever.
5. **Coût accepté.** Si iOS est confirmé, l'interface et les briques natives iOS sont à écrire en SwiftUI et Swift, et l'iOS coûte plus cher qu'avec Flutter (section 3). Pour limiter ce surcoût, le domaine est écrit dès le départ en Kotlin pur : modèles, moteur de gabarits, règles d'audit, client LLM sous Ktor, map-reduce. Il pourra devenir un module KMP. Le stockage iOS sera natif (SQLCipher en Swift) et non KMP, car SQLCipher sous KMP/iOS est documenté comme fragile (cf. 04, §1.3 et §9).

Ordre de grandeur du surcoût : avec Flutter, l'iOS coûterait environ 5 à 8 personnes-semaines (p.-sem.) de moins que la voie KMP + SwiftUI (section 3). C'est pourquoi la décision est réversible à la fin de la phase 0, avant tout investissement dans l'interface.

React Native est écarté : ses wrappers sherpa-onnx sont communautaires (cf. 04, §1.1), et `expo-updates` peut faire des appels réseau (cf. 05, §1.4 A).

### 1.2 Fork, développement neuf ou réutilisation de composants

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| Fork de Private Meeting Notes | Pipeline Android complet, garde-fou « aucun réseau », Parakeet déjà intégré | Projet d'une semaine, 0 étoile, un seul développeur, testé sur un seul Pixel, Android 15+ minimum, 15 Go requis, LLM local à retirer (cf. 01, §3.1 et §8) | Non |
| Fork de HearoPilot | API 30+, Room, sherpa-onnx et Parakeet, gestion de la RAM | Inactif depuis 2026-06-10. Modèle de données sans audit, sans versions ni résumés multiples. LLM local (cf. 01) | Non |
| Fork d'Anarlog | Couche LLM la plus proche de C4 | Pile Tauri/Rust + Expo, synchronisation cloud, composants `enterprise/` sous licence commerciale, pas de transcription locale sur mobile (cf. 01, §3.2 et §8) | Non (référence de conception) |
| **Développement neuf + composants** | Le modèle de données est conçu pour C5 à C8 (cf. 04, §3 et §4). Ces exigences n'existent dans aucun projet examiné (cf. 01, §7). On reprend le code éprouvé et on écarte le reste. | Il faut réécrire l'interface | **Retenu** |

Ce qui fait la valeur du produit (gabarits, résumés multiples, journal d'audit, chiffrement, client OpenAI/Anthropic) manque dans tous les projets étudiés (cf. 01, §7, « Manques à construire »). Un fork imposerait donc de refaire le modèle de données tout en héritant de la dette du projet d'origine.

**Composants à reprendre**, après lecture du code en phase 0 (1 à 2 jours, le code n'a pas encore été lu, cf. 01, §9) :
- Private Meeting Notes : service d'enregistrement écran éteint, intégration Parakeet et sherpa-onnx, banc d'essai, `scripts/check-manifest.sh`, à adapter pour autoriser les seuls hôtes de la liste blanche.
- HearoPilot : gestionnaire de RAM, intégration du VAD Silero.
- Transcription (totec448) : modèle d'expérience pour « clé API utilisateur » et « modes à prompt modifiable » (cf. 01, §3.1).
- Obligations : conserver les fichiers LICENSE et NOTICE (Apache-2.0) et la mention d'attribution CC-BY-4.0 du modèle Parakeet (cf. 02, §2).

### 1.3 Moteur ASR : Parakeet plutôt que Nemotron

**Désaccord entre les notes.** La note 01 rappelle la cible initiale : Nemotron 3.5 streaming, « ou une alternative locale » (C3). La note 02 recommande Parakeet. La note 04 cite Whisper ou Parakeet « selon le bench ».

**Décision : Parakeet TDT 0.6B v3 int8 (sherpa-onnx), en batch après la réunion.**
- **Qualité en français.** WER FLEURS de 5,15 pour Parakeet, contre 9,0 pour Nemotron à 1,12 s et 11,0 à 80 ms, soit environ 40 % d'erreurs en moins (cf. 02, §2 et §4).
- **Maturité sur mobile.** Parakeet a un paquet int8 officiel sherpa-onnx de 640 Mo, il est déjà en production sur Android en français, et Private Meeting Notes comme HearoPilot l'utilisent (cf. 01 et 02). Pour Nemotron, l'export ONNX est communautaire, en FP32 (2,59 Go), aucun int8 n'est publié et aucune mesure Android n'existe (cf. 02, §1).
- **Horodatage au mot**, nécessaire pour la diarisation et pour renvoyer à la source dans le résumé. Nemotron ne le documente pas (cf. 02, §1 et §3).
- **Pas de besoin de streaming dans le MVP.** Un compte rendu se fait après la réunion. Nemotron « n'apporte rien face à Parakeet » dans ce cas (cf. 02, §4).
- Whisper est écarté sur Android : turbo est lourd sans NPU, et small est trop faible en français (cf. 02, §2). Whisper reste un repli possible sur iOS via WhisperKit.

**Nemotron reste une option** si l'utilisateur confirme le besoin de transcription en direct (section 6). Dans ce cas, la phase 0 mesure Nemotron int8 en streaming pendant 1 h. Le texte en direct servirait d'aperçu, et Parakeet produirait la transcription définitive. Ce double calcul doit être validé sur le plan thermique.

**Conséquences de conception :**
- On enregistre toujours l'audio brut, en blocs chiffrés de 1 à 5 minutes (cf. 04, §2.3), puis l'ASR découpe le flux en segments VAD de 10 à 30 secondes (cf. 02, §3). Ces deux découpages sont indépendants.
- La file de transcription est reprenable segment par segment, avec une barre de progression et une option « transcrire en charge » (cf. 02, §3).
- **Distribution du modèle (640 Mo).** Le télécharger depuis Hugging Face fait apparaître un tiers (cf. 05, §1.3). Décision : en distribution MDM, le modèle est servi par un miroir HTTPS de l'entreprise ou embarqué dans l'APK. Sur le Play Store public, il passe par Play Asset Delivery. Dans tous les cas, son empreinte SHA-256 est épinglée dans l'appli. Hugging Face ne sert qu'en développement. Les limites de taille ne sont pas vérifiées (cf. 05, §5).

### 1.4 Modes de connexion aux LLM

**Désaccords entre les notes :**
- La note 03 fait de la clé personnelle de l'utilisateur (BYOK) le mode principal. La note 05 juge les clés personnelles inacceptables en entreprise, faute de DPA et de contrôle de la rétention (cf. 05, §3.4).
- La note 03 met le partage vers l'appli officielle dans le MVP. Selon la note 05, les données relèvent alors du régime grand public, où l'entraînement est possible.

| Mode | Décision | Justification |
|---|---|---|
| Clé API OpenAI et Anthropic saisie dans l'appli, appel direct | **MVP.** Même mécanisme qu'en 03, mais la politique impose une **clé de projet d'organisation** fournie par l'entreprise, avec plafond de dépenses et expiration. Stockage : Keystore + Tink/DataStore (cf. 03, §1.2). OpenAI : `store:false`. Option `eu.api.openai.com` si le projet est configuré pour l'UE. | Ce mode est autorisé (cf. 03, §3). C'est le seul qui permet un DPA, le ZDR ou la résidence UE (cf. 05, §3). |
| Mode « local seulement » pour une réunion | **MVP**, sans aucun appel réseau. On le choisit avant l'enregistrement. Sa valeur par défaut est fixée par la politique de l'entreprise, « local » par défaut tant qu'aucune clé n'est configurée. | Exigé pour les réunions sensibles (cf. 05, §4.4). Coût faible. |
| Partage manuel vers l'appli officielle ChatGPT ou Claude | **V1, désactivé par défaut.** Activable par politique seulement si l'entreprise dispose d'offres Business/Team/Enterprise couvertes par un DPA. Avertissement explicite sur le régime des données. | Autorisé (cf. 03, §2.4), mais incompatible avec la confidentialité si le compte est grand public (cf. 03, §2.4 et 05, §3.4). |
| « Sign in with ChatGPT » (forfait) | **V2 au plus tôt**, sous réserve d'une confirmation écrite d'OpenAI sur le mobile, l'appli commerciale, la rétention et les offres Business. | Le régime de rétention et d'entraînement n'est pas clair, et seuls les forfaits Plus/Pro sont couverts (cf. 03, §2.2). C'est peu utile en entreprise. |
| Connexion Claude.ai, réutilisation de jetons Claude Code/Codex | **Jamais.** | Interdit (cf. 03, §2.1). |
| Connecteur MCP / app ChatGPT | **Exclu.** | Exige un serveur exposé, ce qui contredit C8 (cf. 03, §2.3). |

**Fournisseur par défaut.** OpenAI si l'entreprise a besoin de la résidence UE : elle est possible avec un avenant et 10 % de surcoût. L'API directe d'Anthropic n'offre pas de région UE (cf. 03, §1.5 et 05, §3.2). Le choix final dépend des DPA signés (section 6).

**Autres arbitrages techniques sur les LLM :**
- **Instantané du prompt.** On stocke le gabarit rendu **sans** la transcription, avec `transcript_revision` et l'empreinte (hash) de la transcription. Cela tranche le point ouvert en 04, §4.2.
- **Passage unique ou map-reduce.** Passage unique si l'estimation tient dans 70 % de la fenêtre du modèle, map-reduce sinon (cf. 04, §5.4).
- **Sorties structurées** : pour le format « décisions et actions » seulement, avec une validation côté appli (cf. 04, §5.5).
- **Pseudonymisation avant envoi** : V1 (cf. 05, §4.4). Elle repose sur des expressions régulières et la liste des participants. Un modèle de reconnaissance d'entités (NER) local en français est à étudier.

---

## 2. Android seul ou Android + iOS

### 2.1 Verdict

**Android seul : faisable**, sous réserve des seuils de la phase 0 (ASR, autonomie, enregistrement de 2 h).
**iOS : faisable techniquement, avec un risque modéré.** Ce risque tient surtout au traitement en arrière-plan et à l'organisation (Mac, compte Apple, canal de distribution). Avec la stack retenue, il coûte **12 à 19 p.-sem. de plus** (section 3). Recommandation : lancer iOS seulement après la V1 Android, et si les conditions de la section 2.3 sont réunies.

### 2.2 Risques propres à iOS

| Sujet | Constat | Conséquence |
|---|---|---|
| **Enregistrement en arrière-plan** | Mode `UIBackgroundModes: audio` et `AVAudioSession` en catégorie `playAndRecord`, avec gestion des interruptions comme un appel entrant (cf. 04, §1.2, non vérifié). | Enregistrer 1 à 2 h écran verrouillé est faisable tant que la session audio est active (non vérifié). À tester en phase 0 si iOS est lancé. |
| **Calcul lourd après l'enregistrement** | En dehors d'une session audio active, iOS limite le calcul en arrière-plan. `BGProcessingTask` ne garantit pas son déclenchement (cf. 04, §1.2 et §9). | La transcription Parakeet sur iOS doit se faire **appli au premier plan**, avec écran de progression et option « garder l'écran allumé », ou **au fil de l'eau pendant l'enregistrement**, tant que la session audio est active. Piste à vérifier : une API iOS 26 de poursuite des tâches lancées par l'utilisateur (non vérifié, aucune source relue). |
| **Apple SpeechTranscriber** (iOS 26+) | Local, conçu pour l'audio long, aucun modèle à embarquer, accepte fr-FR, fr-CA, fr-BE et fr-CH. Pas de détection de langue. Apple ne publie aucun WER (cf. 02, §2 et §4). | Il peut remplacer Parakeet sur iOS et simplifie beaucoup le travail : pas de modèle de 640 Mo, accélération par l'OS. Mais (1) sa qualité doit être mesurée sur notre corpus, (2) le pack de langue est téléchargé depuis Apple : c'est un tiers technique, au même titre que l'hébergeur du modèle (cf. 05, §1.3), à faire valider, (3) il faut iOS 26 ou plus, et la liste des appareils compatibles n'est pas vérifiée. Il n'y a pas d'équivalent sur Android : le `SpeechRecognizer` est inadapté et interdit (cf. 02 et 05). |
| **Autres moteurs iOS** | Parakeet est disponible via sherpa-onnx (Swift) ou FluidAudio (CoreML/ANE, plus rapide, non vérifié). WhisperKit turbo (626 Mo) sert de repli (cf. 02, §4). Le portage Core AI de Nemotron reste non fusionné (cf. 02, §1). | On compare en phase 0 iOS : SpeechTranscriber, Parakeet/FluidAudio et Parakeet/sherpa-onnx. |
| **Stockage chiffré** | SQLCipher sous KMP/iOS est fragile, avec un risque de liaison silencieuse au SQLite du système (cf. 04, §1.3 et §2.1). | Stockage iOS natif en Swift (SQLCipher, avec GRDB par exemple, non vérifié), test automatique « le fichier ne commence pas par `SQLite format 3` », Keychain en mode `AfterFirstUnlockThisDeviceOnly` (cf. 04, §2.2). |
| **Mac obligatoire** | Xcode, la signature et la publication ne tournent que sous macOS (non vérifié dans les notes, connaissance générale). | Il faut au moins un Mac Apple Silicon pour le développeur et un ou deux iPhones physiques (un récent, un iPhone milieu de gamme de 3 à 4 ans) pour mesurer l'ASR. Un service Mac d'intégration continue dans le cloud verrait le code source, pas les données des utilisateurs : acceptable, mais à faire valider. |
| **Distribution** | Connaissance générale, non vérifiée dans les notes : **App Store** = publication publique, revue Apple, étiquettes de confidentialité. **TestFlight** = bêta seulement, builds limités dans le temps (environ 90 jours) : ce n'est pas un canal durable. **Apple Developer Enterprise Program** = distribution interne, éligibilité restreinte et contrôlée par Apple. **App personnalisée via Apple Business Manager + MDM** = voie usuelle pour une appli interne. | Recommandation (non vérifiée) : un compte Apple Developer au nom de l'organisation, une distribution privée via Apple Business Manager et le MDM de l'entreprise, et TestFlight pour le pilote. Prévoir 1 à 3 semaines de délai administratif (compte D-U-N-S, revue). |
| **Coût de développement** | Avec la stack retenue, l'interface SwiftUI et les briques natives (audio, ASR, stockage) sont à écrire. Seul le domaine est partagé via KMP. | Section 3 : 12 à 19 p.-sem. |

### 2.3 Conditions pour lancer iOS (go/no-go)

1. Au moins 20 % des utilisateurs cibles ont un iPhone professionnel géré par le MDM (question en section 6).
2. Un Mac et un compte Apple Developer d'organisation sont disponibles.
3. En phase 0 iOS, SpeechTranscriber ou Parakeet atteint les mêmes seuils de WER que sur Android (section 5.1), avec une transcription au premier plan de **≤ 15 min pour 1 h d'audio** sur l'iPhone milieu de gamme.
4. La V1 Android est acceptée en pilote.

---

## 3. Chiffrage (un développeur expérimenté, en p.-sem.)

Hypothèses : un développeur Kotlin/Android confirmé qui connaît aussi Swift pour l'iOS. Fourchette basse = composants réutilisés sans difficulté, pas de surprise en phase 0. Fourchette haute = un repli de moteur, deux cycles de corrections sur appareils. Non compris : AIPD, DPA, consultation du CSE (temps du DPO et du juriste), pentest externe (prestation).

### 3.1 Phase 0 et MVP Android

| Lot | Contenu | Bas | Haut |
|---|---|---|---|
| P0 | Spike et benchmark (section 5.1) : lecture du code de Private Meeting Notes et HearoPilot, corpus, mesures ASR et LLM, test d'enregistrement de 2 h, capture réseau | 2 | 3 |
| A1 | Socle : projet multi-modules (domaine en Kotlin pur), CI, règles de dépendances, contrôle du manifeste fusionné, client HTTP unique avec liste blanche | 1 | 1,5 |
| A2 | Enregistrement long : service de premier plan micro, blocs chiffrés de 1 à 5 min, reprise, interruptions (appel, Bluetooth), encodage Opus/AAC | 2 | 3 |
| A3 | ASR : téléchargement et vérification du modèle, VAD, file reprenable, progression, gestion de la RAM et de la chaleur, Canary en repli | 2 | 3 |
| A4 | Stockage chiffré : Room + SQLCipher, clés enveloppées par le Keystore, sauvegardes désactivées, diagnostic au démarrage | 1,5 | 2 |
| A5 | Historique : `audit_event` dans la même transaction, versions immuables, corbeille et purge avec effacement cryptographique | 1 | 1,5 |
| A6 | Client LLM OpenAI et Anthropic : clés, test de la clé, streaming SSE, sorties structurées, map-reduce, estimation du coût, gestion des erreurs | 2 | 3 |
| A7 | Gabarits : 5 formats intégrés, gabarits utilisateur à variables, plusieurs résumés par réunion, régénération | 1,5 | 2,5 |
| A8 | Interface : réunions, enregistrement, transcription (lecture et correction), résumés, gabarits, réglages, export Markdown et PDF, partage | 2 | 3 |
| A9 | Recette sur 3 appareils, corrections, documentation d'exploitation | 1,5 | 2,5 |
| **Total** | **Phase 0 + MVP Android** | **16,5** | **25** |

### 3.2 iOS (après la V1 Android)

| Lot | Contenu | Bas | Haut |
|---|---|---|---|
| I0 | Spike iOS : session audio de 2 h, comparaison SpeechTranscriber / Parakeet | 1 | 1,5 |
| I1 | Extraction du domaine en module KMP (gabarits, audit, client LLM sous Ktor, map-reduce), export du framework iOS | 1,5 | 2,5 |
| I2 | Environnement iOS : Mac, signature, CI, Apple Business Manager, TestFlight | 1 | 1,5 |
| I3 | Enregistrement : `AVAudioSession`, blocs chiffrés, interruptions | 1,5 | 2,5 |
| I4 | ASR iOS au premier plan ou au fil de l'eau, selon le moteur retenu | 1,5 | 3 |
| I5 | Stockage SQLCipher natif + Keychain, protection des fichiers, exclusion des sauvegardes | 1,5 | 2 |
| I6 | Interface SwiftUI avec les fonctions du MVP | 3 | 4,5 |
| I7 | Recette sur 2 iPhones, corrections | 1 | 1,5 |
| **Total** | **iOS** | **12** | **19** |

Pour comparaison, iOS sous Flutter (si la stack était inversée) coûterait environ 5 à 8 p.-sem. pour I0, I2, I3, I4, I7 et une adaptation légère de l'interface. L'Android MVP serait à peu près au même coût, à 1 p.-sem. près pour les ponts natifs. Estimation non vérifiée.

### 3.3 Durcissement pour un usage en entreprise

| Lot | Contenu | Android | iOS (en plus) |
|---|---|---|---|
| E1 | Réseau : liste blanche stricte, `network-security-config`, épinglage des CA intermédiaires avec pins de secours, journal des échecs TLS, test PCAPdroid/mitmproxy et analyse Exodus en CI (cf. 05, §1.4) | 1 – 1,5 | 0,5 – 1 |
| E2 | Protections locales : verrou biométrique, `FLAG_SECURE`, purge automatique (rétention), suppression de l'audio après validation, export et import d'une archive chiffrée (Argon2id) | 1,5 – 2 | 1 – 1,5 |
| E3 | Politiques MDM (configurations gérées) : fournisseurs autorisés, mode local imposé, durée de rétention, désactivation du partage | 1 – 2 | 0,5 – 1 |
| E4 | Classification des réunions, blocage de l'envoi pour les réunions sensibles, pseudonymisation (expressions régulières + liste des participants) | 1,5 – 2,5 | 0,5 – 1 (logique KMP) |
| E5 | Corrections après pentest externe, SBOM, build reproductible, dossier technique pour l'AIPD | 1,5 – 2,5 | 0,5 – 1 |
| **Total** | | **6,5 – 10,5** | **3 – 5,5** |

### 3.4 Récapitulatif

| Trajectoire | p.-sem. |
|---|---|
| Phase 0 + MVP Android | 16,5 – 25 |
| + compléments fonctionnels V1 (diarisation, import de skills, partage vers l'appli officielle) | + 3 – 5 |
| + durcissement entreprise Android | + 6,5 – 10,5 |
| **V1 Android entreprise** | **26 – 40,5** |
| + iOS + durcissement iOS | + 15 – 24,5 |
| **Android + iOS entreprise** | **41 – 65** |

Avec un seul développeur, on peut compter environ 6 à 9 mois calendaires pour la V1 Android, et 10 à 15 mois avec iOS (non vérifié : dépend de la disponibilité réelle du développeur et des délais du DPO). Une réserve de 15 à 20 % pour les imprévus est recommandée en plus.

---

## 4. Registre des risques

Probabilité (P) et impact (I) : F = faible, M = moyen, É = élevé.

| # | Risque | P | I | Atténuation | Test go/no-go |
|---|---|---|---|---|---|
| R1 | Qualité de l'ASR insuffisante sur de vraies réunions en français (bruit, chevauchements, micro posé sur la table : WER réel 2 à 3 fois FLEURS, cf. 02, §2) | M | É | Corpus réel en phase 0, conseils de placement du micro, correction manuelle de la transcription, Canary ou Nemotron comparés | Phase 0 : WER Parakeet ≤ 20 % en médiane sur le corpus, et résumé jugé exploitable sur au moins 4 réunions sur 5 |
| R2 | Performances, RAM ou chaleur insuffisantes sur Android milieu de gamme, ou service tué pendant l'ASR (cf. 01, HearoPilot ; 04, §9) | M | É | Segments VAD, file reprenable, gestionnaire de RAM, option « en charge », Canary 180M en repli | Phase 0 : RTF ≤ 0,5 et pic RAM ≤ 1,5 Go sur le téléphone milieu de gamme, 1 h traitée sans plantage 3 fois de suite |
| R3 | Perte d'enregistrement : arrêt forcé par le constructeur, démarrage impossible depuis l'arrière-plan (Android 14+), interruptions (cf. 04, §1.2) | M | É | Service micro démarré depuis l'interface, blocs de 1 à 5 min écrits au fil de l'eau, reprise de session, guide « désactiver l'optimisation batterie » par marque | Phase 0 : 5 enregistrements de 2 h écran verrouillé, au plus 1 bloc perdu au total |
| R4 | Non-conformité RGPD : pas de DPA, clés personnelles, transfert vers les États-Unis (DPF contesté, C-703/25 P), Anthropic sans région UE, information des participants, CSE (cf. 05, §3 et §4) | É | É | Clés d'organisation, DPA signé, AIPD, mode local par défaut, information au début de la réunion, OpenAI UE si exigé | **Bloquant pour le pilote** : DPA signé avec le fournisseur retenu et AIPD validée par le DPO |
| R5 | Perte de la clé (réinstallation, restauration, changement d'appareil) et donc perte des données (cf. 04, §2.4) | M | É | Sauvegardes système désactivées, diagnostic au démarrage sans écrasement, export chiffré par l'utilisateur | Recette : réinstallation puis restauration d'un export, 100 % des réunions relues |
| R6 | Chiffrement inactif sans qu'on le voie (mauvaise liaison SQLCipher, surtout sur iOS) (cf. 04, §2.1) | F (Android) / M (iOS) | É | Test automatique en CI et au démarrage : en-tête du fichier et `PRAGMA cipher_version` | Échec du test = build bloqué |
| R7 | Fuite vers un tiers via une dépendance transitive (SDK Google, télémétrie) ou via l'hébergeur du modèle (cf. 05, §1.3 et §1.4) | M | É | Client HTTP unique avec liste blanche, revue du manifeste fusionné, Exodus en CI, miroir du modèle ou Play Asset Delivery | Phase 0 puis chaque version : capture réseau d'un parcours complet, **aucun** hôte hors liste blanche |
| R8 | Hallucinations ou omissions dans le résumé (décisions inventées) | M | M | Sortie structurée avec horodatages sources, relecture humaine obligatoire avant diffusion, régénération versionnée | Phase 0 : 0 décision inventée sur les 5 réunions du corpus, vérifié par un participant |
| R9 | Injection de prompt via la transcription ou un skill importé (cf. 04, §5.2 et §5.3) | M | M | Délimiteurs et consigne explicite, aucun déclenchement d'action, scripts de skill jamais exécutés, avertissement à l'import | — |
| R10 | Changements chez les fournisseurs : modèle retiré, prix, conditions, politique BYOK d'OpenAI non vérifiée (cf. 03, §1.4) | M | M | Abstraction `LlmProvider`, table des modèles et des prix modifiable, deux fournisseurs, veille sur les conditions | — |
| R11 | iOS : transcription impossible en arrière-plan, utilisateurs qui quittent l'appli (cf. 04, §1.2) | É (si iOS) | M | Transcription au premier plan ou pendant l'enregistrement, SpeechTranscriber | Section 2.3, condition 3 |
| R12 | iOS : organisation (pas de Mac, compte Apple, Apple Business Manager, délais de revue) | M | M | Décision prise tôt, compte d'organisation, distribution privée | Section 2.3, condition 2 |
| R13 | Un seul développeur : arrêt du projet en cas d'absence, pas de relecture croisée | É | M | Documentation des décisions (ADR), tests automatisés, revue de code externe ponctuelle | — |
| R14 | Licences : OpenMDW-1.1 (Nemotron) non analysée, attribution CC-BY-4.0, mentions Apache-2.0 (cf. 01, §2 et §8) | F | M | Fichier NOTICE, écran « licences », Nemotron non embarqué tant que le juriste n'a pas validé | — |
| R15 | Espace de stockage : 640 Mo de modèle et l'audio (environ 22 Mo pour 2 h en Opus, cf. 04, §2.3) sur des appareils pleins | M | F | Vérifier l'espace avant téléchargement, suppression de l'audio après validation, variante int4 (410 Mo) | — |
| R16 | Coût LLM d'un map-reduce sur des réunions longues | F | F | Estimation affichée avant l'envoi, passage unique par défaut, plafond de dépenses sur la clé | — |

**Les 5 risques principaux** : R4 (RGPD), R1 (qualité de l'ASR), R2 (performances Android), R3 (perte d'enregistrement), R7 (fuite vers un tiers).

---

## 5. Plan par phases

### 5.1 Phase 0 : spike et benchmark (2 à 3 semaines)

**Matériel et corpus :**
- 3 à 5 vraies réunions en français, de 30 à 90 min, enregistrées au téléphone posé sur la table, avec le consentement des participants (cf. 05, §4.1).
- Pour chacune, au moins deux extraits de 15 min transcrits à la main comme référence.
- Appareils : un Android milieu de gamme (6 à 8 Go de RAM), un Android représentatif du bas du parc, et un iPhone si iOS est envisagé (section 6).

**Moteurs mesurés :** Parakeet v3 int8, Canary 180M Flash ; Nemotron int8 seulement si la transcription en direct est demandée ; SpeechTranscriber et Parakeet/FluidAudio si iOS est envisagé.

**Critères go/no-go.** Les seuils sont fixés par cette note, à faire valider par l'utilisateur.

| Critère | Mesure | Go | No-go → repli |
|---|---|---|---|
| Qualité ASR | WER normalisé sur les extraits de référence | Médiane ≤ 20 %, aucune réunion > 30 % | Essayer Canary ou Nemotron, sinon arrêt ou mode « dictée » |
| Vitesse | RTF sur l'Android milieu de gamme | ≤ 0,5 (1 h traitée en ≤ 30 min), cible 0,2 | Canary 180M ; si RTF > 1, no-go Android |
| Mémoire | Pic de RAM pendant l'ASR | ≤ 1,5 Go, 0 arrêt par l'OS sur 3 passes de 1 h | Segments plus courts, int4 |
| Chaleur et batterie | Consommation, fréquence CPU | Enregistrement d'1 h ≤ 10 % de batterie, transcription d'1 h ≤ 15 %, sans arrêt thermique | Imposer « transcrire en charge » |
| Enregistrement | 5 sessions de 2 h écran verrouillé, avec 1 appel entrant | Au plus 1 bloc de 5 min perdu au total, reprise automatique | Revoir le service ; no-go si les pertes ne se maîtrisent pas |
| Utilité du résumé | Résumé « compte rendu » et « décisions + actions » sur les 5 réunions, chez les 2 fournisseurs | Au moins 4 sur 5 jugés « diffusables après relecture légère » par un participant, 0 décision inventée | Revoir les prompts ; si l'ASR est en cause, voir la ligne 1 |
| LLM technique | Transcription de 2 h | Passage unique réussi chez les deux fournisseurs, JSON structuré valide ≥ 95 % sur 20 appels, coût par réunion ≤ plafond fixé par l'utilisateur | Map-reduce |
| Réseau | Capture PCAPdroid d'un parcours complet | Seulement `api.openai.com` et/ou `api.anthropic.com` (plus le miroir du modèle au premier lancement) | Retirer la dépendance fautive |
| Chiffrement | Fichier de base de données | Ne commence pas par `SQLite format 3`, `cipher_version` non nul | Corriger la liaison |
| Code existant | Lecture de Private Meeting Notes et HearoPilot | Liste des composants repris, avec leur licence | Développement neuf intégral (+1 à 2 p.-sem.) |

Livrables : un rapport de mesures et la décision de stack (confirmation de Kotlin ou bascule sur Flutter, section 1.1).

### 5.2 MVP (Android, usage pilote interne, 5 à 10 utilisateurs)

**Inclus :**
- Création, modification, suppression (corbeille) et recherche de réunions.
- Enregistrement long en arrière-plan, audio chiffré en blocs.
- Transcription locale avec Parakeet, en batch reprenable ; correction manuelle versionnée.
- Clés API OpenAI et Anthropic (organisation) dans le Keystore ; test de la clé ; `store:false`.
- 5 formats intégrés (compte rendu, décisions + actions, synthèse exécutive, points clés, e-mail de suivi) et gabarits utilisateur avec variables `{{…}}`.
- Plusieurs résumés par réunion, régénération qui crée une nouvelle version.
- Journal d'audit pour chaque création, modification et suppression ; versions immuables.
- Mode « local seulement » par réunion.
- Base SQLCipher, sauvegardes désactivées, liste blanche réseau.
- Export Markdown et PDF, partage système avec avertissement.
- Rappel de l'annonce de l'enregistrement en début de séance (cf. 05, §4.1).

**Exclus :**
- iOS, transcription en direct, diarisation, import de skills, pseudonymisation.
- Partage vers l'appli officielle, Sign in with ChatGPT, DOCX.
- Politiques MDM, verrou biométrique, épinglage de certificats, synchronisation entre appareils.

**Critères d'acceptation :**
1. Une réunion de 2 h enregistrée écran verrouillé donne un audio complet (au plus 1 bloc perdu), sur les 2 appareils Android de référence.
2. La transcription d'1 h se termine en ≤ 30 min sur le milieu de gamme. Après un arrêt forcé, elle reprend au segment où elle s'était arrêtée.
3. On peut produire au moins 3 résumés de formats différents pour une même réunion. Chacun garde son modèle, son fournisseur, son nombre de tokens et la version du gabarit utilisée.
4. Chaque création, modification ou suppression d'une réunion, d'une transcription, d'un résumé ou d'un gabarit produit exactement un `audit_event`, écrit dans la même transaction, sans contenu sensible (test automatisé).
5. La capture réseau d'un parcours complet ne montre aucun hôte en dehors de la liste blanche. En mode « local seulement », elle ne montre aucune connexion.
6. Le fichier de base est illisible sans la clé. La clé API n'apparaît ni dans la base, ni dans les journaux, ni dans une sauvegarde (vérification par `adb backup` ou équivalent).
7. Un gabarit utilisateur avec une variable obligatoire manquante bloque l'envoi avec un message clair.
8. Les pilotes jugent au moins 80 % des résumés « diffusables après relecture légère ».

### 5.3 V1 (Android pour l'entreprise)

**Contenu :**
- Durcissement E1 à E5 : liste blanche stricte, épinglage, verrou biométrique, rétention et purge, politiques MDM, classification des réunions et blocage de l'envoi, pseudonymisation, export chiffré.
- Diarisation sherpa-onnx (pyannote + CAM++), avec saisie du nombre de locuteurs.
- Import de skills `SKILL.md` sans exécution de scripts.
- Partage vers l'appli officielle, activable par politique.
- Résidence UE d'OpenAI, si elle est demandée.
- Transcription au fil de l'eau pendant l'enregistrement, si la phase 0 montre que la chaleur le permet.

**Critères d'acceptation :**
1. Pentest externe sans vulnérabilité critique ni élevée ouverte.
2. AIPD validée et DPA archivé (prérequis).
3. Une politique MDM qui impose « local seulement » rend tout envoi impossible ; test sur un appareil géré.
4. La pseudonymisation remplace au moins 95 % des noms des participants déclarés sur le corpus. Le taux réel est communiqué au DPO.
5. Après une purge, l'audio est irrécupérable (clé détruite), et l'audit garde l'événement sans son contenu.
6. Sur le corpus, l'attribution des locuteurs est correcte pour au moins 80 % du temps de parole quand le nombre de locuteurs est donné. C'est un seuil à valider ; la diarisation sur de vraies réunions françaises n'a pas été mesurée (cf. 02, §3).
7. Un skill contenant `scripts/` est importé sans ses scripts, avec un avertissement, et l'import reste tracé dans l'audit.

### 5.4 V2

- **iOS** (sections 2 et 3.2), si les conditions de la section 2.3 sont remplies.
- Transcription en direct (Nemotron streaming ou SpeechTranscriber sur iOS), si le besoin est confirmé.
- Sign in with ChatGPT, seulement après réponse écrite d'OpenAI (cf. 03, §4).
- Export DOCX ; suivi des actions (`summary_item`) avec échéances et filtres.
- Synchronisation entre appareils : **hors périmètre** tant que C8 interdit tout serveur. Seul l'export ou l'import chiffré manuel est possible.

**Critères d'acceptation iOS :**
1. Mêmes critères 1 à 7 que le MVP, sur deux iPhones.
2. Transcription d'1 h en ≤ 15 min au premier plan.
3. Distribution privée via le MDM opérationnelle.

---

## 6. Questions ouvertes pour l'utilisateur

**Équipe et budget**
1. Qui développe, et avec quelles compétences (Kotlin, Swift, Dart) ? Un seul développeur ou plusieurs ? La réponse peut renverser la décision de stack (section 1.1).
2. Quel budget et quelle échéance ? Une V1 Android entreprise représente 26 à 40 p.-sem. ; avec iOS, 41 à 65.

**Parc et plateformes**
3. Quel parc d'appareils : modèles Android, RAM, versions ? Quelle part d'iPhones ? Les téléphones sont-ils professionnels ou personnels (BYOD) ?
4. iOS est-il nécessaire, et pour quand ? Un Mac et un compte Apple Developer d'organisation sont-ils disponibles ?

**MDM et distribution**
5. Quel MDM (Intune, Workspace ONE, etc.) ? Accepte-t-il les configurations gérées Android et les applis personnalisées Apple Business Manager ?
6. Quel canal de distribution : Google Play géré (appli privée), APK installé via le MDM ou Play Store public ? Ce choix détermine la façon de livrer le modèle de 640 Mo (section 1.3).
7. Un miroir HTTPS interne est-il possible pour le modèle ASR ? Sinon, Hugging Face ou le store sont-ils acceptés comme tiers technique ?

**Juridique et fournisseurs**
8. Des DPA sont-ils signés avec OpenAI et/ou Anthropic, sur un compte d'organisation ? Le ZDR est-il demandé ?
9. Quel fournisseur privilégier ? La résidence UE est-elle exigée ? Si oui, OpenAI EU, car Anthropic en direct n'offre pas de région UE (cf. 05, §3.2).
10. Le DPO a-t-il été saisi ? Une AIPD est-elle prévue ? Le CSE doit-il être consulté ?
11. Les clés personnelles des salariés sont-elles interdites ? Les clés d'organisation seront-elles distribuées par projet ou par utilisateur ?

**Usage**
12. La transcription en direct est-elle nécessaire, ou un compte rendu après la réunion suffit-il ? La réponse décide de l'évaluation de Nemotron (section 1.3).
13. Confirmez-vous l'abandon de Nemotron comme moteur principal au profit de Parakeet ? Nemotron figurait comme cible dans C3 (cf. 01).
14. Quelle durée typique et maximale des réunions ? Combien de participants ? Réunions en présentiel seulement, ou aussi en visio avec le haut-parleur du téléphone ?
15. Faut-il identifier les locuteurs (diarisation) dès le MVP ?
16. Quelles durées de conservation : audio supprimé après validation du compte rendu ou au bout de N jours ? Quelle durée pour les transcriptions et les résumés ?
17. Quels formats de résumé sont prioritaires ? Faut-il des gabarits « maison » existants à intégrer ? DOCX est-il indispensable ?
18. Quelle grille de classification des réunions existe déjà (public, interne, confidentiel, secret) ?
19. Quel plafond de coût LLM par réunion ou par mois ?
20. Une version « local seulement », sans permission `INTERNET`, est-elle utile pour certains services ?
