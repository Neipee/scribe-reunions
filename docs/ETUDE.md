# Scribe Réunions — Étude préalable (phase 1)

Date : 2026-10-27 · Statut : étude, aucun code d'application · Notes détaillées : [`notes/`](notes/)

> Aucun moteur n'a été installé ni mesuré. Les chiffres viennent de sources publiées ; les points marqués « non vérifié » dans les notes le restent. Ce document n'est pas un avis juridique.

## Verdict

**À construire en s'appuyant sur des briques existantes.**

Aucune application, mobile ou desktop, ne réunit les contraintes : transcription locale sur téléphone + synthèse via OpenAI/Anthropic + plusieurs synthèses par réunion + modèles personnalisés + historique du CRUD + aucun autre tiers. Chaque projet existant en couvre une partie (cf. [01](notes/01-existant.md)).

On ne forke pas : on crée un dépôt neuf et on reprend des composants sous licence Apache-2.0 (moteur sherpa-onnx, gestion audio/mémoire de projets Android existants).

## 1. Existant (cf. [01-existant](notes/01-existant.md))

| Projet | Ce qu'il apporte | Ce qui manque |
|---|---|---|
| [Private Meeting Notes](https://github.com/matthesschramm/private-meeting-notes) (Android, Kotlin, Apache-2.0) | Enregistrement, Parakeet 0.6B local, diarisation, aucune permission réseau (testé) | Synthèse par LLM local seulement, pas d'API OpenAI/Anthropic. Projet jeune : 1 développeur, 0 étoile, 1 téléphone testé |
| [HearoPilot](https://github.com/Helldez/HearoPilot-App) (Android, Apache-2.0, ~105 ★) | sherpa-onnx + Parakeet, sessions éditables, gestion mémoire | Inactif depuis 2026-06 ; 4 modes de synthèse figés ; LLM local seulement |
| [Anarlog (ex-Hyprnote)](https://github.com/fastrepl/anarlog) (desktop, MIT, ~9,6 k ★) | Meilleure référence pour le LLM : clé API, plusieurs fournisseurs, modèles de synthèse, SQLite | Mobile limité à la consultation (bêta) ; Tauri/Rust ; synchro cloud ; une partie sous licence commerciale |
| [Meetily](https://github.com/Zackriya-Solutions/meetily) (desktop) | Transcription locale + LLM | Pas de mobile ; modèles personnalisés réservés à l'offre payante |

Manques communs : aucun projet mobile n'associe ASR local et API OpenAI/Anthropic, aucun n'a d'historique du CRUD, et plusieurs synthèses par réunion ne sont confirmées nulle part.

## 2. Transcription : Nemotron et alternatives (cf. [02-asr](notes/02-asr.md))

**Nemotron 3.5 ASR streaming 0.6B** ([fiche](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b)) :
- **Français** : oui (fr-FR, fr-CA), avec un taux d'erreur (WER FLEURS) de 9,0 à 11,0 % selon la taille des blocs.
- **Fiche technique** : 600 M de paramètres, conçu pour le streaming, ponctuation intégrée.
- **Licence** : OpenMDW, usage commercial permis.
- **Cible** : NVIDIA ne le vise officiellement que sur GPU sous Linux.
- **Mobile** : pas de version légère int8 officielle (GGUF q8 de 742 Mo, ONNX communautaire de 2,6 Go).
  - Prise en charge par sherpa-onnx encore en branche de développement.
  - Seule mesure sur téléphone : un portage communautaire sur iPhone 17 Pro. Aucune mesure Android.
- **Décision : option**, à évaluer seulement si on veut la transcription en direct.

**Moteur recommandé : [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), en int8, via [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx), en traitement après la réunion.**
- WER français FLEURS 5,15 % et MLS 4,97 %, soit environ 40 % d'erreurs en moins que Nemotron.
- Environ 640 Mo, horodatage au mot, licence CC-BY-4.0.
- Déjà utilisé sur Android par les projets cités plus haut.

**Secours :**
- Android modeste : Canary 180M Flash (~154 Mo).
- iOS : Apple SpeechTranscriber (iOS 26+, gère le français, mais aucun WER publié) ou WhisperKit large-v3-turbo.

**Écartés pour le français** : Vosk, Moonshine, la reconnaissance Android intégrée, Whisper small ou plus petit, Voxtral (trop lourd).

| | Streaming en direct | Après la réunion (recommandé) |
|---|---|---|
| Usage | Sous-titres pendant la réunion | Transcription complète après l'arrêt |
| Moteur | Nemotron (option), SpeechTranscriber (iOS) | Parakeet v3 int8 |
| Qualité FR | Moins bonne | Meilleure |
| Batterie et chaleur | Charge continue pendant 1 à 2 h | Calcul ponctuel, de préférence téléphone en charge, avec reprise possible |

Pour les réunions de 1 à 2 h : on enregistre l'audio brut en blocs chiffrés. On le découpe ensuite sur les silences en segments de 10 à 30 s, et le traitement peut reprendre là où il s'est arrêté. Diarisation (qui parle) : pyannote via sherpa-onnx, ~40 Mo, qualité non mesurée en français.

## 3. Connexion aux LLM (cf. [03-llm-connexion](notes/03-llm-connexion.md))

| Mode | Statut | Remarque |
|---|---|---|
| Clé API Anthropic, appel direct depuis l'appli | **Autorisé** | [Commercial Terms](https://www.anthropic.com/legal/commercial-terms) ; pas d'entraînement par défaut, suppression sous 30 jours ; **pas de région UE** en accès direct |
| Clé API OpenAI, appel direct | **Autorisé** (contrat non relu, erreur 403) | Pas d'entraînement par défaut, `store:false` ; [résidence UE](https://help.openai.com/en/articles/10503543-data-residency-for-the-openai-api) possible, sur approbation |
| Partage manuel vers l'appli officielle ChatGPT ou Claude | **Autorisé** | Les données suivent alors les réglages grand public du compte |
| Connexion avec un abonnement Claude.ai dans une appli tierce | **Interdit** | [Legal & compliance Claude Code](https://code.claude.com/docs/en/legal-and-compliance) et Consumer Terms ; appliqué depuis 2026-01 |
| Réutiliser des jetons Codex ou Claude Code, ou une session web | **Interdit** | — |
| [Sign in with ChatGPT](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt) avec usage du forfait | **Pas clair** | Programme officiel, mais plusieurs inconnues (voir ci-dessous) |
| Connecteurs MCP / apps ChatGPT | Autorisé mais **exclu** | Exige un serveur joignable sur Internet, donc un tiers |

Inconnues sur Sign in with ChatGPT : liste d'attente pour les applis commerciales, mobile non documenté, et régime des données (API ou grand public) non précisé.

Les clés API sont stockées dans Android Keystore (Tink + DataStore) ou dans le Keychain iOS, jamais dans la base de données. Conseils à l'utilisateur : une clé dédiée, un plafond de dépenses et une date d'expiration.

## 4. Architecture (cf. [04-architecture](notes/04-architecture.md), arbitrée en [06](notes/06-faisabilite.md))

Les notes 04 et 06 divergent sur la stack :
- **04** penchait pour **Flutter**, pour une seule base Android + iOS.
- **06** tranche pour **Kotlin natif** : Android est le seul impératif et les meilleures bases à réutiliser sont en Kotlin.
- On écrit le domaine en Kotlin pur pour garder ouverte la voie KMP vers iOS.
- **Bascule vers Flutter** si iOS devient obligatoire à la fin de la phase 0 et que l'équipe maîtrise Dart. iOS coûterait alors environ 5 à 8 personnes-semaines de moins.

Composants retenus :
- **Enregistrement** : service de premier plan de type `microphone` (Android 14+ : démarrage seulement au premier plan), blocs audio de 1 à 5 min chiffrés au fil de l'eau.
- **Stockage** : SQLite + SQLCipher (Room), fichiers audio chiffrés, clés dans le Keystore. Sauvegardes système désactivées ; export chiffré à l'initiative de l'utilisateur.
- **Historique du CRUD** :
  - un journal `audit_event` en ajout seul, écrit dans la même transaction que chaque modification ;
  - des versions immuables pour les synthèses, gabarits et skills ;
  - une corbeille avec suppression logique ;
  - le journal ne contient jamais le texte des transcriptions ni des synthèses (identifiants, noms de champs et empreintes seulement) ;
  - pas d'event sourcing complet.
- **Modèle de données** : `Meeting` 1–n `Recording` (blocs) → `Transcript` (segments horodatés, locuteur). `Meeting` 1–n `Summary`, chaque synthèse portant :
  - sa version ;
  - le fournisseur et le modèle utilisés ;
  - une copie du prompt ;
  - son coût en jetons.

  S'y ajoutent `PromptTemplate` / `Skill` (intégré ou utilisateur, variables, versions), `ProviderConfig` (sans secret) et `AuditEvent`.
- **Synthèses** :
  - **Formats prédéfinis** : compte rendu, décisions + actions (sortie JSON structurée), résumé exécutif, puces, courriel de suivi.
  - **Personnalisées** : gabarits avec variables, et skills au format `SKILL.md` importables comme fichiers, en instructions seulement, sans exécution de scripts.
  - **Longues réunions** : map-reduce quand la transcription dépasse le contexte.
  - **Export** : Markdown, PDF, DOCX, partage.

## 5. Confidentialité (cf. [05-confidentialite](notes/05-confidentialite.md))

**Flux** :
1. Le micro alimente l'ASR local, qui écrit dans le stockage chiffré.
2. Une pseudonymisation optionnelle remplace les noms.
3. **La transcription seule** (jamais l'audio) part vers `api.openai.com` / `eu.api.openai.com` ou `api.anthropic.com`.
4. La synthèse revient et les noms sont réassociés en local.

Seule autre connexion : le téléchargement unique du modèle ASR. L'hébergeur voit alors l'adresse IP, sans aucune donnée utilisateur. Variantes possibles : modèle embarqué, Play Asset Delivery ou miroir interne de l'entreprise.

Mesures clés :
1. Aucun SDK de télémétrie ni de crash reporting (pas de Firebase ni de Sentry), aucune reconnaissance vocale cloud de l'OS.
2. Un seul client HTTP, avec une liste fermée de domaines ; épinglage de CA intermédiaires avec pins de secours.
3. Vérification avec PCAPdroid / mitmproxy (capture réseau) et Exodus (analyse statique).
4. SQLCipher et audio chiffré, verrouillage biométrique, `allowBackup=false` + `dataExtractionRules`, `FLAG_SECURE`, effacement par destruction de clé.
5. Mode **« local seulement »** choisi par réunion (aucun appel LLM) et option de suppression de l'audio après transcription.

**Usage en entreprise** :
- **Consentement** : annoncer l'enregistrement et permettre de refuser ([art. 226-1 C. pén.](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006417929)).
- **Contrats** : OpenAI et Anthropic sont des sous-traitants RGPD (art. 28). Il faut des DPA signés, des clés d'organisation (pas de clés personnelles) et une inscription au registre.
- **Analyses** : une AIPD et l'avis du DPO, plus le CSE si l'outil peut servir au contrôle des salariés.
- **Hors UE** : Anthropic n'a pas de région UE en accès direct, et le Data Privacy Framework fait l'objet d'un recours devant la CJUE.
- **Réunions sensibles** : jamais vers le cloud. Mode local obligatoire pour les réunions classées « confidentiel ».
- La pseudonymisation ne vaut pas anonymisation.

## 6. Faisabilité, effort, MVP (cf. [06-faisabilite](notes/06-faisabilite.md))

**Android seul : faisable. iOS : faisable après la V1 Android.**

iOS impose plusieurs contraintes :
- un Mac pour compiler ;
- une distribution privée via Apple Business Manager et le MDM ;
- une transcription faite appli ouverte, car iOS limite le calcul en arrière-plan.

Estimations sans mesure, pour un développeur expérimenté :

| Lot | Personnes-semaines |
|---|---|
| Phase 0 (benchmark) + MVP Android | 16,5 – 25 |
| V1 Android entreprise (cumul, durcissement inclus) | 26 – 40,5 |
| iOS en plus | 15 – 24,5 |
| **Total Android + iOS entreprise** | **41 – 65** |

**Phase 0, avant toute ligne de code d'application** : banc d'essai sur 3 à 5 vraies réunions en français, enregistrées au téléphone. Critères de go :

| Critère | Seuil |
|---|---|
| WER médian | ≤ 20 % |
| Durée de traitement d'1 h d'audio | ≤ 30 min |
| Pic de mémoire | ≤ 1,5 Go |
| Perte d'enregistrement (5 sessions de 2 h, écran verrouillé) | ≤ 1 bloc perdu |
| Capture réseau | Aucun hôte hors liste blanche |

**MVP Android** :
- enregistrement long fiable ;
- transcription Parakeet après la réunion ;
- synthèses via clé API (OpenAI et Anthropic) en 5 formats, avec gabarits personnalisés et plusieurs synthèses par réunion ;
- historique du CRUD et corbeille ;
- stockage chiffré et mode local seulement ;
- export.

**V1** : skills importables, diarisation, partage vers l'appli officielle, pseudonymisation, durcissement pour l'entreprise.

**V2** : iOS, Sign in with ChatGPT (si les conditions sont clarifiées), streaming en direct avec Nemotron (si besoin).

## Risques majeurs

| Risque | Parade |
|---|---|
| RGPD : pas de DPA, pas de région UE chez Anthropic, transferts vers les États-Unis | Bloquant pour le pilote tant qu'il n'y a pas de DPA signé, d'AIPD validée et de choix du fournisseur (OpenAI UE ?) |
| Qualité ASR sur de vraies réunions FR (bruit, chevauchements, jargon) | Critère de go en phase 0 |
| Performances Android : chaleur, mémoire, durée sur un téléphone milieu de gamme | Banc d'essai sur les appareils réels de l'entreprise |
| Perte d'enregistrement : système qui tue l'appli, interruptions | Blocs chiffrés au fil de l'eau, test de 2 h écran verrouillé |
| Fuite vers un tiers via un SDK ou une dépendance | Aucun SDK tiers, liste fermée de domaines, capture réseau en recette |
| Abonnements : attente d'une connexion par abonnement qui est interdite (Claude) ou floue (ChatGPT) | Clé API d'organisation et partage manuel ; expliquer le choix dans l'appli |

## Questions ouvertes pour l'utilisateur

1. Compétences de l'équipe (Kotlin, Swift, Dart), budget et échéance ?
2. Parc d'appareils : part d'iPhones, modèles Android ? Mac et compte Apple d'organisation disponibles ?
3. MDM et canal de distribution (Play privé, APK, Apple Business Manager) ? Miroir interne possible pour le modèle de 640 Mo ?
4. DPA signés avec OpenAI et/ou Anthropic ? Fournisseur préféré ? Résidence UE exigée, ce qui oriente vers OpenAI UE ?
5. Avis du DPO, AIPD, consultation du CSE ?
6. La transcription en direct est-elle nécessaire, ou le traitement après la réunion suffit-il ? Abandon de Nemotron comme moteur principal accepté ?
7. Durées de conservation (audio, transcriptions), grille de classification des réunions, plafond de coût LLM ?

## Sous-agents utilisés

| Note | Tâche | Modèle |
|---|---|---|
| [01-existant](notes/01-existant.md) | Recensement des applis et projets existants | Sonnet |
| [02-asr](notes/02-asr.md) | Nemotron ASR et alternatives locales | Opus |
| [03-llm-connexion](notes/03-llm-connexion.md) | Clés API, abonnements, conditions d'utilisation | Opus |
| [04-architecture](notes/04-architecture.md) | Stack, stockage, historique, modèle de données | Sonnet |
| [05-confidentialite](notes/05-confidentialite.md) | Flux de données, chiffrement, RGPD | Sonnet |
| [06-faisabilite](notes/06-faisabilite.md) | Arbitrages, effort, risques, plan de MVP | Opus |
