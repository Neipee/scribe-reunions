# 03 — Connexion aux LLM (OpenAI / Anthropic)

Étude documentaire, sans code. Rédigée le 2026-10-27. Toutes les sources ont été consultées le **2026-10-27** sauf mention contraire.
Légende : **[officiel]** = source Anthropic/OpenAI ; **[presse/tiers]** = source secondaire ; **non vérifié** = non confirmé sur une source officielle lisible.

Contrainte du projet rappelée : la transcription est faite sur l'appareil ; le texte ne doit partir **que** vers OpenAI ou Anthropic. Aucun backend propre.

---

## 1. Mode « clé API » (BYOK, bring your own key)

### 1.1 Appel direct depuis l'appli, sans backend

- **OpenAI** : appel HTTPS direct à `https://api.openai.com/v1/responses` (ou Chat Completions) avec l'en-tête `Authorization: Bearer <clé>`. Pour la résidence UE, domaine `eu.api.openai.com` (voir 1.4). [officiel] [OpenAI — Your data / data controls](https://developers.openai.com/api/docs/guides/your-data) (vu le 2026-10-27).
- **Anthropic** : appel HTTPS direct à `https://api.anthropic.com/v1/messages` avec `x-api-key` et `anthropic-version`. Une appli native (Kotlin/Swift) n'est pas concernée par CORS. Une appli web, ou une WebView qui fait des `fetch()`, doit envoyer l'en-tête `anthropic-dangerous-direct-browser-access: true`. Le mot « dangerous » met en garde contre les clés intégrées au client, et le cas BYOK y est explicitement présenté comme légitime. [presse/tiers] [Simon Willison, 2024-08-23](https://simonwillison.net/2024/Aug/23/anthropic-dangerous-direct-browser-access/) (vu le 2026-10-27). Documentation officielle de cet en-tête : **non vérifiée**.
- Ni le texte des Commercial Terms d'Anthropic ni celui d'OpenAI ne demande de backend. Le risque porte sur la clé, pas sur le contrat (voir 1.3).

### 1.2 Stockage sécurisé de la clé sur l'appareil

- **Android** : toutes les API de Jetpack Security Crypto (`EncryptedSharedPreferences`, `MasterKey`) sont **dépréciées depuis la 1.1.0**, et aucune nouvelle version n'est prévue. La documentation Android Cryptography le dit, mais je l'ai lu via des sources secondaires et non vérifié directement sur developer.android.com. Remplacement recommandé : **Jetpack DataStore** pour la persistance, **Tink (AEAD)** pour le chiffrement, avec une clé maîtresse dans **Android Keystore** (non exportable, adossée au matériel si possible). L'artefact `androidx.datastore:datastore-tink` existerait depuis DataStore 1.3.0-rc01 (**non vérifié**, notes de version officielles à consulter). [presse/tiers] [Include Security, 2026-08](https://blog.includesecurity.com/2026/08/encryptedsharedpreferences-is-dead-heres-what-you-should-use-instead/), [ProAndroidDev — migration 2026](https://proandroiddev.com/goodbye-encryptedsharedpreferences-a-2026-migration-guide-4b819b4a537a) (vus le 2026-10-27).
- **iOS** : Keychain (`kSecClassGenericPassword`, accessibilité `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` pour exclure la clé des sauvegardes et des transferts entre appareils). Pratique courante, mais pas re-sourcée ici (**non vérifié** dans le cadre de cette étude).
- **Multiplateforme** : `flutter_secure_storage` (Keychain / Keystore) ou `react-native-keychain`. Vérifier que la version retenue n'utilise plus `EncryptedSharedPreferences` par défaut sur Android (**non vérifié**).
- Bonnes pratiques complémentaires :
  - ne jamais journaliser la clé ni la copier dans les rapports de plantage ;
  - l'exclure de la sauvegarde Android (`android:allowBackup` / règles `dataExtractionRules`) ;
  - masquer le champ de saisie et offrir un bouton « supprimer la clé » ;
  - vérifier la clé par un appel minimal ;
  - épingler les domaines (`api.openai.com`, `eu.api.openai.com`, `api.anthropic.com`) dans une `network_security_config` qui n'autorise que le TLS.

### 1.3 Risques d'une clé fournie par l'utilisateur sur l'appareil

- **Fuite de la clé** : appareil rooté ou jailbreaké, malware, sauvegarde mal exclue, captures d'écran pendant la saisie. Conséquence : facturation à la charge de l'utilisateur et usage abusif sous son compte.
- **Recommandation officielle OpenAI** : une clé par personne (partager une clé contrevient aux conditions d'utilisation), clés avec **date d'expiration** et rotation régulière. [officiel] [OpenAI Help — Best practices for API key safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety) (vu le 2026-10-27, extrait lu via le moteur de recherche, la page renvoyant une erreur 403). La consigne « ne pas mettre la clé côté client (navigateur, mobile) » vise le cas où **l'éditeur** intègre **sa** clé dans l'appli. Pour une clé saisie par l'utilisateur lui-même, la règle ne s'applique pas telle quelle (interprétation, **non vérifié** sur le texte officiel).
- Conseils à afficher à l'utilisateur :
  - créer une clé dédiée à l'appli, dans un projet dédié ;
  - fixer une limite de dépenses ;
  - restreindre les permissions de la clé si la console le permet ;
  - fixer une expiration.
- **Responsabilité** : chez Anthropic, « Customer is responsible for all activity under its account » (Commercial Terms, D.5). Le client, c'est l'utilisateur titulaire de la clé.

### 1.4 Les conditions des éditeurs autorisent-elles une appli BYOK ?

- **Anthropic** :
  - Les Commercial Terms permettent d'utiliser les services « to power products and services Customer makes available to its own customers and end users » (A.1). Aucune clause n'interdit qu'un utilisateur final fournisse sa propre clé. Seule limite proche : ne pas construire de produit concurrent (D.4(a)). [officiel] [Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms) (vu le 2026-10-27, effectifs au 2025-06-17).
  - La page Legal and compliance de Claude Code demande aux développeurs d'utiliser « API key authentication through Claude Console ». Elle précise aussi que chaque utilisateur final peut s'authentifier avec **sa propre clé API**, facturée directement sur son compte. [officiel] [Claude Code — Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance) (vu le 2026-10-27).
  - Côté consommateur : interdiction de partager sa clé API avec quelqu'un d'autre (Consumer Terms §2). L'utilisateur qui saisit sa clé dans une appli qu'il utilise lui-même ne la « partage » pas avec un tiers, puisque l'éditeur n'y a pas accès sans backend (interprétation, **non vérifié** auprès d'Anthropic).
- **OpenAI** : l'interdiction de partager une clé existe, et rien dans les extraits consultés n'interdit une appli BYOK. Mais le texte du Services Agreement et des Terms of Use n'a pas pu être lu (erreur 403 sur openai.com/policies). **Non vérifié** sur le texte contractuel. Les fils de la communauté OpenAI ([Bring Your Own Key policy](https://community.openai.com/t/bring-your-own-key-policy/446168), vu le 2026-10-27) ne valent pas position officielle.
- **Conclusion** : BYOK **autorisé** chez Anthropic (texte officiel explicite pour Claude Code, et rien de contraire dans les Commercial Terms). **Très probablement autorisé** chez OpenAI, mais **non vérifié** sur le texte contractuel.

### 1.5 Conservation des données, entraînement, résidence UE, DPA

| | OpenAI API | Anthropic API |
|---|---|---|
| Entraînement par défaut | **Non** : « data sent to the OpenAI API is not used to train or improve OpenAI models » sauf opt-in explicite | **Non** : « Anthropic may not train models on Customer Content from Services » (Commercial Terms B). Exceptions : programme Development Partner Program (opt-in d'organisation) et feedback explicite (pouce haut/bas) |
| Conservation par défaut | Journaux d'abus jusqu'à **30 jours**. Responses API : état applicatif conservé 30 jours si `store=true` → **mettre `store:false`** | Suppression des entrées/sorties **sous 30 jours**. Jusqu'à **2 ans** si le contenu est signalé pour violation de l'Usage Policy |
| Zero Data Retention | Sur **approbation** d'OpenAI (ZDR ou Modified Abuse Monitoring). Responses et Chat Completions sont éligibles | Par **accord** (ZDR agreement), selon les organisations |
| Résidence UE | **Oui** : projet région Europe, `eu.api.openai.com`, stockage et traitement en UE. Exige l'approbation des contrôles d'abus (ZDR/MAM…) et un avenant Modified Retention ; surcoût de 10 % sur les modèles récents | **Non en 1P** : `inference_geo` = `us` ou `global` seulement, workspace geo = `us` seulement (au 2026-10-14 selon une source tierce). L'UE n'est possible que via Bedrock ou Vertex (hors périmètre « OpenAI ou Anthropic uniquement ») |
| DPA | Oui pour l'API et ChatGPT Business/Enterprise ; formulaire DPA ; **pas pour un compte personnel** | DPA intégré par renvoi aux Commercial Terms (section C) |

Sources :
- [officiel] [OpenAI — Your data](https://developers.openai.com/api/docs/guides/your-data) ;
- [officiel] [OpenAI — Enterprise privacy](https://openai.com/enterprise-privacy/) (lu via le moteur de recherche, erreur 403) ;
- [officiel] [Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms) ;
- [officiel] [Anthropic DPA](https://www.anthropic.com/legal/data-processing-addendum) (page non lue en détail, **non vérifié**) ;
- [officiel] [privacy.claude.com — durée de conservation (organisations)](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data) ;
- [officiel] [privacy.claude.com — entraînement](https://privacy.claude.com/en/articles/7996885-how-do-you-use-personal-data-in-model-training) ;
- [officiel] [Development Partner Program](https://support.claude.com/en/articles/11174108-about-the-development-partner-program) ;
- [officiel] [Claude Platform — Data residency](https://platform.claude.com/docs/en/manage-claude/data-residency) (lu via le moteur de recherche) ;
- [presse/tiers] [theaiconsultancy.ai — Claude data residency UK 2026](https://theaiconsultancy.ai/blog/claude-data-residency-uk-2026) ;
- [presse/tiers] [iubenda — OpenAI GDPR 2026](https://www.iubenda.com/en/blog/openai-gdpr-compliance/).

Toutes vues le 2026-10-27.

Points d'attention pour l'appli :
- Côté OpenAI, envoyer `store: false` sur Responses.
- Ne pas utiliser les endpoints à état (conversations, files, vector stores), qui ne sont pas éligibles au ZDR.
- Le ZDR, la résidence UE et le DPA sont des démarches de **l'utilisateur titulaire de la clé** (organisation), pas de l'éditeur de l'appli. Pour un particulier, la conservation par défaut de 30 jours s'applique.

---

## 2. Mode « abonnement » (Claude Pro/Max/Team/Enterprise, ChatGPT Plus/Pro/Team/Enterprise)

### 2.1 Anthropic : connexion Claude.ai dans une appli tierce → NON AUTORISÉ

- **Texte officiel** [Claude Code — Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance) (vu le 2026-10-27), section « Authentication and credential use » :
  - L'OAuth est réservé aux abonnés Free/Pro/Max/Team/Enterprise et « designed to support ordinary use of Claude Code and other native Anthropic applications ».
  - « Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, or Max plan credentials on behalf of their users. »
  - « developers may not collect, store, or intermediate Claude.ai credentials or session tokens — sign-in to a Claude account must complete through Anthropic's own flow. »
  - « Anthropic reserves the right to take measures to enforce these restrictions and may do so without prior notice. »
- **Agent SDK** : « Unless previously approved, we do not allow third party developers to apply Claude.ai rate limits for their products, including agents built on the Claude Agent SDK. » [officiel] [Agent SDK overview](https://docs.claude.com/en/docs/agent-sdk/overview) (lu via le moteur de recherche le 2026-10-27).
- **Consumer Terms §3(7)** : interdiction d'accéder aux services « through automated or non-human means, whether through a bot, script, or otherwise », sauf via une clé API ou avec une autorisation explicite. **Consumer Terms §2** : pas de partage des identifiants de compte ni de la clé API. [officiel] [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms) (effectifs au 2025-10-08, vus le 2026-10-27).
- **Application effective** [presse/tiers] :
  - **2026-01-09** : blocages côté serveur des clients tiers (OpenCode, etc.) et bannissements automatiques, dont certains ont ensuite été annulés.
  - **2026-02-19** : clarification de la documentation.
  - **2026-04-04** : les abonnements cessent de couvrir les outils tiers.
  - Sources : [The Register, 2026-02-20](https://www.theregister.com/software/2026/02/20/anthropic-clarifies-ban-on-third-party-tool-access-to-claude/5014546), [WinBuzzer, 2026-02-19](https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/), [apiyi.com](https://help.apiyi.com/en/anthropic-claude-subscription-third-party-tools-openclaw-policy-en.html) (vus le 2026-10-27). Dates exactes **non vérifiées** sur une source Anthropic.
- **Team / Enterprise** : ces plans relèvent des Commercial Terms, mais l'interdiction faite aux développeurs tiers de proposer la connexion Claude.ai est générale. Je n'ai trouvé aucune voie officielle pour qu'une appli tierce consomme un forfait Team/Enterprise. Une exception est possible par accord direct (« contact sales »), mais **non vérifié** et hors MVP.

### 2.2 OpenAI : « Sign in with ChatGPT » (SIWC) → partiellement autorisé, sur programme

- **Ce qui existe officiellement** [officiel] [developers.openai.com/siwc](https://developers.openai.com/siwc), [Quickstart](https://developers.openai.com/siwc/quickstart), [Cookbook — Sign in with ChatGPT in your open-source app](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt), [learn.chatgpt.com — Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt) (tous vus le 2026-10-27) :
  - Deux capacités distinctes :
    - **Identity** : OIDC + PKCE, scopes `openid profile email`.
    - **ChatGPT plan usage** : scope `chatgpt.tokens.use.direct`, requêtes vers la **Responses API publique** (`https://api.openai.com/v1`) avec le jeton OAuth de l'utilisateur, sans clé API ni secret client.
  - Aucune des deux ne donne accès aux conversations ChatGPT.
  - **Éligibilité** :
    - Identity : « selected commercial partners through a limited trial ».
    - Plan usage : « all open-source partners and selected private clients ».
    - Le Cookbook précise : « open-source projects, personal projects that run locally, and selected private apps ». Une appli **payante ou hébergée à distance** doit d'abord passer par la liste d'attente.
  - **Plans utilisateurs** : « eligible ChatGPT **Plus and Pro** subscribers ». Business/Team/Enterprise/Edu ne sont pas cités pour l'usage du forfait. Ils l'étaient explicitement exclus en 2025 ([MediaNama, 2025-06](https://www.medianama.com/2025/06/223-openai-sign-in-with-chatgpt-third-party-apps/)). Statut actuel **non vérifié**.
  - L'utilisateur fixe un plafond hebdomadaire par appli dans ChatGPT (Settings > Usage). L'usage est décompté du forfait ChatGPT.
  - Les apps doivent utiliser le libellé « Continue with ChatGPT » et la charte graphique OpenAI.
  - **Mobile** : aucune mention dans les pages consultées. Les exemples cités sont des outils locaux (CLI, desktop) : OpenClaw, OpenCode, Pi, T3. **Non vérifié** pour une appli Android/iOS.
- **Lancement** : beta en juillet 2026, élargissement à DevDay 2026 [presse/tiers] [The New Stack](https://thenewstack.io/sign-in-with-chatgpt/), [The Star, 2026-10-04](https://www.thestar.com.my/tech/tech-news/2026/10/04/openai-expands-chatgpt-with-apps-and-third-party-sign-in) (vus le 2026-10-27). Les pages d'aide [help.openai.com 20001410](https://help.openai.com/en/articles/20001410-sign-in-with-chatgpt) et [20001542](https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites) ont renvoyé une erreur 403 et n'ont été lues que via les extraits du moteur de recherche.
- **Conservation et entraînement des requêtes faites via le forfait** : est-ce le régime API (pas d'entraînement, 30 jours) ou le régime ChatGPT grand public (entraînement possible si l'utilisateur ne l'a pas désactivé) ? **Pas trouvé, NON CLAIR.** C'est un point bloquant pour une appli de comptes rendus de réunion confidentiels.
- **Codex CLI** : il utilise la connexion ChatGPT, mais c'est un produit OpenAI. Son existence n'autorise pas à réutiliser ses jetons dans une autre appli : seul le programme SIWC est la voie officielle.
- **Hors SIWC** : réutiliser une session ChatGPT ou passer par une API non officielle est **NON AUTORISÉ**. Les Terms of Use interdisent l'extraction automatisée ou programmatique, d'après les extraits vus ; le texte n'a pas été lu à cause de l'erreur 403, donc **non vérifié mot pour mot**.

### 2.3 Alternative inverse : l'appli expose ses données à ChatGPT/Claude (MCP, connecteurs, apps)

- **Claude** : les connecteurs personnalisés (remote MCP) sont disponibles sur Free/Pro/Max/Team/Enterprise et utilisables dans les applis mobiles (ajout depuis le mobile en beta). Mais Claude se connecte au serveur MCP **depuis l'infrastructure cloud d'Anthropic** : le serveur doit être **joignable sur Internet public**. [officiel] [Get started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [Use connectors](https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities) (vus le 2026-10-27).
- **ChatGPT** : les Apps SDK et le mode développeur reposent eux aussi sur un serveur MCP en HTTPS public, ou sur le « Secure MCP Tunnel ». Les plans concernés varient selon les sources (**non vérifié**). [officiel] [openai-apps-sdk-examples](https://github.com/openai/openai-apps-sdk-examples) ; [presse/tiers] [usecarly.com](https://www.usecarly.com/blog/chatgpt-mcp/) (vus le 2026-10-27).
- **Conséquence** : la démarche est AUTORISÉE en principe, mais il faut un serveur exposé, c'est-à-dire un backend ou un tunnel. Les transcriptions transiteraient alors par ce serveur, ce qui **contredit la contrainte « données nulle part ailleurs »**. Un téléphone qui servirait de serveur MCP public n'est pas réaliste (NAT, sécurité). **À exclure du MVP.**

### 2.4 Partage vers l'appli officielle (share sheet) → AUTORISÉ

- L'utilisateur partage le texte (intent Android `ACTION_SEND` en `text/plain`, ou feuille de partage iOS) vers l'appli ChatGPT ou Claude. Il colle ou valide lui-même, avec un prompt de synthèse préformaté et copié dans le presse-papiers.
- Aucun jeton n'est manipulé et il n'y a aucun accès automatisé : c'est un usage ordinaire de l'appli officielle par l'abonné. Cela respecte les Consumer Terms §3(7) d'Anthropic, puisque l'action est humaine, et la doctrine « native Anthropic applications ».
- **Non vérifié** : que les applis Android ChatGPT et Claude acceptent bien `ACTION_SEND text/plain`, et la longueur maximale d'un texte partagé. À tester sur appareil. Prévoir aussi le partage en fichier `.txt` ou `.md` en pièce jointe pour les longues transcriptions.
- **Confidentialité** : les données suivent alors le régime **grand public** du compte de l'utilisateur. Chez Anthropic, il y a entraînement sur Free/Pro/Max si le réglage est activé ([privacy.claude.com](https://privacy.claude.com/en/articles/7996885-how-do-you-use-personal-data-in-model-training)). Pour ChatGPT, cela dépend du réglage « Améliorer le modèle » (**non vérifié** ici). Il faut l'afficher clairement.

---

## 3. Synthèse : autorisé / non autorisé / non clair

| Mode | Statut | Fondement |
|---|---|---|
| Clé API Anthropic saisie par l'utilisateur, appel direct | **AUTORISÉ** | Commercial Terms A.1 ; Legal & compliance (« own Anthropic API key ») |
| Clé API OpenAI saisie par l'utilisateur, appel direct | **AUTORISÉ (probable)**, texte contractuel **non vérifié** (403) | Pas d'interdiction trouvée ; une clé par personne |
| Connexion Claude.ai (Pro/Max/Team/Ent.) dans l'appli | **NON AUTORISÉ** | Legal & compliance : interdit d'offrir la connexion Claude.ai, de router les requêtes, de stocker les jetons ; Consumer Terms §3(7) ; application effective depuis 2026-01 |
| Réutilisation de jetons Claude Code / Codex / session web | **NON AUTORISÉ** | Mêmes textes ; Terms OpenAI (accès programmatique) |
| « Sign in with ChatGPT » avec usage du forfait (Plus/Pro) | **NON CLAIR / sous condition** : programme sur liste d'attente pour les applis commerciales ou payantes ; mobile non documenté ; plans Team/Enterprise non couverts ; régime de conservation et d'entraînement non trouvé | developers.openai.com/siwc, Cookbook |
| Connecteur MCP / app ChatGPT (sens inverse) | Autorisé, mais **incompatible** avec « pas de backend / données nulle part ailleurs » | support.claude.com, Apps SDK |
| Partage manuel vers l'appli ChatGPT/Claude officielle | **AUTORISÉ** | Usage humain ordinaire de l'appli officielle |

---

## 4. Recommandation pour le MVP

**À livrer :**
1. **« Ma clé API »** (OpenAI et Anthropic), mode principal.
   - Stockage : Keystore + Tink/DataStore sur Android, Keychain sur iOS.
   - Appels directs, `store:false` côté OpenAI, aucun endpoint à état.
   - Bouton « Tester la clé ».
   - Conseils affichés : clé dédiée, plafond de dépenses, expiration.
   - Mention : « vos transcriptions ne sont envoyées qu'à [fournisseur] ; pas d'entraînement par défaut ; conservation jusqu'à 30 jours pour la lutte contre les abus, sauf accord ZDR de votre organisation ».
   - Option « région Europe » pour OpenAI, réservée aux utilisateurs dont le projet est configuré pour l'UE. Côté Anthropic, indiquer honnêtement l'absence d'option UE en accès direct.
2. **« Utiliser mon abonnement Claude ou ChatGPT »**, mis en œuvre par **partage vers l'appli officielle** : prompt prêt à l'emploi et transcription en texte ou fichier, puis l'utilisateur colle le résumé obtenu dans l'appli s'il le souhaite. Formulation honnête : « Anthropic et OpenAI ne permettent pas aux applis tierces de se connecter à votre abonnement ; nous ouvrons l'appli officielle avec votre transcription. »

**À ne pas livrer en MVP :**
- Aucune connexion Claude.ai, ni maintenant ni plus tard sans accord écrit d'Anthropic.
- Aucun connecteur MCP ou app ChatGPT, car ils exigent un serveur.

**À étudier après le MVP :**
- **Sign in with ChatGPT** (usage du forfait) : déposer une demande sur la liste d'attente. Il faut d'abord obtenir d'OpenAI la confirmation écrite :
  - du support mobile ;
  - de l'éligibilité d'une appli commerciale fermée ;
  - du régime de conservation et d'entraînement des requêtes ;
  - de la couverture Business/Enterprise.
- **Écran de choix** : trois cartes. « Clé API (recommandé, le plus confidentiel) », « Mon abonnement via l'appli ChatGPT/Claude (manuel) », et éventuellement plus tard « Continuer avec ChatGPT ». Chaque carte porte une ligne « Où vont vos données » et une ligne « Qui paie ».
