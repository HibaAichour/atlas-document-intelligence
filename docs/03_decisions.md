# Journal des décisions techniques — ATLAS V1

Format : une entrée par décision, la plus récente en haut.

## Modèle d'entrée
### [AAAA-MM-JJ] Titre de la décision
- **Contexte** : pourquoi la question se pose
- **Décision** : ce qui est choisi
- **Alternatives écartées** : et pourquoi
- **Conséquences** : impact sur le projet, lien avec la V2

---
## [2026-10-31] Démo en ligne sur SnapDeploy, Render demandant une carte bancaire
- **Contexte** : à la création du service, Render a demandé une carte bancaire (vérification par une autorisation temporaire de 1 USD), ce que l'utilisatrice refuse. Critères fixés avant de chercher : aucune carte, `Dockerfile` inchangé, au moins 512 Mo, accès sortant à Groq et Gemini, veille acceptable.
- **Décision** : offre gratuite de SnapDeploy : 512 Mo, 0,25 vCPU, 100 heures de conteneur par mois (le temps de veille ne compte pas), veille après environ 15 minutes sans visite, réveil par une visite dans un navigateur, 10 déploiements par jour (5 par tranche de 12 heures), 100 requêtes par minute par adresse IP, images ARM64, pas de disque persistant. Conteneur `atlas-demo-0dffb`, taille Small, port 8000 détecté par la ligne `EXPOSE`, image publique `ghcr.io/hibaaichour/atlas-document-intelligence:latest`, deux secrets (`LLM_API_KEY`, `EMBEDDING_API_KEY`). Adresse : `https://atlas-demo-0dffb.containers.snapdeploy.app`.
- **Alternatives écartées** : Render avec une carte (refusé par l'utilisatrice) ; Hugging Face Spaces (Docker réservé à l'abonnement PRO depuis juillet 2026) ; Koyeb (carte, empreinte de 29 $) ; Google Cloud Run et Fly.io (carte) ; Back4App (256 Mo, moins que nos mesures) ; PythonAnywhere (pas d'ASGI, accès sortant filtré) ; Railway (crédit de 1 $ par mois) ; Azure for Students (sans carte, mais mise en place plus complexe et limitée à 12 mois ; gardé en solution de secours).
- **Conséquences** : démarrage : 4 documents indexés, 27 vecteurs, en 2 s ; Uvicorn sur le port 8000. Scénarios en anglais : préavis juste (60 days, p. 4) en 2,8 s (Retrieval 237 ms, Writer 842 ms, Critic 1,1 s) ; salaire du CEO refusé par le seuil en 0,5 s ; facture 7 champs sur 7 en 1,5 s ; exports Word et PowerPoint corrects. En français : 60 jours, p. 4, en 2,1 s ; export Word en français. Mémoire : 33 % selon SnapDeploy (environ 170 Mo, mesure non comparable à `docker stats`). Réveil : conteneur endormi entre 12 et 22 minutes sans visite ; en ouvrant l'adresse, interface affichée en 1 min 02 s, puis première question juste en 2,3 s ; sessions reparties de zéro, comme prévu. À dire dans le README : 100 heures par mois ; réveil d'environ une minute, uniquement par un navigateur ; sessions partagées entre visiteurs ; redéploiement à lancer à la main après une nouvelle image ; dépendance à un petit hébergeur, le `Dockerfile` restant portable. À faire : activer la double authentification du compte SnapDeploy ; mettre à jour la plateforme dans `02_architecture.md` (§ 3.3 et § 13) à l'étape 13.

## [2026-10-31] Image de la démo publiée par GitHub Actions, sans accès de l'hébergeur au compte GitHub
- **Contexte** : la connexion GitHub de SnapDeploy passe par une autorisation OAuth avec la permission `repo`, qui donne accès en lecture et en écriture à tous les dépôts du compte, sans pouvoir la limiter à un seul. L'accès a été retiré des deux côtés (*Disconnect* dans SnapDeploy, *Revoke* dans GitHub).
- **Décision** : `.github/workflows/publish-image.yml`, lancé à chaque push sur `main` (sauf si seuls `docs/`, `eval/` ou des fichiers `*.md` changent) et à la main (`workflow_dispatch`) ; machine ARM64 native (`ubuntu-24.04-arm`, gratuite pour un dépôt public) ; jeton automatique `GITHUB_TOKEN` limité à `contents: read` et `packages: write` ; étiquettes `latest` et `sha-<commit>` ; cache de construction de GitHub ; un nouveau push annule le build en cours. Paquet rendu public (il ne contient aucune clé). Vérifié avec `actionlint` 1.7.7 ; image ARM64 lisible sans identifiant (`docker manifest inspect`).
- **Alternatives écartées** : la connexion GitHub de SnapDeploy (accès à tous les dépôts) ; l'application GitHub de SnapDeploy (non vérifiable à l'avance) ; une machine Intel avec simulation ARM (QEMU, beaucoup plus lente) ; un jeton personnel (un secret de plus) ; les tests (pytest, vitest) dans le même workflow (V2).
- **Conséquences** : premier build en 1 min 56 s, contre 12 min 27 s sur le Mac en 12.2. Après une nouvelle image, le redéploiement se lance à la main dans SnapDeploy. Actions épinglées sur leur version majeure (`@v4`...), pas sur une empreinte. Sur le CV : « image Docker construite et publiée par GitHub Actions (GHCR, ARM64) ».

## [2026-10-30] Recherche de la démo en ligne calibrée pour Gemini : seuil 0,56, écart désactivé
- **Contexte** : le seuil (0,44) et l'écart au meilleur score (0,05) avaient été mesurés avec `bge-m3` en local ; Gemini donne des scores sur une autre échelle (avec lui, le salaire du CEO dépassait 0,44). L'entrée du 2026-10-28 demandait de mesurer l'écart entre questions hors sujet et bons passages, avec un repli sur OVH `BGE-M3` sans écart net. Critères fixés avant la mesure : seuil = plus bas bon passage moins 0,01, arrondi vers le bas ; écart = le plus petit de 0,03, 0,05 et 0,08 qui ne perd aucun bon passage, sinon désactivé ; acceptation : scénario 1 juste en anglais et en français, salaire refusé dans les deux langues, au moins 16 réponses justes sur 21, 15 champs sur 15.
- **Décision** : `RETRIEVAL_MIN_SCORE=0.56` et `RETRIEVAL_MAX_GAP=1`, dans le bloc de configuration en ligne du `Dockerfile` seulement (configuration locale inchangée). Mesures avec le conteneur (512 Mo, 0,1 processeur) : `probe_scores` sur les 5 jeux (53 questions, top 5) donne un plus bas bon passage de 0,572 (alerte des certificats) et un plus haut hors sujet de 0,774 (chiffre d'affaires d'Orion), soit un chevauchement de 0,20, contre un écart de +0,038 avec `bge-m3` ; bon passage premier 33 fois sur 38. `probe_margin` (`RETRIEVAL_MIN_SCORE=0.56`) : chaque écart essayé perd un bon passage, celui du taux d'intérêt (facture 0,762, contrat p. 3 0,670) ; sans écart, 4,9 passages en moyenne. Option `--pause` de `run_eval` (0 par défaut), 20 s en ligne : environ 2,5 questions par minute, sous la limite de 8 000 jetons de Groq ; résultats dans `eval/results_online.json`.
- **Alternatives écartées** : le repli sur OVH `BGE-M3` (2 requêtes par minute, partagées par l'adresse IP de sortie de Render : démo inutilisable) ; un écart de 0,08 (perd le passage du contrat sur le taux d'intérêt, même si la facture donne aussi ce taux) ; retoucher le prompt du Writer pour les 2 réponses en français à une question anglaise (réglage sur deux questions).
- **Conséquences** : évaluation en ligne en 542 s, sans 429 : 18 questions justes sur 21 (anglais 8 sur 10, français 10 sur 11), 18 sur 21 justes et bien citées, 14 réponses justes sur 14 avec la bonne page, 15 champs sur 15 ; Critic : 1 réponse fausse signalée sur 3, 1 fausse alerte sur 14 ; scénario 1 juste dans les deux langues ; salaire du CEO refusé par le seuil en anglais (1,1 s, sans appel à Groq) et par le Writer en français. Les 4 critères d'acceptation sont remplis. Échecs : `outage-en` (juste sur le fond, mais répondu en français, le texte attendu étant l'anglais « storage ») ; `revenue-en` et `revenue-fr` (45 370 USD, ce qu'Orion a payé et non son chiffre d'affaires, le piège connu). `gpt-oss-20b` répond parfois dans la langue des passages : 12 réponses sur 14 dans la langue de la question, contre 14 sur 15 en local. Seules 4 des 13 questions hors sujet différentes sont refusées par le seuil, avec une marge faible pour le salaire du CEO en anglais (0,545 pour 0,56) ; la recherche interlangue a manqué un bon passage (« Quand le contrat commence-t-il ? »). Le bloc `local_settings` de `results_online.json` donne les réglages locaux, pas ceux du conteneur. À dire dans le README : score en ligne non comparable au score local (autres modèles), et ces limites. 574 tests backend.

## [2026-10-30] Limite d'un fournisseur en ligne : 429, et messages sans Ollama en ligne
- **Contexte** : les providers ne mettaient le code HTTP que dans le texte de `LLMError` et `EmbeddingError` ; toute panne devenait donc un 503, et l'interface affichait pour tout 503 « … Ollama est-il lancé ? », faux en ligne. Les offres gratuites de Groq (8 000 jetons par minute) et de Gemini peuvent répondre 429.
- **Décision** : backend : `LLMError` et `EmbeddingError` reçoivent `rate_limited` (faux par défaut), mis à vrai par les providers compatibles OpenAI sur un 429 (`is_too_many_requests`, `app/core/http_errors.py` ; les embeddings Ollama passent par le même code, sans effet, Ollama ne limitant jamais). `app/api/errors.py` : `service_error` suit la chaîne des causes (`__cause__`, une `RetrievalError` enveloppant l'`EmbeddingError`) et répond 429 avec un message fixe, sans le texte du fournisseur (celui de Groq contient l'identifiant de l'organisation), sinon 503 avec le message d'avant. Utilisé par `/ask`, `/search` et les routes de session ; `answer_or_503` et `extract_or_503` deviennent `answer_or_error` et `extract_or_error`. Sur un 429, rien n'est enregistré, comme sur un 503. Frontend : textes `errorRateLimited` (« Limite gratuite atteinte, réessayez dans une minute. ») et `errorServiceDownOnline` (sans Ollama) ; `apiErrorText(…, provider = 'ollama')` ; `llmProviderOf` (`lib/config.ts`) donne `'ollama'` tant que la configuration n'est pas lue ; `App` transmet le fournisseur à `useChat` seulement.
- **Alternatives écartées** : lire et renvoyer `Retry-After` (délai non affiché, Gemini ne l'envoie pas toujours ; ajout possible en V2 sans casser l'API) ; un nouvel essai automatique après un 429 (V2) ; transmettre le fournisseur à `useDocuments` (un téléversement ne renvoie jamais 503 : une panne d'embedding donne un document `failed`, et le téléversement est refusé en ligne) ; un message distinct pour la limite par jour.
- **Conséquences** : 572 tests backend, 149 frontend. Vérifié dans le conteneur (512 Mo, 0,1 processeur) : avec une fausse clé Groq, 503 et le message en ligne en anglais et en français, sans « Ollama » ; avec les vraies clés, scénario 1 juste (60 days, p. 4, Critic sans problème) en 3,1 s. Le 429 n'a pas été provoqué en vrai (il aurait entamé le quota du jour) : couvert par les tests. Une limite par jour affiche aussi « réessayez dans une minute » (README). Le message d'attente « Le modèle local peut demander jusqu'à une minute » s'affiche aussi en ligne : à revoir à l'étape 13.

## [2026-10-29] Interface : téléversement masqué en mode démo
- **Contexte** : en ligne, le backend refuse les téléversements (403) ; le bouton « Upload a file » ne doit donc pas apparaître.
- **Décision** : type `AppConfig` et `getConfig()` (`api/`) ; hook `useConfig`, qui lit `/api/config` une fois au chargement. La règle `uploadsAllowed` (`lib/config.ts`) masque le bouton pendant le chargement (sinon il apparaîtrait puis disparaîtrait en ligne), l'affiche en local et aussi si la lecture échoue (le mode local doit rester utilisable ; le backend de démo refuse de toute façon). En démo, une note remplace le bouton et le sélecteur de fichier (« Online demo: sample documents only. Uploads are disabled. », traduite). Un 403 sur un téléversement donne un message traduit (filet de sécurité). Tests React Testing Library de `DocumentsPanel` ; la note française est comparée à son texte exact, les requêtes de Testing Library remplaçant l'espace insécable par une espace normale.
- **Alternatives écartées** : masquer selon l'adresse de la page (fragile, et faux pour le conteneur testé sur `localhost:8000`).
- **Conséquences** : 145 tests frontend. Vérifié dans le conteneur, en anglais et en français. `useConfig` servira en 12.3 au message d'erreur selon le fournisseur (`llm_provider`).

## [2026-10-29] Index d'embedding absent lu comme 0 (Gemini)
- **Contexte** : au premier démarrage du conteneur, les 4 documents ont échoué à l'indexation (« items with and without an index »). Mesure avec `curl` sur trois textes : Gemini omet `index` pour le premier élément, puis donne `1` et `2` (son format n'écrit pas les valeurs par défaut, donc un index égal à 0 disparaît). Le test de l'entrée du 2026-10-28 n'envoyait qu'un seul texte et ne pouvait pas le montrer.
- **Décision** : dans `_in_input_order`, si aucun élément n'a d'`index`, l'ordre reçu est gardé ; sinon, un `index` absent vaut 0, et les index doivent être exactement 0 à n−1, chacun une fois, sinon `EmbeddingError` (doublon, trou, hors limites, valeur qui n'est pas un entier). Les éléments sont placés à leur position, sans tri, ce qui permet à mypy de vérifier les types. Remplace la règle « mélange = erreur » de l'entrée du 2026-10-28.
- **Alternatives écartées** : ignorer toujours `index` (plus simple, mais un fournisseur qui renverrait les vecteurs dans le désordre donnerait à chaque passage le vecteur d'un autre, sans aucune erreur).
- **Conséquences** : 555 tests backend. L'indexation du conteneur réussit : 4 documents, 27 vecteurs.

## [2026-10-29] Image de production : conteneur unique, images épinglées
- **Contexte** : la démo en ligne tourne dans un seul conteneur, sans Ollama, sur une offre de 512 Mo et 0,1 processeur.
- **Décision** : `Dockerfile` et `.dockerignore` à la racine. Node compile le frontend ; Python reçoit le backend, les scripts, les documents de démo et le frontend compilé (`/app/static`), puis lance `seed_demo` sous l'utilisateur `atlas`. Images épinglées sur les versions mesurées le 2026-10-29, `python:3.13.18-slim-trixie` et `node:24.22.2-alpine3.24`, sans empreinte `sha256` (une mise à jour se fait volontairement, en changeant une ligne). Configuration en ligne dans l'image, sans les clés ; `LLM_API_KEY` et `EMBEDDING_API_KEY` sont données au lancement. Démarrage : `python -m scripts.reindex; exec uvicorn … --port ${PORT:-8000}`. Tesseract reste dans l'image (OCR pendant le build). `docker-compose.yml` inchangé.
- **Alternatives écartées** : Nginx dans le conteneur (deux programmes à surveiller) ; une troisième étape pour retirer Tesseract (environ 35 Mo pour un Dockerfile plus complexe) ; des empreintes `sha256` (plus de correctifs automatiques, sans gain pour une démo).
- **Conséquences** : image de 1,07 Go. Premier build en 12 min 27 s (Tesseract 327 s, `pip` 405 s, avec une connexion d'environ 8 Ko/s vers Debian) ; reconstruction en 9,7 s quand seul le backend change, 37 s quand le frontend change. Une première tentative a été arrêtée après 20 minutes (« cannot allocate memory » dans la machine virtuelle de 2 Go et 1 Go de swap) ; réussie après un redémarrage de Docker Desktop, cause exacte non identifiée. Mesures avec `--memory=512m --memory-swap=512m --cpus=0.1` : RAM de 285 Mo au repos, 295 Mo après deux questions, 301 Mo après une extraction et deux exports ; scénario 1 juste, cité p. 4, en 2,8 s (dont 1,2 s de recherche, surtout l'appel à Gemini) ; scénario 3 : 7 champs sur 7 en 3,9 s ; scénario 4 : Word et PowerPoint s'ouvrent correctement ; scénario 2 refusé par le Writer et non par le seuil (avec Gemini, le salaire du CEO dépasse 0,44) : à recalibrer en 12.4.

## [2026-10-29] Documents de démo préparés au build, indexés au démarrage
- **Contexte** : le disque de l'hébergeur gratuit est effacé à chaque mise en veille, et l'OCR est lent sur 0,1 processeur.
- **Décision** : `scripts/seed_demo.py` lit chaque fichier de `demo_documents/` comme un téléversement (OCR de la facture compris) et l'enregistre comme prêt, avec ses pages, sans embeddings. Chaque fichier est lu avant d'être enregistré : un fichier illisible ne laisse aucune trace et le script se termine avec le code 1, ce qui fait échouer la construction de l'image. Un fichier déjà enregistré sous le même nom est ignoré. Les originaux ne sont pas copiés dans `uploads/` (rien ne les relit). Au démarrage du conteneur, `scripts.reindex` calcule les vecteurs (4 appels à Gemini).
- **Alternatives écartées** : calculer les embeddings au build (la clé Gemini en argument de build, lisible dans l'historique de l'image) ; indexer dans le démarrage de FastAPI (l'application devrait connaître le mode démo) ; garder les documents ratés avec le statut `failed` (une démo cassée en ligne).
- **Conséquences** : une fois les dépendances installées, le build n'a besoin ni du réseau ni d'une clé. Quelques secondes de plus à chaque réveil. Si Gemini ne répond pas au démarrage, le serveur démarre quand même, sans vecteurs, et les questions sont refusées (vérifié en simulation, à signaler dans le README). Les sessions repartent de zéro à chaque démarrage du conteneur.

## [2026-10-29] Mode démo, route /api/config, frontend servi par FastAPI
- **Contexte** : en ligne, un document téléversé serait visible de tous les visiteurs (aucun compte), et un seul conteneur doit servir l'API et l'interface.
- **Décision** : réglages `DEMO_MODE` (faux par défaut) et `STATIC_DIR` (vide par défaut). En mode démo, `POST /api/documents` répond 403 (« Uploads are disabled in the online demo. ») avant tout traitement. `GET /api/config` renvoie `demo_mode` et `llm_provider`, jamais une adresse ni une clé. `mount_frontend` (`app/frontend.py`) sert `STATIC_DIR` sur `/`, après les routes `/api`, et lève `FrontendNotBuiltError` sans `index.html`, pour qu'un mauvais chemin arrête le serveur au lieu de répondre 404.
- **Alternatives écartées** : Nginx dans le conteneur ; un réglage par fonctionnalité (`UPLOADS_ENABLED`), un seul mode démo suffisant en V1.
- **Conséquences** : rien ne change en local ni avec Docker Compose. Le corps d'un téléversement refusé est quand même reçu par FastAPI avant le 403. Une adresse inconnue renvoie 404, sans retour à `index.html` (suffisant pour un écran unique). Sessions partagées entre visiteurs : accepté, à signaler dans le README.

## [2026-10-28] Embeddings de la démo en ligne : Gemini Embedding, sous réserve du calibrage
- **Contexte** : Groq ne propose pas d'embeddings, et la démo ne doit rien coûter. OVHcloud sans clé est limité à 2 requêtes par minute, par adresse IP et par modèle, et les adresses de sortie de Render sont partagées entre beaucoup de services ; avec une clé, OVH facture au jeton (projet Public Cloud).
- **Décision** : `gemini-embedding-001` par le point d'accès compatible OpenAI de l'API Gemini (`https://generativelanguage.googleapis.com/v1beta/openai`), clé gratuite d'AI Studio, sans carte. Vecteurs de 3 072 dimensions, 4,0 s avec `check_providers`. Condition : en 12.4, `probe_scores` doit montrer un écart net entre les questions hors sujet et les bons passages, et le seuil et l'écart au meilleur score sont mesurés pour ce modèle. Sinon, repli sur OVH `BGE-M3` (testé : 1 024 dimensions, 3,2 s), avec le seuil de 0,44 déjà connu.
- **Alternatives écartées** : OVH sans clé (limite trop basse et partagée pour une démo) ; une clé OVH (payante) ; `bge-m3` dans le conteneur (673 Mo, plus que les 512 Mo de Render) ; comparer les vecteurs d'OVH à ceux de `bge-m3` en local (n'aurait pas changé la décision).
- **Conséquences** : modèles différents en local et en ligne : la démo a son propre index, son propre seuil et son propre écart, et le score de l'évaluation en ligne ne sera pas directement comparable à celui de l'étape 11 (à dire dans le README). Limites gratuites relevées sur le forum de Google (100 requêtes par minute, 1 000 par jour, 30 000 jetons par minute) à confirmer dans AI Studio. Dans l'offre gratuite, Google peut utiliser les textes envoyés : acceptable avec des documents de démo fictifs.

## [2026-10-28] Groq gpt-oss-20b : raisonnement par défaut, mesuré avec probe_online
- **Contexte** : l'offre gratuite de Groq est limitée à 8 000 jetons par minute et 200 000 par jour, et les jetons de raisonnement de `gpt-oss-20b` comptent dans ces limites. Critère fixé avant la mesure : moins de 3 000 jetons par question, sinon un réglage `LLM_REASONING_EFFORT`.
- **Décision** : aucun réglage. `scripts/probe_online.py` fait tourner les vrais agents ; il donne au provider son propre client HTTP, dont les crochets (requête et réponse) lisent le champ `usage` et les en-têtes `x-ratelimit`, attend quand il reste moins de 5 000 jetons dans la minute et s'arrête sur un 429 ; `OpenAICompatibleProvider` n'est pas modifié. Résultats : une question coûte 1 831 jetons en moyenne, dont 434 de raisonnement, en 4,9 s (Writer et Critic) ; extraction de la facture 1 856 jetons, du contrat 3 447 ; mode JSON accepté. Scénario 1 juste en anglais et en français, sans problème signalé par le Critic, sur les 3 passages de la page 4 découpés par le chunker (sans recherche).
- **Alternatives écartées** : `LLM_REASONING_EFFORT=low` (inutile au vu de la mesure, et modifiait le provider) ; lire les jetons consommés dans le provider (changer l'application pour une mesure).
- **Conséquences** : capacité de la démo d'environ 4 questions par minute et 109 par jour, ou 75 extractions par jour. `run_eval` en ligne (12.4) : environ 45 000 jetons et 8 minutes. Le script compte les champs trouvés sans vérifier leur valeur : `run_eval` le fera. 536 tests backend. Une clé exportée dans le terminal fait échouer `test_defaults_run_locally_with_ollama` : lancer les tests avec `env -u LLM_API_KEY -u EMBEDDING_API_KEY`.

## [2026-10-28] Réponses d'embeddings sans champ index acceptées
- **Contexte** : l'API Gemini renvoie les vecteurs sans champ `index`, et `OpenAICompatibleEmbeddingProvider` échouait avec « Unexpected response format ».
- **Décision** : `_in_input_order` (`app/retrieval/embeddings.py`) trie selon `index` quand tous les éléments en ont un, garde l'ordre de la réponse quand aucun n'en a (ce que garantit aussi l'API OpenAI) et lève `EmbeddingError` en cas de mélange. Le contrôle du nombre de vecteurs (`_check_count`) est inchangé. Trois tests.
- **Alternatives écartées** : une classe `GeminiEmbeddingProvider` (code en double pour un seul champ) ; ignorer toujours `index` (dangereux avec un fournisseur qui renverrait les vecteurs dans le désordre).
- **Conséquences** : 510 tests backend. Changer de fournisseur compatible OpenAI revient toujours à changer trois variables, Gemini compris.

## [2026-10-25] Tests de composants avec React Testing Library
- **Contexte** : les 116 tests frontend portaient sur des fonctions pures (`lib/`, `api/`) ; l'affichage n'était vérifié qu'à la main (Chromium sans tête avec un faux backend, Safari, Docker).
- **Décision** : `@testing-library/react`, `@testing-library/dom` et `jsdom` en dépendances de développement. Chaque fichier de test commence par `// @vitest-environment jsdom` (les autres tests gardent leur environnement, `vite.config.ts` inchangé) ; `cleanup` appelé dans `afterEach` (globals de Vitest désactivés) ; vérifications de base de Vitest, sans `jest-dom`. Trois composants, ceux que montre la démo : `CriticReview` (8 tests : vert, « rules only », groupes Certain / To check, message du backend jamais affiché, extraction, français), `ExtractionView` (7 : tableau, page qui ouvre la source, champ manquant, problème sous la bonne valeur, libellés français, refus), `ChatPanel` (8 : citation cliquable vers son passage, verdict et liens d'export, deux types de refus, Entrée / Maj+Entrée, saisie bloquée sans document, mode Extract, langue du contexte ; `scrollIntoView` remplacé, jsdom n'ayant pas de mise en page).
- **Alternatives écartées** : Playwright (navigateur à installer, tests lents, parcours déjà vérifiés à la main) ; `jest-dom` (une dépendance de plus pour des vérifications que Vitest fait) ; environnement jsdom pour tous les tests (plus lent, sans besoin).
- **Conséquences** : 139 tests frontend en moins d'une seconde. Dépendances de développement : 13 à 16. L'image Docker du frontend lance `tsc -b`, qui vérifie aussi les fichiers de test : les dépendances de développement restent installées par `npm ci` à la construction (pas dans l'image finale). Les hooks (`useChat`, `useSessions`, `useDocuments`) restent vérifiés à la main. Sur le CV : « component tests with React Testing Library ».

## [2026-10-25] Premier score de l'évaluation dans Docker ; seuil de 0,44 conservé
- **Contexte** : le jeu d'évaluation doit donner un score vérifiable, et l'étape 11 prévoyait de recalibrer le seuil sur tous les documents de démo.
- **Décision** : score de référence mesuré dans Docker (`run_eval --url http://localhost:8080 --label docker`), conditions de la démo, sans le doublon du contrat de la base native. Résultats, identiques mot pour mot sur deux exécutions (température 0) : 16 questions justes sur 21 (anglais 7 sur 10, français 9 sur 11), 13 sur 21 justes et bien citées, 14 réponses sur 15 dans la langue de la question, 15 champs extraits justes sur 15. Critic : 2 réponses fausses signalées sur 3, 2 fausses alertes sur 9 réponses justes et bien citées, 3 réponses justes mais mal citées signalées sur 3. Les échecs sont les cas connus : scénario 1 en anglais, avoir de mai en anglais (refus du modèle), alerte des certificats (ligne de tableau hors du top 5), chiffre d'affaires d'Orion en anglais et en français (45 370 cité ; non signalé en français). Seuil gardé à 0,44 sans nouvelle mesure : aucune question qui a une réponse n'est refusée par le seuil (les 3 refus à tort viennent du modèle), et les 2 refus par le seuil sont justes (salaire, EN et FR).
- **Alternatives écartées** : un nouveau calibrage avec `probe_scores` (les mesures de l'écart couvrent déjà les quatre documents, facture comprise) ; une évaluation en natif (doublon du contrat, base de développement).
- **Conséquences** : chiffre à mettre en avant dans le README : 62 % de réponses justes et bien citées, 100 % des champs extraits, en local avec `qwen2.5:3b`. Le contrôle des citations par le code est fiable ; le contrôle par le modèle donne encore des fausses alertes. Évaluation à refaire en ligne à l'étape 12 (`gpt-oss-20b`, fournisseur d'embeddings à choisir).

## [2026-10-25] Jeu d'évaluation bilingue noté par le code, sans route /api/extract
- **Contexte** : il faut un jeu de 15 à 20 questions avec réponses attendues, en français et en anglais, et un score affiché.
- **Décision** : `eval/questions.json` : 21 questions (10 en anglais, 11 en français, dont 2 en interlangue ; 15 réponses attendues, 6 refus) et 2 extractions (facture, 7 champs ; contrat, 8 champs). Chaque question donne les textes attendus (plusieurs écritures : « 17 100 », « 17,100 »), les textes interdits (« 30 days » pour le scénario 1), les pages qui contiennent la réponse et une note sur le piège. Réponses vérifiées sur le texte des documents. `scripts/eval_scoring.py` : fonctions pures (lecture et contrôle du fichier, notation, résumé, `results.json`). `scripts/run_eval.py` : appelle l'API réelle ; questions par `/api/ask` limitées aux quatre documents de démo ; extractions par la route de session de l'interface (une session « Extract the key fields of … » créée par exécution, `--no-extractions` pour l'éviter). Notation par le code : réponse juste (texte attendu présent, texte interdit absent), juste et bien citée (une source sur une page attendue), langue de la réponse devinée par des mots courants (ligne séparée), Critic en trois lignes (réponses fausses signalées ; réponses justes et bien citées signalées, les vraies fausses alertes ; réponses justes mais mal citées signalées, alertes justifiées), champs extraits. Détail versionné dans `eval/results.json`.
- **Alternatives écartées** : un LLM juge (un 3B ne juge pas fiablement ses propres réponses) ; une route sans état `/api/extract` (nouveau schéma de réponse et nouvelle route pour un besoin couvert par la route de session) ; une route de suppression de session (dérive de périmètre) ; le code dans `eval/` (ses tests seraient hors de la suite du backend) ; compter faux une réponse juste dans la mauvaise langue (deux qualités différentes).
- **Conséquences** : 507 tests backend. La première version de la notation comptait mal : langue non vérifiée (une question anglaise répondue en français comptée juste) et fausses alertes du Critic surestimées (5 sur 12 au lieu de 2 sur 9 : trois alertes visaient de vraies erreurs de citation) ; corrigé avant de publier le score. Le jeu n'est pas indépendant des réglages : plusieurs questions ont servi au seuil et à l'écart (le droit applicable et le total de la facture 0042 à aucun réglage), à dire dans le README. Code dans `backend/scripts/` et données dans `eval/` : à noter dans `02_architecture.md` à l'étape 13.

## [2026-10-25] Écart au meilleur score : RETRIEVAL_MAX_GAP = 0,05
- **Contexte** : avec `bge-m3`, les scores sont resserrés et le seuil de 0,44 laisse passer presque toujours les 5 passages du top 5 jusqu'au Writer (contre 1 ou 2 avec nomic et 0,60).
- **Décision** : `relevant_passages(passages, min_score, max_gap)` (`app/agents/orchestrator.py`) garde les passages au-dessus du seuil et à moins de `max_gap` du meilleur ; le meilleur est toujours gardé, donc l'écart ne change jamais un refus ni une réponse en refus. Réglage `retrieval_max_gap = 0.05` (`config.py`, `RETRIEVAL_MAX_GAP`, 1 pour revenir au comportement d'avant), passé à l'Orchestrator par `dependencies.py` ; la trace indique « 2 of 5 passages kept (threshold 0.44, gap 0.05, best 0.62) ». Mesuré avec `scripts/probe_margin.py` (recherche par le serveur, filtre appliqué dans le script) : sur les 53 questions de `probe_scores`, 2,9 passages en moyenne au lieu de 4,9 et aucun bon passage perdu (le seul « LOST », le taux d'intérêt, est aussi sur la facture) ; Writer et Critic dans Docker sur 11 questions : verdicts identiques, temps du modèle 22,9 s au lieu de 61,7 s.
- **Alternatives écartées** : un écart de 0,03 (perd la ligne du tableau de la disponibilité de mai) ; réduire `top_k` (coupe aussi les réponses qui ont besoin de plusieurs passages) ; un écart relatif, en pourcentage du meilleur score (plus difficile à expliquer, non mesuré).
- **Conséquences** : 469 tests backend ; confirmé dans Docker avec `probe_writer_fr` par `/api/ask`. Aucune ré-indexation. Réponses locales environ 2,5 fois plus rapides ; sur le scénario 1, l'erreur est signalée par le code (« Certain ») et non plus par le modèle (« To check »). Une réponse répartie sur des passages aux scores éloignés recevrait moins de contexte (non observé). `probe_writer_fr` avait été mesuré à l'étape 10 bis avec nomic et 0,60 : pas comparable directement.

## [2026-10-25] Scénario 1 en anglais : limite du 3B en local ; découpage par articles et ordre de lecture écartés
- **Contexte** : « What is the termination notice period? » répond « 30 days » (délai de remédiation de l'article 4.4) à côté de « 60 days » (préavis de l'article 4.3). Mesurer avant de décider, en anglais et en français.
- **Décision** : quatre mesures. (1) `probe_margin` : l'écart au meilleur score ne change pas la justesse (6 sur 11 quel que soit l'écart). (2) Découpage de la page 4 par le chunker : le premier passage contient l'article 4.3 et le début du 4.4 ; aucun filtre ne peut l'en séparer. (3) `scripts/probe_clauses.py` (passages construits à la main, vrais Writer et Critic) : les articles 4.1 à 4.3 seuls, puis 4.4 dans un passage séparé, donnent 2 réponses justes sur 2 ; le 4.4 en premier, 0 sur 2 (en français : refus). (4) Une option de découpage aux numéros de clause (`clause_breaks`), mesurée en mémoire avec `bge-m3` : neutre ailleurs, seuil inchangé, mais le passage du 4.4 arrive premier en anglais (0,623 contre 0,606) ; combinée à un ordre de lecture des passages (document, page, position) et mesurée de bout en bout sur 11 questions avec une règle fixée avant la mesure, elle rend l'anglais juste mais casse le français (la page 3 passe avant la page 4, réponse sur l'article 4.2). Non adoptée. Le scénario 1 en anglais est une limite connue de `qwen2.5:3b` en local ; la vidéo de l'étape 13 sera tournée avec la démo en ligne (`gpt-oss-20b`), à mesurer à l'étape 12. L'option `clause_breaks` et les deux scripts de mesure qui en dépendaient sont retirés ; `probe_margin` et `probe_clauses` sont gardés.
- **Alternatives écartées** : retoucher le prompt du Writer (réglage sur une seule question, déjà écarté à l'étape 6) ; changer la question de la vidéo (masquerait la limite) ; un reranker (PyTorch, contraire au budget de 8 Go) ; garder le découpage aux articles seul (ne règle pas l'ordre, code de plus sans gain mesuré).
- **Conséquences** : `qwen2.5:3b` est très sensible à l'ordre et au voisinage des passages ; aucune règle générale de découpage ou d'ordre ne donne le scénario juste dans les deux langues (README, limitations connues). En local, l'interface montre l'erreur honnêtement : le Critic la signale. Environ une journée passée sur ce scénario, arrêtée comme prévu après la dernière mesure.

## [2026-10-25] Étape 10 bis validée dans Docker ; scénario 1 dégradé, à régler à l'étape 11
- **Contexte** : le changement de modèle d'embedding, la nouvelle interface et l'export traduit doivent fonctionner avec le frontend compilé servi par Nginx et la base du volume Docker.
- **Décision** : aucune modification des Dockerfiles ni de `docker-compose.yml` : les nouvelles valeurs par défaut (`bge-m3`, sans préfixes, seuil 0,44) sont dans `config.py`, et le conteneur appelle `bge-m3` dans l'Ollama du Mac. Reconstruction avec `docker compose up -d --build` (3,7 s : pour la première fois, aucune des trois images de base n'avait changé d'empreinte), puis `docker compose stop backend`, `docker compose run --rm backend python -m scripts.reindex` (6 documents, 29 vecteurs) et `docker compose start backend`. Le compte rendu français est téléversé par l'interface.
- **Alternatives écartées** : recréer le volume (inutile : la ré-indexation lit les pages déjà en SQLite, et le nouveau modèle a sa propre collection Chroma).
- **Conséquences** : parcours validé sur `localhost:8080` en anglais et en français : refus du salaire du CEO en 0,1 s, question française sur Marseille (17 100,00 USD, pages 2 et 3, aucun problème), extraction de la facture en français (7 champs sur 7, libellés traduits, durées « 1,3 s »), export Word en français, session et langue conservées au rechargement. **Point ouvert prioritaire pour l'étape 11** : le scénario 1 (« What is the termination notice period? ») répond désormais « 60 days for convenience termination or 30 days for material breach termination », la confusion délai de remédiation / préavis déjà connue ; le Critic la signale (« To check »). Cause probable : avec le seuil de 0,44, les 5 passages du top 5 vont au Writer (dont l'article 4.4), contre 1 ou 2 avec nomic et 0,60. Piste déjà notée : ne garder que les passages proches du meilleur score. À régler avant la vidéo (étape 13).

## [2026-10-25] Interface en français : contexte de langue, sélecteur EN | FR
- **Contexte** : l'interface doit être utilisable en français et en anglais, au choix de l'utilisatrice, sans réécrire les composants (dictionnaire préparé à l'étape 7).
- **Décision** : dictionnaire `fr` du type `Messages` dans `lib/i18n.ts` (TypeScript signale toute entrée manquante ; espace insécable avant `:` et `?` ; décimales et pluriels français). `LanguageContext` et `useLanguage()` ; `useMessages()` lit la langue courante. `components/LanguageProvider.tsx` garde la langue, l'enregistre sous `atlas.language` (fonctions sans erreur de `lib/language.ts`) et met à jour `<html lang>`. Au premier chargement : la langue du navigateur (français si elle commence par `fr`, sinon anglais). `components/LanguageSwitch.tsx` : « EN | FR » dans l'en-tête, avec les classes du sélecteur Ask / Extract ; chaque langue est nommée dans sa propre langue pour les lecteurs d'écran. Les noms des agents restent en anglais. Les durées suivent la langue des dates (`Intl.NumberFormat`, « 2,9 s »). Les libellés des champs extraits sont traduits par nom de champ (`fieldLabels`), le libellé du backend sert de secours. Deux textes français raccourcis après la première capture (« Téléverser », « Questions : 4 documents sur 4. »).
- **Alternatives écartées** : passer la langue en paramètre à chaque composant (tous à modifier) ; anglais par défaut au premier chargement (moins naturel pour une visiteuse francophone) ; traduire les noms des agents (ce sont les noms de l'architecture).
- **Conséquences** : 116 tests frontend. Le parcours a été vérifié dans un Chromium sans tête avec un faux backend (changement de langue sans aucune requête, lien d'export, erreur 503 traduite), puis dans Safari en natif et dans Docker. Le titre d'une session reste dans la langue de sa première demande, enregistrée par le backend.

## [2026-10-25] Erreurs de l'API traduites par le frontend, sans code d'erreur
- **Contexte** : les messages d'erreur du backend sont en anglais et étaient affichés tels quels.
- **Décision** : `apiErrorText(error, opération, t)` (`lib/errors.ts`) écrit le message à partir de l'opération (téléversement, question, extraction, sessions, documents) et du statut HTTP : 0 injoignable, 413 trop gros, 400 type non accepté (téléversement), 404 élément disparu, 409 document pas prêt (extraction), 422 requête invalide, 503 « Ollama est-il lancé ? », sinon le statut. Le détail du backend n'est jamais affiché. La raison d'échec d'un document, enregistrée en anglais, est présentée dans un cadre traduit (« Lecture impossible : … »).
- **Alternatives écartées** : un champ `code` dans les erreurs du backend (7 fichiers de routes à modifier, alors que l'opération et le statut suffisent) ; une colonne de code pour les raisons d'échec (changement de schéma pour des cas rares en démo).
- **Conséquences** : aucun changement du backend. Le détail technique n'est plus visible dans l'interface (il reste dans l'onglet réseau). Une erreur déjà affichée garde sa langue si l'on change de langue ensuite. `errorText` n'est plus utilisé : à retirer à l'étape 13, avec `toggleId` et `usableIds`.

## [2026-10-25] Chargements initiaux indépendants de la langue
- **Contexte** : les `useEffect` de chargement de `useDocuments` et `useSessions` dépendaient des textes `t`. Avec le sélecteur, changer de langue les aurait relancés : liste des documents rechargée, et surtout session du chargement de la page rouverte à la place de la session en cours.
- **Décision** : les textes sont lus à travers une référence (`tRef`), mise à jour à chaque affichage comme `onOpenedRef`. Les effets ne dépendent plus que de `initialId` (sessions) ou de rien (documents).
- **Alternatives écartées** : garder `t` dans les dépendances et ignorer le second chargement (fragile, la session serait quand même rouverte).
- **Conséquences** : vérifié dans le navigateur : aucune requête au changement de langue, conversation conservée.

## [2026-10-25] Demande d'extraction gardée par nom de fichier
- **Contexte** : le backend enregistre la demande en anglais (« Extract the key fields of … ») ; affichée telle quelle, elle restait en anglais dans une interface en français.
- **Décision** : un message de l'utilisatrice peut porter `extractOf` (nom du fichier) ; `ChatPanel` écrit la demande dans la langue du moment, `text` sert de secours. En direct, `useChat` transmet le nom du document ; à la restauration, `extractedFilename` relit le nom après `EXTRACT_REQUEST_PREFIX`, seulement pour les messages en mode `extract` (une extraction refusée garde aussi son nom).
- **Alternatives écartées** : réécrire la demande dans `restoreMessages` avec les textes de la langue courante (elle ne changerait plus au changement de langue) ; enregistrer la demande dans la langue de l'utilisatrice (le backend devrait connaître la langue).
- **Conséquences** : le texte « Extract the key fields of … » devient un contrat entre `app/api/sessions.py` et `lib/chat.ts`, comme le format des citations.

## [2026-10-25] Export en anglais ou en français : paramètre lang
- **Contexte** : les fichiers Word et PowerPoint doivent suivre la langue de l'interface.
- **Décision** : instance `FRENCH` de `ExportTexts` et `EXPORT_TEXTS = {"en", "fr"}` (`app/export/content.py`), avec les mois, « 1er » pour le premier jour (`first_day`), les textes du Critic, les types de document et les 15 libellés des champs (`field_labels`, vide en anglais). La ligne « Demande » d'une extraction est écrite par l'export (`extraction_request`) et non recopiée du message enregistré en anglais. Route d'export : `&lang=en|fr`, `en` par défaut, 422 pour une autre langue ; le frontend ajoute la langue courante au lien. Restent tels qu'écrits : la question, la réponse, les valeurs extraites, les passages et le nom du fichier téléchargé (sans accent dans l'en-tête HTTP).
- **Alternatives écartées** : traduire la réponse (appel au LLM, contraire à un export sans LLM) ; un nom de fichier français (accents dans `Content-Disposition`).
- **Conséquences** : 438 tests backend. Les liens existants sans `lang` donnent le même fichier qu'avant. Vérifié dans Pages et Keynote.

## [2026-10-25] Critic : nombres lus aux formats anglais et français
- **Contexte** : `numbers_in` lisait « 99,38 » comme 9938 et coupait « 45 370,00 » en deux nombres. Un nombre juste écrit au format français à partir d'une source anglaise (ou l'inverse) aurait été signalé `unsupported_number` (« Certain »).
- **Décision** : `number_readings` donne les valeurs possibles d'un nombre écrit : espaces des milliers (normale, insécable, fine insécable), dernier séparateur décimal quand il y en a deux, virgule décimale, et les deux lectures pour les cas ambigus (« 12,500 » : 12500 ou 12.5 ; « 1.500 »). Un nombre est accepté si l'une de ses lectures figure dans les passages cités ; le message donne le nombre tel qu'il est écrit. `appears_in` (montants extraits) utilise la même règle.
- **Alternatives écartées** : deviner la langue du texte pour choisir le format (peu fiable sur une phrase, une réponse française peut recopier « 12,500 »).
- **Conséquences** : vérification un peu plus permissive (« 12,500 » accepté face à « 12.5 »). Un nombre suivi d'un groupe de trois chiffres serait fusionné (« en 2026 300 colis »), cas rare. Honnêteté de la mesure : l'alerte observée avec `probe_writer_fr` (« 99,38% ») était en fait juste (page citée sans ce chiffre) ; la correction prévient un défaut démontré par les tests, sans cas réel bien cité observé.

## [2026-10-25] Langue des réponses : celle de la question, sans champ language dans l'API
- **Contexte** : le plan prévoyait un champ `language` pour imposer la langue des agents ; il fallait d'abord mesurer le comportement de `qwen2.5:3b`.
- **Décision** : garder la règle du Writer (« in the language of the question »), écrite à l'étape 6. Script `scripts/probe_writer_fr.py` : 11 questions par `/api/ask`, limitées aux documents de démo. Résultat (identique sur deux exécutions, température 0) : 9 réponses sur 9 dans la langue de la question, y compris en interlangue, 8 sur 9 citées, refus du salaire du PDG par le seuil.
- **Alternatives écartées** : un champ `language` sur `/ask` et `/extract` (inutile au vu de la mesure, change l'API).
- **Conséquences** : aucune modification de l'API. Cas pour l'étape 11 : fausse alerte du modèle sur « Le préavis de résiliation est de 60 jours » (phrase française, passage anglais) ; marqueur inventé `[SL1]` (citation perdue) ; « chiffre d'affaires d'Orion » répondu par 45 370,00 USD (risque déjà connu en anglais) ; « Qui doit mettre en place l'alerte d'expiration des certificats ? » (ligne de tableau hors du top 5).

## [2026-10-25] Modèle d'embedding multilingue : bge-m3, seuil 0,44
- **Contexte** : `nomic-embed-text` est surtout anglais ; une question française doit trouver un passage anglais et inversement, dans les 8 Go de RAM.
- **Décision** : `bge-m3` (sans préfixes), seuil `RETRIEVAL_MIN_SCORE = 0.44`. Choix mesuré avec `scripts/probe_embeddings.py` : script autonome (parseurs et chunker d'ATLAS, similarité calculée en mémoire, aucune écriture dans la base ou l'index), validé parce qu'il retrouve pour nomic les valeurs notées à l'étape 6 (0,645, 0,620, 0,810). Critères fixés avant la mesure. Résultats : nomic ne place aucun bon passage dans le top 5 pour les 6 questions françaises sur le contrat ; `bge-m3` a les meilleurs écarts en anglais (contrat −0,027 contre −0,093 pour nomic) et en interlangue (5/6 et 3/3 premiers, aucun manqué), 673 Mo en mémoire contre 370. Seuil vérifié sur le vrai index avec `probe_scores` (jeux `contract`, `review`, `minutes`, `contract-fr`, `minutes-en`) : hors sujet au plus 0,426 (salaire du CEO, poussé par `test_document.docx`), bons passages du top 5 dès 0,464. Le seuil penche vers les bons passages : une question hors sujet qui passe est refusée par le Writer, un bon passage perdu est une réponse perdue. Les jeux de questions français sont dans `probe_scores.py`, importés par `probe_embeddings.py`.
- **Alternatives écartées** : `nomic-embed-text-v2-moe` (hors sujet jusqu'à 0,270 contre 0,282 pour le préavis en français : marge trop faible ; un passage du contrat hors du top 5) ; `granite-embedding:278m` (le plus faible partout) ; garder nomic (repli prévu, inutile).
- **Conséquences** : ré-indexation native (`scripts.reindex`) et Docker ; l'ancien index nomic reste dans sa propre collection. Échelle des scores plus resserrée (0,26 à 0,70) : marge absolue de 0,055 seulement entre hors sujet et bon passage. Les questions absentes mais proches du sujet (0,46 à 0,64) restent refusées par le Writer. À recalibrer à l'étape 11 sur le jeu d'évaluation, et à l'étape 12 avec un fournisseur d'embeddings en ligne qui propose `bge-m3`. Les modèles écartés peuvent être supprimés d'Ollama (`ollama rm`).

## [2026-10-25] Document de démo en français : compte rendu de comité de pilotage
- **Contexte** : il faut un document français pour démontrer les questions en français et la recherche interlangue.
- **Décision** : `scripts/make_demo_minutes_fr.py` (`fpdf2`, déjà dans `requirements-dev.txt`) produit `demo_documents/compte_rendu_copil_HDS_2026-07.pdf` : comité du 15 juillet 2026 avec Orion Freight France SAS (filiale du client, entrepôts de Lyon et du Havre), PDF texte de 3 pages, un sujet par page. Chiffres repris de la revue au format français (99,74 %, 4 h 37 min, 625,00 USD, 45 370,00 USD) et devis de Marseille calculé avec `Decimal` (18 jours à 950 USD, 17 100,00 USD). La panne du 14 mai reste celle de la revue (stockage à Francfort) ; l'expiration d'un certificat au Havre est le second incident. Relecture par le parseur, fichier identique à chaque exécution.
- **Alternatives écartées** : un scan (Tesseract `fra` à ajouter à l'image) ; `reportlab` (absent du projet) ; un document pour l'extraction (mots-clés de l'Analyst et formats du Critic à doubler).
- **Conséquences** : document réservé au mode Ask ; l'extraction en français porte sur les documents anglais, avec une interface et des libellés en français. Polices intégrées de `fpdf2` : Latin-1 seulement (apostrophe droite, pas de « œ »).

## [2026-10-24] Étape 10 validée dans Docker
- **Contexte** : l'export doit fonctionner avec le frontend compilé servi par Nginx et la base du volume Docker.
- **Décision** : aucune modification des Dockerfiles ni de la configuration Nginx ; reconstruction avec `docker compose up -d --build`. La revue trimestrielle est téléversée dans le volume par l'interface.
- **Alternatives écartées** : aucune.
- **Conséquences** : scénario 4 validé sur `localhost:8080` : réponse « How much was invoiced in Q2 2026? » (USD 45,370.00, p. 5) exportée en Word, extraction de la facture exportée en PowerPoint (`ATLAS_extraction_…`), fichiers ouverts dans Pages et Keynote. Nginx transmet le fichier et l'en-tête `Content-Disposition` sans réglage. L'image `python:3.13-slim` a encore changé d'empreinte : build du backend de 13 min 25 (Tesseract 481 s, `pip install` 302 s), les images du frontend étaient en cache. Argument de plus pour la décision de l'étape 12 sur le fait de figer les images.

## [2026-10-23] Interface : liens d'export sous chaque résultat
- **Contexte** : le scénario 4 demande un bouton Exporter ; le frontend ne gardait pas l'identifiant en base des messages (identifiants locaux `position + 1`).
- **Décision** : les messages `done` et `extracted` du `chatReducer` reçoivent `saved: SavedRef` (`sessionId`, `messageId`) : en direct, depuis `saved.answer.id` de la réponse de l'API ; pour une session relue, depuis `restoreMessages(messages, sessionId)`. `lib/export.ts` : `exportUrl`, `canExportAnswer`, `canExportExtraction` (fonctions pures testées). `components/ExportLinks.tsx` : « EXPORT ↓ Word ↓ PowerPoint », deux liens `<a href download>` vers la route d'export, sur la ligne des agents (bloc `answer-footer`, retour à la ligne si la place manque). Aucun lien sous un refus. Textes dans `lib/i18n.ts`, avec un libellé complet pour les lecteurs d'écran.
- **Alternatives écartées** : un `fetch` puis un `Blob` téléchargé par JavaScript (état d'attente et gestion d'erreur à coder pour un export instantané) ; exporter la session entière (dérive de périmètre, refus et erreurs au milieu).
- **Conséquences** : 100 tests frontend. Si le serveur répondait par une erreur, le navigateur téléchargerait le message d'erreur au lieu de l'afficher : peu probable, le lien n'apparaissant que sur un résultat exportable (à signaler dans le README).

## [2026-10-23] Route d'export : GET, fichier construit en mémoire
- **Contexte** : l'export doit partir du message enregistré, sources comprises, et fonctionner sur un hébergeur sans disque persistant.
- **Décision** : `GET /api/sessions/{session_id}/messages/{message_id}/export?format=docx|pptx` (`app/api/export.py`). Le message est cherché parmi ceux de la session (`list_messages`) : session ou message inconnu, ou message d'une autre session : 404 ; question ou refus : 409 ; format absent ou inconnu : 422 (`Literal`). La question exportée est le message de l'utilisatrice qui précède. Réponse avec le type MIME du format et `Content-Disposition: attachment; filename="ATLAS_answer_2026-10-23.docx"`. Heure de génération par une dépendance (`get_export_time`), remplacée dans les tests. Aucun appel au LLM, rien n'est écrit sur le disque.
- **Alternatives écartées** : POST avec le contenu affiché par le frontend (la base est la source de vérité, le contenu serait à revalider) ; une méthode `get_message` dans le dépôt (`list_messages` suffit pour quelques dizaines de messages).
- **Conséquences** : 388 tests backend. Vérifié en natif avec `curl` (en-têtes et fichiers ouverts dans Pages et Keynote). L'export fonctionne même si Ollama est arrêté.

## [2026-10-23] Fichiers Word et PowerPoint : un contenu commun, deux rendus
- **Contexte** : les deux formats doivent montrer les mêmes informations, avec le style « Lagon ».
- **Décision** : `app/export/content.py` : `build_export` transforme un `MessageOut` en `ExportContent` (titre, demande, réponse ou lignes du tableau, verdict en phrases, sources). Les textes fixes sont dans `ExportTexts` / `ENGLISH` (mois compris, pour une date identique sur le Mac et dans Docker). Les problèmes d'une extraction sont placés sous la valeur concernée ; les champs lus dans le même passage partagent une source (« Used for: … ») ; deux passages de la même page forment une source. `readable_text` reprend `readableText` du frontend, avec les mêmes cas de test. `docx_export.py` : titres turquoise, tableau, passages complets sur fond clair (`w:shd`), pied de page daté. `pptx_export.py` (16:9) : titre, réponse ou tableau avec le verdict (4 problèmes au plus, taille du texte selon la longueur), sources à 2 par diapositive, coupées à 700 caractères. Le titre de la session n'est que dans les propriétés du fichier.
- **Alternatives écartées** : un gabarit `.dotx` / `.potx` (dérive de périmètre) ; traiter à part les lignes de tableau jointes dans les passages PPTX (l'export resterait différent du panneau Source) ; inclure la trace des agents (trop technique pour un document remis).
- **Conséquences** : les textes du verdict existent dans le frontend et dans le backend : l'étape 10 bis ajoutera une instance `FRENCH`. Les lignes de tableau d'une diapositive apparaissent jointes dans les sources, comme dans l'interface (à signaler dans le README).

## [2026-10-23] Critic : citations placées après le point final
- **Contexte** : sur « How much was invoiced in Q2 2026? », le Writer a écrit `… 45,370.00. [S1][S2]` ; `split_sentences` coupait après le point, la phrase restait sans citation et le Critic signalait à tort `uncited_sentence` (« Certain »). Au milieu d'une réponse, la citation était attribuée à la phrase suivante.
- **Décision** : avant le découpage, les citations qui suivent directement `.`, `!` ou `?` sont déplacées devant ce signe (`_CITATIONS_AFTER_END`). Trois tests, dont un qui vérifie qu'une phrase vraiment non citée reste signalée.
- **Alternatives écartées** : demander au Writer de citer avant le point (un 3B ne le respecte pas toujours).
- **Conséquences** : verdict juste sur la même question, vérifié dans l'interface. La réponse déjà enregistrée garde son ancien verdict.

## [2026-10-23] Revue trimestrielle de démo et mesure des scores
- **Contexte** : le troisième document de démo devait démontrer le parsing PPTX et une question chiffrée à exporter.
- **Décision** : `scripts/make_demo_review.py` produit `demo_documents/quarterly_review_HDS_Q2_2026.pptx` : revue fictive du Q2 2026 (avril à juin) de Helix pour Orion, 6 diapositives (un sujet par diapositive), deux tableaux. Chiffres calculés avec `Decimal` d'après les articles 2.5, 2.6, 3.1 et 3.6 du contrat (disponibilité moyenne 99.74 %, panne de mai de 4 h 37 min, crédit de USD 625, total facturé USD 45,370.00) ; la facture d'avril est la facture de démo. Relecture par le parseur d'ATLAS à la fin du script ; dates fixes dans le fichier et dans le zip, pour un fichier identique à chaque exécution. `probe_scores` reçoit l'option `--set contract|review` et le score du bon passage (bon fichier, bonne page), même quand un autre document arrive en tête.
- **Alternatives écartées** : une revue du Q1 (un seul mois de service, le contrat commençant le 1er mars) ; des graphiques ou des notes du présentateur (texte non extrait par le parseur).
- **Conséquences** : avec le seuil de 0,60, le bon passage obtient 0,620 à 0,803 sur 9 questions (premier 8 fois sur 9 ; les tickets de support passent derrière l'article 2.4 du contrat). Le salaire du CEO reste refusé par le seuil (0,554). Les questions absentes mais proches du sujet passent largement le seuil (chiffre d'affaires d'Orion 0,810, incidents de juillet 0,681) : le refus dépend du Writer et du Critic. Deux cas pour le jeu d'évaluation de l'étape 11, dont le risque de répondre « 45,370 » au chiffre d'affaires d'Orion (c'est ce qu'Orion a payé).

## [2026-10-22] Étape 9 validée dans Docker
- **Contexte** : les agents, l'extraction et le nouvel affichage doivent fonctionner avec le frontend compilé servi par Nginx et la base du volume Docker.
- **Décision** : aucune modification des Dockerfiles ; reconstruction avec `docker compose up -d --build`. Au démarrage, `add_missing_columns` ajoute `messages.review` et `messages.extraction` à la base existante, sans erreur et sans perte des sessions. La facture de démo est téléversée dans le volume par l'interface (OCR dans le conteneur).
- **Alternatives écartées** : recréer le volume (`docker compose down -v`), inutile grâce à la mise à jour automatique des colonnes.
- **Conséquences** : scénarios 1 à 3 validés sur `localhost:8080` : réponse citée (page 4, verdict « no problem found », Retrieval 43 ms → Writer 5,5 s → Critic 2,6 s), refus immédiat en 0,1 s (Writer et Critic « not run »), extraction de la facture, session relue après rechargement. Les trois images de base (`python:3.13-slim`, `node:24-alpine` et, pour la première fois, `nginx:stable-alpine`) ont changé d'empreinte : build complet de 6,5 minutes. La question de figer les images (étape 12) concerne les trois.

## [2026-10-22] Interface : agents intervenus, verdict du Critic, mode Ask / Extract
- **Contexte** : la démo doit montrer quels agents ont travaillé, ce que le Critic a vérifié, et permettre une extraction depuis l'interface.
- **Décision** : sous chaque réponse, une ligne « AGENTS » avec les étapes dans l'ordre du plan et leur durée (`lib/trace.ts` : « < 1 ms », « 4 ms », « 3.3 s » ; un agent arrêté en corail « stopped », un agent non exécuté en gris « not run »). Verdict du Critic (`components/CriticReview.tsx`) : une ligne verte sans problème (« rules only » si seul le code a vérifié), sinon un encadré corail en deux groupes, « Certain » (problèmes du code) et « To check » (problèmes du modèle, avec un avertissement). Tous les textes sont écrits par le frontend à partir du nom de l'agent, du statut et du code du problème (`lib/i18n.ts`), jamais à partir des champs `summary` et `message` du backend. Sélecteur Ask / Extract dans la zone de saisie ; en Extract, liste des documents prêts, indépendante des cases cochées (le premier coché est présélectionné, `lib/extraction.ts`). Résultat en tableau (`components/ExtractionView.tsx`) : champ, valeur en serif, pastille de page qui ouvre le panneau Source, problèmes du Critic sous la valeur concernée. Un nouveau type de message `extracted` dans `chatReducer`, restauré par `restoreMessages`. `OpenSource` distingue une citation de réponse (`answer`) d'une valeur extraite (`field`) : pour une valeur, le panneau explique d'où elle vient et masque le score de similarité.
- **Alternatives écartées** : afficher le `summary` technique du backend (non traduisible à l'étape 10 bis) ; limiter l'extraction aux documents cochés (il faudrait cocher puis décocher pour une simple extraction) ; deux listes de messages séparées pour les questions et les extractions (ordre difficile à garder) ; afficher « 0 ms » pour le Critic par le code (semble dire que l'agent n'a rien fait).
- **Conséquences** : 95 tests frontend. Vérifié avec un faux backend (captures et parcours en direct), puis en natif et dans Docker avec `qwen2.5:3b`. Le texte de la demande (« Extract the key fields of … ») est enregistré en anglais par le backend : à faire écrire par le frontend à l'étape 10 bis. Deux documents de même nom donnent deux marqueurs de citation identiques (doublon de la base native) : à signaler dans le README.

## [2026-10-22] API de l'extraction : route de session, sélection inchangée
- **Contexte** : le plan `extract` doit être appelable depuis l'interface et son résultat enregistré dans l'historique.
- **Décision** : `POST /api/sessions/{id}/extract` avec `{"document_id"}`. Session ou document inconnu : 404 ; document pas prêt ou sans texte : 409 ; tous vérifiés avant tout appel au LLM. `LLMError` : 503, rien n'est enregistré (`extract_or_503`). Le message user est écrit par le code ; le message assistant a `mode="extract"`, `status` `answered` ou `refused` (`refusal_reason="unsupported_document"`, ajouté à `RefusalReason`), l'extraction, le verdict et la trace. Les sources des valeurs ne sont que dans `extraction` (`sources` reste vide). Une extraction ne modifie pas les documents sélectionnés de la session (`add_exchange(document_ids=None)`). Réponse au format de `SessionAskResponse`, partagée avec `/ask` (`exchange_response`). `IssueOut.field` facultatif, `None` par défaut.
- **Alternatives écartées** : 400 ou 422 pour un document pas prêt (422 est déjà utilisé par FastAPI pour un corps invalide) ; recopier les sources dans `sources` (données en double) ; `session_documents = [document_id]` (une extraction effacerait la sélection des questions) ; une route sans état `/api/extract` (rien ne la demande ; à ajouter à l'étape 11 si l'évaluation en a besoin) ; renommer `SessionAskResponse` (changement cosmétique qui touche le frontend).
- **Conséquences** : 337 tests backend. Mesures avec `qwen2.5:3b` en natif : facture en 8,2 s (Analyst 3,3 s, Extractor 4,9 s, Critic 4 ms), contrat en 10,7 s (Analyst 2,0 s, Extractor 8,7 s) ; 15 champs justes sur 15, dont la date d'effet (1 March 2026 et non la date de signature) et le préavis de 60 jours (sans confusion avec le délai de remédiation). Chaque champ porte une copie complète de sa source (11 Ko pour la facture) : accepté en V1, comme pour les citations.

## [2026-10-22] Plan extract et source de chaque valeur
- **Contexte** : une extraction doit passer par Analyst, Extractor et Critic, et chaque valeur doit pointer vers une page vérifiable.
- **Décision** : `EXTRACT_PLAN` = analyst → extractor → critic, exécuté par la même boucle que le plan `ask`. `Orchestrator.extract(repository, document)` renvoie un `ExtractOutcome` (statut `extracted` / `refused`, type de document, valeurs, verdict, trace), avec un message écrit par le code et la forme JSON enregistrée (`extraction_dict`). La source d'une valeur est le chunk de sa page qui contient la valeur. Un document « other » : analyst `refused`, extractor et critic `skipped`.
- **Alternatives écartées** : demander au modèle de citer le passage (un 3B recopie mal les sources) ; source = page entière (pas de passage précis à afficher).
- **Conséquences** : une valeur dont la page ne contient pas le texte n'a pas de source cliquable, et le Critic la signale.

## [2026-10-22] Critic d'extraction : contrôles par le code seulement
- **Contexte** : une valeur extraite est vérifiable mécaniquement contre les pages, contrairement à une phrase libre.
- **Décision** : `review_extraction(result, pages)` : `missing_required_field`, `value_not_found`, `wrong_page`, `unreadable_date`, `unreadable_amount`. Les comparaisons normalisent le texte et les nombres (zéros décimaux finaux ignorés). `Issue` reçoit un champ `field`.
- **Alternatives écartées** : un contrôle par le modèle (lent, avec des fausses alertes mesurées en 9.2, pour une vérification que le code fait mieux).
- **Conséquences** : le contrôle prend moins d'une milliseconde ; tous ses problèmes sont « certains » dans l'interface.

## [2026-10-22] Champs fixes par type de document et Extractor
- **Contexte** : un 3B extrait mal des champs libres et invente des clés.
- **Décision** : `FieldSpec` (nom, libellé, type `text` / `date` / `amount`, obligatoire, description). `INVOICE_FIELDS` : numéro, date, échéance et total obligatoires ; devise, fournisseur, client. `CONTRACT_FIELDS` : numéro d'accord, prestataire, client et date d'effet obligatoires ; durée initiale, préavis de résiliation, préavis de non-renouvellement, droit applicable. L'Extractor demande un JSON `{"fields": {nom: {"value", "page"}}}` avec des valeurs recopiées exactement ; les champs ajoutés par le modèle sont ignorés, un nombre est converti en texte ; un JSON invalide lève `LLMError`.
- **Alternatives écartées** : champs choisis par l'utilisateur (hors périmètre V1) ; schéma Pydantic généré à la volée (plus complexe, même résultat).
- **Conséquences** : comportement prévisible et testable. Ajouter un type de document revient à ajouter une liste de champs.

## [2026-10-22] Document Analyst : type par le modèle, pages par le code
- **Contexte** : l'Extractor doit recevoir les bonnes pages sans dépasser le contexte de 4096 tokens.
- **Décision** : le type (`invoice` / `contract` / `other`) est demandé au modèle (JSON validé), avec des mots-clés de secours ; si le modèle répond « other » alors que les mots-clés obtiennent au moins 2, les mots-clés décident. Les pages sont choisies par le code d'après les mots-clés des champs, dans un budget de 8 000 caractères (`MAX_EXTRACTION_CHARS`). En cas de panne du modèle, l'Analyst se rabat sur les mots-clés.
- **Alternatives écartées** : pages choisies par le modèle (peu fiable avec un 3B) ; envoyer tout le document (dépasse le contexte).
- **Conséquences** : contrat → pages 1, 2, 4 et 6 ; facture → page 1. Un document « other » est refusé sans appel à l'Extractor.

## [2026-10-22] Seuil de pertinence trop haut pour la facture scannée : reporté à l'étape 11
- **Contexte** : sur « total amount due and when », le chunk qui contient la réponse obtient 0,59, sous le seuil de 0,60, et le petit dernier chunk 0,667 : le Writer répond `NOT_FOUND`, à juste titre.
- **Décision** : ne rien changer maintenant.
- **Alternatives écartées** : baisser le seuil sur un seul exemple (réglage à l'aveugle, risque de laisser passer des questions hors sujet).
- **Conséquences** : causes identifiées (seuil calibré sur un texte rédigé, lignes de tableau mal lues par Tesseract, petit dernier chunk). À l'étape 11 : recalibrer avec `probe_scores` sur tous les documents de démo, et envisager de garder les passages proches du meilleur. Le mode Extract n'est pas concerné (pas de retrieval).

## [2026-10-22] Facture de démo fictive, scannée, générée par script
- **Contexte** : le scénario 3 demande une vraie facture scannée, cohérente avec le contrat.
- **Décision** : `scripts/make_demo_invoice.py` (Pillow, police intégrée, grain à graine fixe, vérification OCR intégrée) produit `demo_documents/invoice_HDS-INV-2026-0042.pdf`, sans couche texte. Données cohérentes avec les articles 3.1 à 3.4 du contrat : 1 April 2026, échéance 1 May 2026, total USD 15,950.00, Agreement No. HDS-2026-014.
- **Alternatives écartées** : une facture réelle (confidentialité) ; un PDF texte (ne démontre pas l'OCR).
- **Conséquences** : facture reproductible à l'identique. Lue par OCR en natif et dans Docker.

## [2026-10-22] Critic des réponses : contrôles par le code, contrôle par le modèle mesuré
- **Contexte** : le Writer 3B peut citer de travers ou inventer un chiffre ; le Critic doit le signaler sans modifier la réponse.
- **Décision** : contrôles par le code : `invented_citations`, `no_citation`, `uncited_sentence`, `unsupported_number` (nombres normalisés, numéros de page des citations retirés). Contrôle par le modèle (`CRITIC_USE_LLM`, activé par défaut) : JSON `{"unsupported": [...]}` sur les phrases numérotées ; une réponse inutilisable donne `model_checked: false`, jamais un échec. Plan `ask` = retrieval → writer → critic. Verdict renvoyé par `/api/ask` et les sessions (`review`), enregistré en base. Dans l'interface, les problèmes du modèle sont « à vérifier », ceux du code « certains ».
- **Alternatives écartées** : variantes « un verdict par phrase » (5 passages, passages cités seuls, avec contexte), mesurées avec `scripts/probe_critic.py` sur 9 phrases du contrat : 6/9 avec 2 oublis, contre 7/9 sans oubli et 2 fausses alertes pour la consigne retenue. Les passages cités seuls divisent le temps par 2 mais laissent passer la confusion « délai de remédiation » / « préavis ».
- **Conséquences** : environ 2 à 3 s de plus par réponse en local. Les fausses alertes viennent des phrases elliptiques (« it is 60 days ») et d'une phrase presque identique à une phrase fausse voisine. Les tests d'API désactivent le contrôle par le modèle (fixture `data_dir`). À mesurer avec `gpt-oss-20b` à l'étape 12. Cas observé pour l'étape 11 : « 30 days for cause termination » (délai de remédiation présenté comme un préavis) n'a pas été signalé.

## [2026-10-22] Mise à jour de la base au démarrage : add_missing_columns
- **Contexte** : `create_all` ne modifie jamais une table existante ; les nouvelles colonnes `messages.review` et `messages.extraction` imposaient de recréer la base et de perdre l'historique.
- **Décision** : `add_missing_columns()` (`app/db/session.py`), appelée au démarrage : `ALTER TABLE ADD COLUMN` pour chaque colonne facultative déclarée par les modèles et absente de la table ; une colonne obligatoire manquante lève `SchemaUpgradeError` au lieu d'inventer une valeur.
- **Alternatives écartées** : Alembic (un outil de plus en V1) ; recréer la base à chaque changement (perte des sessions).
- **Conséquences** : les bases native et Docker ont été mises à jour sans perte. Toute autre évolution du schéma (renommage, colonne obligatoire) reste manuelle ; Alembic pourra arriver avec PostgreSQL en V2.

## [2026-10-22] Trace d'exécution des agents
- **Contexte** : l'interface doit afficher les agents intervenus, et le débogage du 3B demande de savoir quelle étape a pris du temps.
- **Décision** : `app/agents/trace.py` : `AgentRun` (nom, `kind` agent ou tool, statut `ok` / `refused` / `skipped` / `failed`, durée en ms, résumé technique) et `TraceRecorder`, avec une horloge injectable pour des durées exactes dans les tests. La trace est renvoyée par l'API et enregistrée dans `messages.agent_trace`.
- **Alternatives écartées** : journaux texte (illisibles par l'interface) ; outil d'observabilité (V2).
- **Conséquences** : les étapes non exécutées apparaissent (« skipped ») avec la raison de l'arrêt : l'interface montre qu'un refus immédiat n'a pas appelé le modèle.

## [2026-10-22] Orchestrator à règles avec plans explicites
- **Contexte** : il faut enchaîner retrieval, Writer et Critic (puis Analyst, Extractor et Critic) de façon déterministe, en gardant une place pour le replanning de la V2.
- **Décision** : `app/agents/orchestrator.py` : dataclasses `Step` et `Plan`, un plan par mode (`PLANS`), une boucle `_run` partagée. Quand une étape s'arrête (refus), les suivantes sont `skipped` avec la raison. `QuestionAnswerer` est supprimé : `app/rag/answering.py` ne garde que `AnswerResult` (avec trace et verdict), `REFUSAL_MESSAGE` et `refusal()`. `test_answering.py` devient `test_orchestrator.py`.
- **Alternatives écartées** : garder `QuestionAnswerer` à côté de l'Orchestrator (deux chemins pour la même question) ; un framework d'agents (LangGraph, CrewAI : dépendances lourdes, logique moins visible).
- **Conséquences** : en V2, le replanning modifiera la liste d'étapes après le verdict du Critic, sans changer les agents. Sur le CV : « rule-based orchestrator with explicit plans ».

## [2026-10-21] Étape 8 validée dans Docker
- **Contexte** : l'historique doit fonctionner avec le frontend compilé servi par Nginx et la base SQLite du volume Docker.
- **Décision** : aucune modification des Dockerfiles ; reconstruction avec `docker compose up -d --build`. Les tables `sessions`, `messages` et `session_documents` sont créées au démarrage par `create_all`, sans toucher aux documents déjà indexés.
- **Alternatives écartées** : aucune.
- **Conséquences** : parcours validé sur `localhost:8080` (question, fermeture de l'onglet, retour, redémarrage des conteneurs) ; la session est relue dans le volume `atlas_backend-data`. L'image `node:24-alpine` a, elle aussi, changé d'empreinte entre deux builds : la question de figer les images de base (étape 12) concerne les deux images.

## [2026-10-21] Panneau Sessions et effet de relief au survol
- **Contexte** : il faut lister les sessions, en ouvrir une et en commencer une nouvelle, dans le design « Lagon ».
- **Décision** : panneau « Sessions » en verre au-dessus du panneau « Documents », dans la même colonne et à la même largeur. Une tuile par session : titre sur une ligne, puis nombre de messages et date (« Today, 18:12 », « Yesterday », « 19 Oct », écrite avec `Intl.DateTimeFormat` et la clé `dateLocale` du dictionnaire). Session ouverte : liseré corail, comme un document coché. Nouvelle session non enregistrée : ligne « New session » en italique. Bouton « New session » discret (`button-quiet`) pour laisser « Upload a file » seul bouton turquoise. Au survol, les tuiles des sessions et des documents montent de 3 px, grossissent légèrement, prennent la teinte turquoise des questions et une ombre plus profonde (variables `--tile-hover-…` définies une seule fois) ; un document coché garde son liseré corail.
- **Alternatives écartées** : liste déroulante dans l'en-tête (moins visible pendant la démo) ; bouton « New session » turquoise (deux boutons principaux dans la même colonne).
- **Conséquences** : la liste défile au-delà d'environ trois sessions ; sur grand écran, c'est la liste des documents qui défile si elle est longue. Le français des dates viendra seul à l'étape 10 bis.

## [2026-10-21] Frontend : création différée, session courante en localStorage, verrouillage
- **Contexte** : « fermer l'onglet, revenir, tout est là » ; il ne faut ni sessions vides dans la liste, ni réponse qui arrive dans la mauvaise conversation.
- **Décision** : « New session » vide seulement l'écran ; la session est créée en base à la première question (`ensureSession`). L'identifiant de la session ouverte est gardé dans `localStorage` (`atlas.currentSessionId`), par des fonctions qui ne lèvent jamais d'erreur ; au chargement, la session est relue et restaurée. Une session disparue (404) est oubliée ; si le backend est injoignable, l'identifiant est gardé pour le rechargement suivant. Changer de session est impossible pendant une réponse, et poser une question est impossible pendant la restauration. Le panneau Source se ferme quand on change de session. Hooks : `useSessions` (nouveau), `useChat` (pose les questions avec `askInSession`, `load` restaure les messages), `useDocuments` (`select`).
- **Alternatives écartées** : ouvrir toujours la session la plus récente (une session relue avant de recharger serait remplacée) ; créer la session dès le clic (sessions vides dans la liste) ; laisser changer de session pendant une réponse (la réponse arriverait dans l'autre conversation).
- **Conséquences** : une session dont la première question a échoué (503) existe vide en base ; elle n'est pas listée et s'affiche comme une nouvelle session tant qu'elle est ouverte. Sans `localStorage` (stockage bloqué), l'application fonctionne mais ouvre une nouvelle session à chaque chargement. `askQuestion` (POST /api/ask) n'est plus utilisé par l'interface : gardé pour l'évaluation de l'étape 11. `toggleId` et `usableIds` de `lib/documents.ts` ne sont plus utilisés : à retirer au nettoyage de l'étape 13. Le comportement des hooks est vérifié par un test de bout en bout avec un faux backend et dans Safari, pas par des tests de composants (React Testing Library reste à reconsidérer à l'étape 11).

## [2026-10-21] Sélection des documents décrite, cases calculées
- **Contexte** : au chargement, la liste des documents et la session à restaurer arrivent dans un ordre imprévisible ; recocher tous les documents à l'arrivée de la liste effacerait la sélection restaurée.
- **Décision** : `useDocuments` garde une sélection `'all'` (tous les documents utilisables, y compris ceux téléversés ensuite : nouvelle session) ou un ensemble d'identifiants (choisis ou restaurés). Les cases cochées sont calculées à partir de la sélection et de la liste (`lib/selection.ts`, fonctions pures testées) ; un document supprimé ou en échec est ignoré.
- **Alternatives écartées** : un `useEffect` qui recopie la sélection à l'arrivée de la liste (fragile, signalé par la règle `react-hooks/set-state-in-effect`).
- **Conséquences** : comportement inchangé pour l'utilisatrice (tout coché au départ, téléversement coché). Une session sans document enregistré s'ouvre avec tous les documents.

## [2026-10-21] Conversation restaurée avec le même affichage qu'en direct
- **Contexte** : une réponse relue doit avoir les mêmes citations cliquables, refus et avertissements qu'une réponse reçue en direct.
- **Décision** : fonctions pures `toAskResponse` et `restoreMessages` (`lib/chat.ts`) : chaque réponse enregistrée redevient un `AskResponse` avec la question qui la précède ; messages ordonnés par `position`, identifiants `position + 1`, compteur repris au-dessus (`nextMessageId`). Action `loaded` du `chatReducer`. Le temps de réponse (`seconds`) vaut `null` pour une réponse restaurée et n'est pas affiché.
- **Alternatives écartées** : enregistrer le temps mesuré par le navigateur (une valeur du client dans la base, pour un détail d'affichage) ; afficher « 0 s » (faux).
- **Conséquences** : `ChatPanel` n'a changé que pour l'affichage du temps. Types `SessionSummary`, `SessionDetail`, `StoredMessage` et `SessionAskResponse` recopiés des schémas Pydantic dans `api/types.ts`.

## [2026-10-21] API des sessions : route dédiée, rien d'enregistré en cas de panne
- **Contexte** : une question posée dans une session doit être enregistrée avec sa réponse et ses sources ; `/api/ask` sert aussi aux tests et à l'évaluation.
- **Décision** : `GET /api/sessions` (résumés, plus récemment utilisées en premier, avec `message_count`), `POST /api/sessions` (201, session vide), `GET /api/sessions/{id}` (messages et `document_ids`), `POST /api/sessions/{id}/ask` (même corps que `/api/ask`, renvoie la question, la réponse et le résumé à jour). `/api/ask` reste sans état. Le bloc qui appelle `QuestionAnswerer` et convertit les pannes en 503 est partagé (`answer_or_503`). Session inconnue : 404, vérifiée avant tout appel au LLM. Panne (503) : rien n'est enregistré. Le titre est la première question, espaces réduits et coupée à 60 caractères sur un mot entier (`make_session_title`). Sans `document_ids`, les documents prêts à ce moment sont enregistrés. `MessageOut` reprend les champs de `AskResponse` (`citations` en `CitationOut`, mêmes `Literal`), relus et revalidés par Pydantic.
- **Alternatives écartées** : un `session_id` optionnel dans `/api/ask` (paramètre facile à oublier, route plus complexe) ; enregistrer la question sans réponse en cas de panne (question orpheline dans l'historique) ; titre généré par le LLM (5 à 30 s de plus avec le 3B, résultat incertain).
- **Conséquences** : 247 tests backend. Vérifié avec Ollama en natif (`curl`) : réponse citée, refus immédiat, session relue avec ses 4 messages. Le Critic (étape 9) s'insérera dans le plan sans changer ces routes ; `agent_trace` est déjà renvoyé (liste vide).

## [2026-10-21] Tables sessions, messages et session_documents
- **Contexte** : l'historique doit survivre au rechargement et à la ré-indexation des documents.
- **Décision** : tables conformes à `02_architecture.md`, créées par `create_all`. `sessions` : id uuid, `title` (null jusqu'à la première question), `created_at`, `updated_at`. `messages` : id uuid, `position` (ordre dans la session, unique avec `session_id`), `role`, `mode`, `content`, `sources` et `agent_trace` en JSON, plus `status`, `refusal_reason`, `invalid_citations`, `warnings` et `best_score` pour les réponses. `session_documents` : clé primaire (session, document), suppression en cascade des deux côtés. `sources` est une copie complète des citations (texte, fichier, page, score) au format de `CitationOut`. Classe `ChatSession` (et non `Session`, déjà le nom de la session SQLAlchemy). `SessionRepository.add_exchange` enregistre question, réponse, documents et titre en un seul commit ; les identifiants de documents inconnus ou en double sont ignorés. Fonction `text_enum` partagée pour stocker les énumérations en texte lisible.
- **Alternatives écartées** : `sources` en simple liste d'identifiants de chunks (une ré-indexation recrée les chunks : citations mortes) ; stocker seulement le texte final de la réponse (perte de la raison du refus, que le frontend traduira) ; ordonner par `created_at` (question et réponse ont le même horodatage).
- **Conséquences** : une citation reste lisible après une ré-indexation ou un changement de modèle d'embedding (étape 10 bis), vérifié par un test. Supprimer un document le retire des sessions sans supprimer leurs messages. Les colonnes de réponse et le champ `position` s'ajoutent au modèle de `02_architecture.md`, à mettre à jour à l'étape 13.

## [2026-10-21] Nouvelle étape « Bilingue FR/EN » après l'étape 10
- **Contexte** : l'application doit être utilisable en français et en anglais, au choix de l'utilisateur. Ce n'était pas prévu dans la vision V1.
- **Décision** : une étape dédiée, placée après l'export (étape 10) et avant l'évaluation (étape 11). Elle couvre l'interface, les messages du backend, la langue des agents, un modèle d'embedding multilingue (avec ré-indexation et nouveau calibrage du seuil), un document de démo en français et l'export. Dès l'étape 7, tous les textes de l'interface sont rangés dans un dictionnaire typé (`lib/i18n.ts`, anglais seulement) et les composants appellent `useMessages()`.
- **Alternatives écartées** : traduire seulement l'interface (l'application resterait anglophone dans ses réponses et ses erreurs) ; tout faire pendant l'étape 7 (il faudrait revenir sur chaque étape suivante) ; reporter en V2 (choix de l'utilisatrice).
- **Conséquences** : environ 3 à 5 jours de plus avant la première candidature. Placée ici, l'évaluation pourra mesurer les deux langues, et la démo, la vidéo et le README pourront montrer le changement de langue. Le choix du modèle d'embedding multilingue devra respecter les 8 Go de RAM. Sur le CV : rien tant que l'étape n'est pas faite.

## [2026-10-21] Frontend : couches lib, hooks et components
- **Contexte** : première interface React pour une débutante ; il faut un code lisible, testable et sans outil superflu.
- **Décision** : `api/` (client typé : tous les appels réseau, erreurs converties en `ApiError` avec un message lisible), `lib/` (fonctions pures testées avec Vitest), `hooks/` (état : `useDocuments`, `useChat`), `components/` (affichage). Types recopiés à la main depuis les schémas Pydantic, en snake_case. Une seule page, état géré par React seul (`useState`, `useReducer` pour la conversation), CSS simple avec variables.
- **Alternatives écartées** : `react-router` (un seul écran) ; Redux, Zustand ou React Query (inutiles à cette taille) ; génération des types depuis l'OpenAPI (un outil de plus) ; Tailwind ou une bibliothèque de composants ; tests de composants (React Testing Library, à reconsidérer à l'étape 11).
- **Conséquences** : 31 tests frontend en moins d'une seconde. Un champ ajouté à l'API doit être recopié dans `api/types.ts`. Vitest 5 (compatible avec Vite 8), lancé par `npm test`.

## [2026-10-21] Design « Lagon » : verre dépoli, turquoise et corail
- **Contexte** : l'interface doit être moderne, originale et professionnelle pour une démo devant des recruteurs. Plusieurs directions ont été comparées sur des captures (bleu vif, bleu marine, or, pastel, soleil, lagon, lagon très clair).
- **Décision** : panneaux en verre dépoli (`backdrop-filter`) avec reflet sur le bord supérieur et ombres superposées teintées de turquoise ; fond lumineux turquoise en haut à droite et corail en bas à gauche, sans formes géométriques ; turquoise profond (`#0C7C7A`) pour les actions, corail (`#FF7F66`) en petites touches, texte `#16323A`. IBM Plex Serif pour le nom, les titres et le texte issu des documents ; Manrope pour l'interface. Polices intégrées avec `@fontsource`.
- **Alternatives écartées** : Google Fonts (dépend d'un service tiers, ne marche pas hors ligne) ; les autres directions, écartées par l'utilisatrice (bleu qui tirait vers le violet, logo, cercles en arrière-plan, couleurs trop présentes ou effet verre trop faible).
- **Conséquences** : rendu identique en développement, dans Docker et en ligne. Le flou du verre demande un peu de calcul au navigateur, sans gêne sur le Mac de développement. Les polices ajoutent des fichiers à l'image, mais le navigateur ne télécharge que le sous-ensemble latin.

## [2026-10-21] Panneau des documents : sélection par cases à cocher
- **Contexte** : plusieurs documents sont indexés ; il faut pouvoir limiter une question à certains d'entre eux, comme avec `document_ids` dans l'API.
- **Décision** : une case par document prêt ; tous les documents prêts sont cochés au chargement et chaque nouveau téléversement est coché. Un document en échec n'a pas de case et affiche sa raison en rouge. Sans document coché, la question est désactivée. Les identifiants cochés sont envoyés avec chaque question.
- **Alternatives écartées** : « aucune case cochée = tous les documents » (deux sens pour le même état, source de confusion).
- **Conséquences** : la sélection est perdue au rechargement de la page jusqu'à l'étape 8, où chaque session aura ses documents (`session_documents`).

## [2026-10-21] Chat : une question à la fois, refus affichés par le frontend
- **Contexte** : le modèle local met 5 à 30 secondes par réponse, et les deux types de refus doivent être compréhensibles en démo.
- **Décision** : la conversation est gérée par un reducer pur (`chatReducer`) ; une seule question à la fois (bouton désactivé pendant la génération) ; attente visible (trois points animés et message) ; temps de réponse mesuré par le navigateur et affiché ; message de refus écrit par le frontend à partir de `refusal_reason`, avec une phrase différente pour le seuil et pour `NOT_FOUND` ; avertissements dans un encadré discret.
- **Alternatives écartées** : streaming de la réponse (plus complexe, hors périmètre V1) ; afficher le texte de refus du backend (il deviendra traduisible côté frontend).
- **Conséquences** : en local, 0,1 s pour un refus par le seuil, 1 à 2 s pour un refus par le modèle, environ 6 s pour une réponse citée. La conversation n'est pas conservée au rechargement (étape 8).

## [2026-10-21] Citations cliquables, découpées côté frontend
- **Contexte** : chaque citation `[fichier, p. X]` doit ouvrir le passage exact sur lequel repose la réponse.
- **Décision** : fonction pure `splitAnswer` qui découpe la réponse sur les textes exacts de `citation.display` (marqueurs les plus longs d'abord, caractères spéciaux échappés) et regroupe les passages d'une même page sous un seul marqueur. Chaque marqueur devient une pastille cliquable ; un panneau Source affiche le fichier, la page, le texte de chaque passage et son score de similarité. Fermeture par le bouton ou la touche Échap ; le focus clavier passe sur le panneau. Troisième colonne sur grand écran, panneau flottant sous 1100 px.
- **Alternatives écartées** : réponse renvoyée en morceaux structurés par le backend (changement d'une API qui fonctionne) ; affichage de la page entière ou du PDF d'origine (bibliothèque lourde, hors périmètre V1).
- **Conséquences** : aucun changement côté backend, aucune requête supplémentaire. Le format de `display` est désormais un contrat entre le backend et le frontend.

## [2026-10-21] Texte des passages rendu lisible à l'affichage seulement
- **Contexte** : le texte extrait des PDF garde les retours à la ligne de la page imprimée, souvent au milieu d'une phrase.
- **Décision** : fonction pure `readableText` qui joint les lignes coupées et ne garde que les retours après `.`, `!`, `?` ou `:`, ainsi que les lignes vides.
- **Alternatives écartées** : nettoyer le texte à l'ingestion (changerait les chunks, les embeddings et le texte envoyé au modèle, donc imposerait une ré-indexation et un nouveau calibrage).
- **Conséquences** : seul l'affichage change. Un titre sans ponctuation finale est joint à la ligne suivante.

## [2026-10-21] Frontend validé dans Docker
- **Contexte** : l'interface doit fonctionner compilée et servie par Nginx, comme en production.
- **Décision** : aucune modification des Dockerfiles ni de la configuration Nginx ; reconstruction avec `docker compose up -d --build`.
- **Alternatives écartées** : aucune.
- **Conséquences** : parcours complet validé sur `localhost:8080` (question, réponse citée, panneau Source, polices intégrées). L'image `python:3.13-slim` a de nouveau changé d'empreinte entre deux builds du même jour, ce qui a reconstruit le backend sans changement de code : à prendre en compte dans la décision de l'étape 12 sur le fait de figer l'image de base.

## [2026-10-21] Image de base Docker non figée, à examiner à l'étape 12
- **Contexte** : le build du backend a pris 7 minutes au lieu de quelques secondes, alors que `requirements.txt` n'avait pas changé : l'image `python:3.13-slim` avait été mise à jour par ses mainteneurs, ce qui invalide tout le cache (Tesseract, puis `pip install`).
- **Décision** : ne rien changer en V1.
- **Alternatives écartées** : figer l'image par son empreinte (`python:3.13-slim@sha256:...`) dès maintenant (builds reproductibles, mais plus de correctifs de sécurité automatiques : c'est une question de déploiement).
- **Conséquences** : un build complet reste possible de temps en temps. La question sera tranchée à l'étape 12, avec le Docker de production.

## [2026-10-21] Seuil de pertinence calibré à 0,60 sur le contrat de démo
- **Contexte** : le refus sans appel au LLM dépend d'un seuil sur le score de similarité ; il devait être calibré sur un vrai document de démo (voir l'entrée du 2026-10-20).
- **Décision** : `RETRIEVAL_MIN_SCORE = 0.6`. Seuls les passages au-dessus du seuil sont envoyés au Writer. Mesures avec `nomic-embed-text` sur 18 questions (script `python -m scripts.probe_scores`) : les passages qui répondent à une question obtiennent 0,645 ou plus ; les questions hors sujet 0,454 à 0,541 ; les questions absentes mais proches du sujet 0,613 à 0,638.
- **Alternatives écartées** : 0,65 (refuserait toutes les questions absentes, mais supprimerait le passage qui répond sur les signataires, à 0,645) ; 0,50 (presque tout irait jusqu'au LLM : plus lent et plus de risque d'invention).
- **Conséquences** : les questions hors sujet sont refusées immédiatement (scénario 2 : salaire du CEO, 0,540). Les questions proches du sujet passent le seuil et sont refusées par le modèle (`NOT_FOUND`), vérifié avec `qwen2.5:3b`. Le seuil dépend du modèle d'embedding : à recalibrer à l'étape 12 avec le fournisseur d'embeddings en ligne, et après l'ajout des autres documents de démo. Le script et ses questions serviront de base à l'étape 11.

## [2026-10-21] Contrat de démo fictif : service_agreement.pdf
- **Contexte** : calibrer le seuil et tester le Writer sur des documents de trois phrases n'est pas représentatif.
- **Décision** : contrat de services fictif en anglais (Helix Data Services Ltd. / Orion Freight Co.), PDF texte de 6 pages, un article par page, dans `demo_documents/`. La page 4 contient plusieurs délais (60, 30 et 90 jours) ; le nom du CEO figure page 6, mais aucun salaire.
- **Alternatives écartées** : créer les trois documents de démo maintenant (la facture scannée et la revue PPTX serviront aux étapes 9 et 10).
- **Conséquences** : chaque réponse a une page source unique et vérifiable. Scénarios 1 et 2 validés en natif et dans Docker. Le document de test `test_document.docx` concurrence le contrat dans l'index natif : les tests de bout en bout limitent la question au contrat (`document_ids`).

## [2026-10-21] POST /api/ask : un refus est une réponse normale
- **Contexte** : le frontend doit distinguer « l'information est absente » de « le service est en panne ».
- **Décision** : `POST /api/ask` (`question`, `top_k`, `document_ids`) renvoie toujours 200 avec `status` (`answered` / `refused`), `refusal_reason` (`no_relevant_passages` / `not_found_by_model`), `answer`, `citations` (passage complet : chunk, document, page, texte, score), `invalid_citations`, `warnings` et `best_score`. Erreur 503 si l'embedding ou le LLM est injoignable, ou si la réponse ne contient que des citations inventées. Le message de refus est une constante du code.
- **Alternatives écartées** : refuser une réponse sans citation valide (bloquerait des réponses correctes mal formatées par le 3B ; elle est renvoyée avec l'avertissement `no_valid_citation`) ; une erreur 404 pour un refus (un refus n'est pas une erreur).
- **Conséquences** : le frontend dispose de tout pour rendre les sources cliquables (étape 7). `best_score` aide au calibrage et au débogage.

## [2026-10-21] Service QuestionAnswerer dans app/rag, sans Orchestrator
- **Contexte** : l'Orchestrator n'arrive qu'à l'étape 9, mais l'étape 6 doit répondre à une question de bout en bout.
- **Décision** : classe `QuestionAnswerer` (retriever, seuil, Writer, vérification des citations) dans un nouveau dossier `app/rag/`, avec le module de citations. Dépendance `get_question_answerer` construite à chaque requête à partir d'objets créés au démarrage.
- **Alternatives écartées** : un Orchestrator dès maintenant (étape 9) ; tout mettre dans la route (impossible à réutiliser et à tester sans HTTP).
- **Conséquences** : le plan `ask` de l'Orchestrator réutilisera ces briques sans réécriture. Dossier `app/rag/` absent de la structure de `02_architecture.md`, à mettre à jour à l'étape 13.

## [2026-10-21] Writer : passages anonymes et mot-clé NOT_FOUND
- **Contexte** : un modèle de 3B recopie mal les sources et invente quand l'information manque.
- **Décision** : le Writer reçoit les passages sous la seule forme `[S1]` + texte, sans nom de fichier ni numéro de page. Prompt court en anglais : réponse uniquement depuis les passages, citation `[Sx]` après chaque phrase, réponse exacte `NOT_FOUND` si l'information est absente. Température 0. La détection du refus tolère les variantes (`**NOT_FOUND**`, `Not found.`) mais ignore « not found » au milieu d'une phrase et toute réponse qui contient des citations. Une réponse vide du modèle est une erreur, pas un refus.
- **Alternatives écartées** : détecter une phrase de refus libre (« I couldn't find… »), peu fiable ; afficher le texte de refus du modèle.
- **Conséquences** : le modèle ne peut pas inventer une source. Il ne peut pas non plus répondre à « quelle page parle de… ? » (hors scénarios V1). Avec `qwen2.5:3b`, la réponse au scénario 1 est juste et bien citée, mais contient une redite et confond délai de remédiation et préavis : cas laissé au Critic (étape 9) plutôt que d'ajuster le prompt sur une seule question, et à garder pour le jeu d'évaluation de l'étape 11.

## [2026-10-21] Citations vérifiées par le code
- **Contexte** : le backend doit vérifier chaque identifiant cité avant de le convertir en `[NomDocument, p. X]`.
- **Décision** : module `app/rag/citations.py` (fonctions pures). La numérotation S1…Sn est définie à un seul endroit (`number_passages`), partagée avec le Writer. Variantes comprises : `[S1, S3]`, `[s2]`, `[S1][S2]`, `[S01]`, `[S1; S4]`. Seuls les marqueurs entre crochets commençant par `S` sont reconnus (`[Note]` et `[1]` restent intacts). Les identifiants inventés sont retirés du texte et listés. Deux passages de la même page s'affichent une seule fois, mais restent tous deux dans la liste des sources. Le nom de fichier complet est affiché (`contract.pdf`).
- **Alternatives écartées** : reconnaître `S1` sans crochets (faux positifs dans le texte).
- **Conséquences** : l'utilisateur ne voit jamais de lien mort ; les citations inventées restent traçables pour le Critic.

## [2026-10-21] LLM créé au démarrage, faux LLM injectable dans les tests
- **Contexte** : les routes ont besoin du LLM, et les tests ne doivent pas dépendre d'Ollama.
- **Décision** : `build_llm_provider` est appelé au démarrage (`app.state.llm`), sans contacter le serveur ; dépendance `get_llm_provider`. Dans `conftest.py`, `FakeLLMProvider` renvoie des réponses programmées, enregistre chaque appel (messages, température, mode JSON), peut simuler une panne et fait échouer le test s'il est appelé sans réponse prévue. La fixture `client` l'injecte par `dependency_overrides`.
- **Alternatives écartées** : `unittest.mock` (accepte n'importe quel appel, moins lisible).
- **Conséquences** : le serveur démarre même si Ollama est arrêté. Les tests peuvent vérifier le prompt et l'absence d'appel au LLM lors d'un refus. 207 tests passent sans réseau.

## [2026-10-20] Image backend : 1,06 Go avec Chroma, accepté pour l'instant
- **Contexte** : l'ajout de `chromadb` fait passer l'image backend de 491 Mo à 1,06 Go sur le disque (de 118 à 233 Mo compressés). Le cache de pip est déjà désactivé (`PIP_NO_CACHE_DIR=1`) : la hausse vient uniquement des dépendances de Chroma (`onnxruntime`, `grpcio`, `kubernetes`, etc.).
- **Décision** : accepter cette taille en V1. La RAM, vraie contrainte de la machine, n'est pas touchée (environ 120 Mo pour Chroma).
- **Alternatives écartées** : installer Chroma sans ses dépendances (fragile, casse à la moindre mise à jour) ; changer de base vectorielle dès maintenant (voir l'entrée sur Chroma 1.5.9).
- **Conséquences** : un premier build télécharge environ 100 Mo (11 minutes avec une connexion lente). La taille sera réexaminée à l'étape 12, selon les limites de la plateforme de déploiement choisie.

## [2026-10-20] Scripts de maintenance copiés dans l'image backend
- **Contexte** : le `Dockerfile` ne copiait que `app/`, donc `python -m scripts.reindex` échouait dans le conteneur (`No module named 'scripts'`).
- **Décision** : ajout de `COPY scripts ./scripts`, après l'installation des dépendances pour garder le cache.
- **Alternatives écartées** : lancer les scripts depuis le Mac sur les données Docker (le volume n'est pas accessible directement).
- **Conséquences** : la ré-indexation est possible dans Docker et le sera en production, avec `docker compose run --rm backend python -m scripts.reindex` (backend arrêté pendant l'opération).

## [2026-10-20] Docker : backend relié à Ollama natif via host.docker.internal
- **Contexte** : dans un conteneur, `127.0.0.1` désigne le conteneur lui-même, pas le Mac où tourne Ollama.
- **Décision** : `LLM_BASE_URL` et `EMBEDDING_BASE_URL` valent `http://host.docker.internal:11434` dans `docker-compose.yml`, avec `extra_hosts: host.docker.internal:host-gateway`.
- **Alternatives écartées** : Ollama dans Docker (sans GPU Metal, voir l'entrée du 2026-10-18).
- **Conséquences** : `extra_hosts` ne change rien sur Mac et rend la configuration valable sous Linux. Validé : les 3 documents du volume ont été ré-indexés depuis le conteneur, et une recherche via `localhost:8080` renvoie la bonne page.

## [2026-10-20] Seuil de pertinence : pas fixé à l'étape 5, premières mesures notées
- **Contexte** : le refus sans appel au LLM dépend d'un seuil sur le score (similarité cosinus).
- **Décision** : l'endpoint de recherche renvoie le score sans filtrer. Le seuil sera calibré à l'étape 6 sur les documents de démo.
- **Alternatives écartées** : fixer un seuil dès maintenant sur des documents de test de trois phrases (non représentatif).
- **Conséquences** : premières mesures avec `nomic-embed-text`. Sur un DOCX court : 0,81 pour la bonne page, environ 0,50 pour les autres, 0,47 pour une information absente. Sur la facture scannée : 0,67 pour la bonne page, mais 0,62 et 0,59 pour des passages hors sujet. Les chunks longs ont des scores plus bas : un seuil fixe sera délicat, le Writer et le Critic restent des garde-fous nécessaires.

## [2026-10-20] Recherche : Retriever et POST /api/search
- **Contexte** : il faut une requête qui renvoie les bons passages avec leur source (fin de l'étape 5), et le futur Writer en aura besoin.
- **Décision** : classe `Retriever` (outil déterministe, pas un agent) : embedding de la question avec le préfixe de requête, recherche dans Chroma, puis lecture du texte et du nom de fichier en SQLite. Un vecteur sans chunk en SQLite est ignoré. Endpoint `POST /api/search` : `query` (1 à 1000 caractères), `top_k` (1 à 20, défaut `RETRIEVAL_TOP_K = 5`), `document_ids` optionnel. Réponse `{query, results}`. Erreur 503 si le service d'embedding ne répond pas.
- **Alternatives écartées** : renvoyer le texte stocké dans Chroma (SQLite est la source de vérité) ; une erreur 500 générique (laisserait croire à un bug).
- **Conséquences** : le retriever partage l'embedder et le vector store de l'indexeur (dépendance `get_retriever` construite à partir de `get_indexer`) : même modèle, mêmes préfixes, même index. La réponse sous forme d'objet pourra recevoir de nouveaux champs à l'étape 6 sans casser le frontend.

## [2026-10-20] Script de ré-indexation depuis SQLite
- **Contexte** : les documents téléversés avant l'étape 5 n'avaient pas d'index, et tout changement de modèle, de préfixes ou de taille de chunks impose de ré-indexer.
- **Décision** : `python -m scripts.reindex` traite tous les documents `ready` à partir des pages déjà en SQLite (sans nouvel OCR), continue en cas d'échec et renvoie un code d'erreur s'il y en a eu un. Le serveur doit être arrêté pendant l'opération (Chroma embarqué n'est pas prévu pour deux programmes en même temps).
- **Alternatives écartées** : un endpoint d'API (inutile en V1, et risque d'écritures concurrentes dans Chroma).
- **Conséquences** : script idempotent ; si le service d'embedding est indisponible, l'index existant reste intact.

## [2026-10-20] Indexation synchrone pendant l'upload, nettoyage en cas d'échec
- **Contexte** : un document doit être cherchable dès qu'il est affiché comme prêt.
- **Décision** : classe `DocumentIndexer` (chunking, embeddings, Chroma), appelée par l'upload et par le script de ré-indexation. Ordre : parsing, indexation, puis `mark_ready` : le document reste en `processing` jusqu'à la fin. Les vecteurs sont calculés avant toute écriture. En cas d'échec : `rollback`, suppression des vecteurs, puis `mark_failed` (pages et chunks supprimés, raison enregistrée, par exemple « Indexing failed: ... »). L'indexeur est créé au démarrage, sans appel au service d'embedding.
- **Alternatives écartées** : garder le document en `ready` sans index (affiché comme utilisable alors qu'aucune recherche ne le trouverait) ; indexation en tâche de fond (V2).
- **Conséquences** : un upload nécessite qu'Ollama tourne (ou l'API externe en ligne) ; le serveur démarre même sans lui. Un vecteur orphelin laissé par un échec de Chroma est sans danger : la recherche relit toujours SQLite.

## [2026-10-20] Tests : faux modèle d'embedding injecté par dependency_overrides
- **Contexte** : après l'étape 5, chaque upload appelle le modèle d'embedding ; les tests ne doivent dépendre ni d'Ollama ni du réseau.
- **Décision** : dans `conftest.py`, un provider factice répartit les mots dans 64 dimensions (textes proches, vecteurs proches) ; la fixture `client` remplace `get_indexer` par un indexeur qui l'utilise, sur un Chroma temporaire. Un second provider simule un service d'embedding indisponible.
- **Alternatives écartées** : appeler le vrai Ollama dans les tests (lent, dépend de la machine) ; simuler Chroma (on teste alors une imitation, pas le vrai comportement).
- **Conséquences** : 151 tests passent en quelques secondes, sans réseau ; Chroma est testé pour de vrai. La vérification avec les vrais modèles se fait à la main (`curl` sur `/api/search`).

## [2026-10-20] Préfixes de tâche de nomic-embed-text dans la couche retrieval
- **Contexte** : `nomic-embed-text` est entraîné avec un préfixe différent pour les passages (`search_document: `) et pour les questions (`search_query: `) ; sans eux, le retrieval est moins bon.
- **Décision** : classe `Embedder` au-dessus de l'`EmbeddingProvider` existant : ajoute les préfixes et envoie les textes par lots (`EMBEDDING_BATCH_SIZE = 32`). Préfixes configurables (`EMBEDDING_DOCUMENT_PREFIX`, `EMBEDDING_QUERY_PREFIX`), ceux de nomic par défaut ; à mettre à `""` pour un modèle sans préfixe.
- **Alternatives écartées** : préfixes dans chaque provider (ils dépendent du modèle, pas du fournisseur) ; détection automatique d'après le nom du modèle (magique et fragile).
- **Conséquences** : les providers restent génériques. Changer les préfixes ou le modèle impose de ré-indexer tous les documents.

## [2026-10-20] Chroma 1.5.9, une collection par modèle d'embedding
- **Contexte** : il faut stocker et interroger les vecteurs ; Chroma ajoute environ 360 Mo de dépendances sur le disque.
- **Décision** : `chromadb==1.5.9` épinglé, derrière une interface `VectorStore` (`upsert`, `query`, `delete_document`, `count`). Une collection par modèle d'embedding, en distance cosinus ; le nom exact du modèle est enregistré dans la collection et vérifié à chaque ouverture. Seuls les vecteurs et `document_id`, `page_number`, `position` sont stockés. Télémétrie désactivée. Score renvoyé : 1 − distance cosinus.
- **Alternatives écartées** : `sqlite-vec`, très léger, mais il aurait fallu revenir sur une décision prise et recoder le filtrage et la persistance.
- **Conséquences** : environ 120 Mo de RAM. Les erreurs de Chroma sont traduites en `VectorStoreError`, donc le passage à Qdrant en V2 ne touchera pas le code appelant. Seul `chromadb` est épinglé, pas ses dépendances.

## [2026-10-20] Table chunks, identifiants uuid, tables créées par create_all
- **Contexte** : le texte des chunks doit être en SQLite (source de vérité), sous le même identifiant que dans Chroma.
- **Décision** : table `chunks` (id uuid en texte, `document_id`, `page_number`, `position`, `text`, `created_at`), unicité sur `(document_id, page_number, position)`, suppression en cascade avec le document. Les ids sont générés avant l'enregistrement. Les tables sont créées par `create_all`, sans outil de migration.
- **Alternatives écartées** : id entier auto-incrémenté (inconnu avant l'écriture en base) ; Alembic (un outil de plus à apprendre en V1).
- **Conséquences** : la nouvelle table apparaît d'elle-même dans une base existante. `create_all` ne modifie jamais une table existante : changer ses colonnes impose de recréer la base (`docker compose down -v` dans Docker). Le champ s'appelle `page_number`, comme dans la table `pages` (et non `page` comme dans `02_architecture.md`).

## [2026-10-20] Chunker maison, en caractères
- **Contexte** : chaque chunk doit pointer vers une page exacte.
- **Décision** : fonction pure `chunk_pages`, page par page (un chunk ne chevauche jamais deux pages). Taille ~1000 caractères, chevauchement ~150 (`CHUNK_SIZE`, `CHUNK_OVERLAP`). Coupure de préférence sur paragraphe, ligne, phrase, puis mot, dans la seconde moitié de la fenêtre ; le chunk suivant commence au début d'un mot.
- **Alternatives écartées** : `RecursiveCharacterTextSplitter` de LangChain (grosse dépendance pour une seule fonction) ; taille en tokens (dépendance au tokenizer, inutile ici).
- **Conséquences** : 1000 caractères font environ 250 tokens, très en dessous de la limite du modèle. Un mot de plus de 500 caractères (OCR raté) est coupé.

## [2026-10-20] Nginx : limite d'upload à 21 Mo, délais de 300 s
- **Contexte** : Nginx limite par défaut le corps d'une requête à 1 Mo et attend la réponse du backend 60 s au maximum. Un scan de quelques pages dépasse 1 Mo, et l'OCR synchrone peut dépasser 60 s.
- **Décision** : dans `location /api/` uniquement, `client_max_body_size 21m`, `proxy_read_timeout 300s` et `proxy_send_timeout 300s`. La limite Nginx est volontairement juste au-dessus de celle du backend (`MAX_UPLOAD_MB = 20`), car l'encodage `multipart` ajoute quelques octets au fichier.
- **Alternatives écartées** : limite identique de 20 Mo (un fichier proche de la limite serait refusé par Nginx avec une page HTML 413, au lieu du message JSON du backend) ; réglages sur tout le `server` (inutiles pour les fichiers statiques).
- **Conséquences** : le backend reste la seule source de la règle de taille ; Nginx sert de filet de sécurité. Le délai de 300 s couvre une ingestion normale (au maximum 10 pages en OCR) ; l'ingestion asynchrone est prévue en V2. Validé avec un PDF scanné de 1,36 Mo via `localhost:8080`.

## [2026-10-20] Volume Docker nommé pour `data/`
- **Contexte** : la base SQLite et les fichiers téléversés sont écrits dans le conteneur et disparaîtraient à sa suppression.
- **Décision** : volume nommé `backend-data` (créé sous le nom `atlas_backend-data`) monté sur `/app/data`, et `DATA_DIR=/app/data` défini explicitement dans `docker-compose.yml`. Le dossier existe dans l'image et appartient à l'utilisateur `atlas`, donc le volume hérite de ces droits à sa création.
- **Alternatives écartées** : bind mount vers un dossier du Mac (problèmes de droits avec l'utilisateur non root, mélange avec les données du développement natif) ; aucun volume (données perdues à chaque `docker compose down`).
- **Conséquences** : les données survivent à `docker compose down` et aux reconstructions (vérifié). `docker compose down -v` remet tout à zéro. En production, l'application ne dépend toujours pas d'un disque persistant (documents de démo indexés au démarrage).

## [2026-10-20] Tesseract dans l'image backend, sans Poppler
- **Contexte** : l'OCR doit fonctionner dans Docker comme en natif.
- **Décision** : installation par `apt-get` de `tesseract-ocr` et `tesseract-ocr-eng` (nommé explicitement), avec `--no-install-recommends` et suppression des listes apt, dans une couche placée avant `pip install` pour profiter du cache. Aucune autre bibliothèque système : `pypdfium2` embarque son propre moteur PDF pour rasteriser les pages.
- **Alternatives écartées** : `pdf2image`, qui impose `poppler-utils` dans l'image ; une image de base avec Tesseract préinstallé (moins maîtrisée, plus lourde).
- **Conséquences** : Tesseract 5 disponible dans le conteneur avec les langues `eng` et `osd` (vérifié avec `tesseract --list-langs`). Les reconstructions où seul le code change restent rapides.

## [2026-10-20] Ingestion : limites de taille et documents en échec conservés
- **Contexte** : le traitement est synchrone en V1 ; un fichier trop gros ou un long scan bloquerait la requête.
- **Décision** : limites configurables dans `Settings` : `max_upload_mb = 20`, `max_pages = 50`, `max_ocr_pages = 10`, et délai OCR par appel (`ocr_timeout_seconds = 60`). Un fichier trop gros est refusé avec une erreur 413. Un fichier illisible est quand même enregistré, avec le statut `failed` et la raison dans `error`.
- **Alternatives écartées** : aucune limite (risque de blocage du serveur) ; ignorer les fichiers en échec (l'utilisateur ne saurait pas pourquoi son document n'apparaît pas).
- **Conséquences** : comportement prévisible pendant une démo. Les limites pourront être relevées en V2 avec l'ingestion asynchrone.

## [2026-10-20] PDF : pypdfium2 pour le texte et la rasterisation
- **Contexte** : il faut extraire le texte des PDF page par page et, pour les pages scannées, les convertir en image pour Tesseract.
- **Décision** : `pypdfium2`, qui fait les deux avec une seule bibliothèque et embarque le moteur PDFium (celui de Chrome), sans dépendance système.
- **Alternatives écartées** : `pdf2image` (dépend de Poppler, à installer dans l'image) ; PyMuPDF (licence AGPL, contraignante).
- **Conséquences** : image Docker plus légère et installation identique sur le Mac et dans le conteneur.

## [2026-10-19] Modèle Groq pour la démo : openai/gpt-oss-20b
- **Contexte** : `llama-3.3-70b-versatile` n'est plus proposé par Groq (erreur 404 `model_not_found`). La liste des modèles a été obtenue via l'endpoint `/models`.
- **Décision** : `openai/gpt-oss-20b`, testé avec succès (réponse en environ 1 s).
- **Alternatives écartées** : `openai/gpt-oss-120b` (solution de repli si la qualité ne suffit pas) ; `qwen/qwen3.8-27b` (comportement non vérifié).
- **Conséquences** : le catalogue de Groq change souvent ; le modèle est une simple variable d'environnement, à revérifier avant la démo (étape 12).

## [2026-10-19] Embeddings de la démo : provider générique, fournisseur choisi à l'étape 12
- **Contexte** : Groq ne propose pas d'embeddings ; il faut un fournisseur séparé pour la démo en ligne.
- **Décision** : `OpenAICompatibleEmbeddingProvider` (endpoint standard `/embeddings`), testé dès maintenant contre l'endpoint `/v1` d'Ollama. Le fournisseur réel sera choisi à l'étape 12.
- **Alternatives écartées** : choisir maintenant un fournisseur dont les conditions peuvent changer d'ici le déploiement.
- **Conséquences** : génération et embeddings se configurent indépendamment ; changer de fournisseur revient à changer trois variables.

## [2026-10-19] Client HTTP : httpx2
- **Contexte** : le backend doit appeler Ollama et les API distantes en production.
- **Décision** : `httpx2` (successeur de `httpx`, même auteur, recommandé par Starlette), passé dans `requirements.txt`.
- **Alternatives écartées** : `requests` (synchrone uniquement, bibliothèque de plus pour simuler les réponses) ; SDK `openai` (lourd, ramène l'ancien `httpx`).
- **Conséquences** : `MockTransport` permet de tester les providers sans réseau ; l'asynchrone reste possible pour la V2.

## [2026-10-19] Configuration : pydantic-settings, secrets hors de Git
- **Contexte** : la configuration doit changer entre le local et la démo, sans toucher au code, et les clés ne doivent jamais être publiées.
- **Décision** : classe `Settings` validée (`Literal` pour les providers, `SecretStr` pour les clés) ; `.env` ignoré par Git, `.env.example` publié ; règle `.claude/settings.json` interdisant à Claude Code de lire `.env`. Une clé vide est traitée comme absente.
- **Alternatives écartées** : lecture directe de `os.environ` (aucune validation, erreurs découvertes trop tard).
- **Conséquences** : une faute de frappe dans la configuration bloque le démarrage avec un message clair ; les clés n'apparaissent pas dans les journaux.

## [2026-10-19] Providers testés sans réseau, plus un script de vérification réelle
- **Contexte** : les tests doivent rester rapides et fiables, mais il faut aussi prouver le fonctionnement avec de vrais modèles.
- **Décision** : tests pytest avec `httpx2.MockTransport` (requêtes, réponses et erreurs simulées) ; script `scripts/check_providers.py` lancé à la main contre Ollama et Groq. Les messages d'erreur incluent la raison donnée par le serveur.
- **Alternatives écartées** : tests appelant les vraies API (lents, dépendants du réseau et du quota).
- **Conséquences** : 24 tests en moins d'une seconde ; le script valide une configuration réelle avant une démo.

## [2026-10-18] Docker Compose : Nginx seule porte d'entrée, port 8080
- **Contexte** : il faut lancer backend et frontend ensemble, comme en production.
- **Décision** : deux services Compose. Seul le frontend (Nginx) publie un port sur la machine (`8080:80`) ; le backend n'est joignable que par le réseau interne, via `http://backend:8000`. Ollama reste hors de Compose.
- **Alternatives écartées** : publier aussi le port du backend (deux portes d'entrée, moins sûr) ; port 80 (droits et conflits possibles sur Mac).
- **Conséquences** : même architecture qu'en production. Pour appeler l'API directement en local, on passe par `localhost:8080/api/...` ou par le serveur de développement.

## [2026-10-18] Image frontend en deux étapes (Node puis Nginx)
- **Contexte** : en production, une application React n'est qu'un ensemble de fichiers statiques.
- **Décision** : construction avec `node:24-alpine` (LTS, `npm ci`), puis service par `nginx:stable-alpine`, qui fait aussi le proxy `/api` vers le backend (équivalent du proxy Vite).
- **Alternatives écartées** : servir le frontend avec Node ou le serveur Vite (image de plus de 500 Mo, outil de développement en production).
- **Conséquences** : image finale légère, indépendante de la version de Node installée localement (25, non LTS).

## [2026-10-18] Image backend : python:3.13-slim, utilisateur sans privilèges
- **Contexte** : l'image du backend doit être légère, reproductible et sûre.
- **Décision** : base `python:3.13-slim` (même version qu'en local), dépendances de production uniquement, `requirements.txt` copié avant le code pour profiter du cache, exécution sous un utilisateur `atlas` non root, `.dockerignore` excluant `.venv`, tests et secrets.
- **Alternatives écartées** : image `python:3.13` complète (environ 1 Go) ; exécution en root (risque inutile).
- **Conséquences** : reconstruction en quelques secondes quand seul le code change. Tesseract sera ajouté à l'image à l'étape 4.

## [2026-10-18] Tests : httpx2 à la place de httpx
- **Contexte** : Starlette (base de FastAPI) signale que l'usage de `httpx` par son `TestClient` est déprécié et recommande `httpx2`.
- **Décision** : `httpx2` dans `requirements-dev.txt`, `httpx` retiré après vérification que le test passe sans lui.
- **Alternatives écartées** : ignorer l'avertissement (risque de casse lors d'une future mise à jour).
- **Conséquences** : suite de tests sans avertissement.

## [2026-10-18] Frontend : appels relatifs `/api`, sans CORS
- **Contexte** : le frontend doit appeler le backend en développement, dans Docker et en ligne.
- **Décision** : le frontend appelle toujours `/api/...` sur sa propre adresse. En développement, le proxy de Vite redirige vers le backend ; dans Docker, c'est Nginx.
- **Alternatives écartées** : adresse du backend écrite dans le code et configuration CORS (plus de configuration, sources d'erreurs entre environnements).
- **Conséquences** : le même code fonctionne partout. Le déploiement en conteneur unique (FastAPI servant le frontend compilé) reste possible.

## [2026-10-18] Environnement Python : venv + pip + requirements.txt
- **Contexte** : il faut isoler les dépendances du backend ; débutante en Python.
- **Décision** : `venv` et `pip`, fournis avec Python, et un fichier `requirements.txt`.
- **Alternatives écartées** : Poetry et uv (plus modernes, mais un outil de plus à apprendre).
- **Conséquences** : installation standard, documentée partout, simple à reproduire dans Docker.

## [2026-10-18] Plateforme de déploiement : décision reportée à l'étape 12
- **Contexte** : la documentation de Hugging Face indique désormais qu'un Space Docker ou Gradio demande un abonnement payant ; Railway fonctionne avec des crédits limités. Les offres changent souvent.
- **Décision** : ne pas choisir maintenant. Contrainte retenue dès aujourd'hui : une image Docker légère, sans modèle local en production, et aucune dépendance à un disque persistant (documents de démo indexés au démarrage).
- **Alternatives écartées** : choisir maintenant, au risque que les conditions aient changé d'ici l'étape 12.
- **Conséquences** : l'application reste déployable sur une offre gratuite ou peu chère, quelle qu'elle soit.

## [2026-10-18] LLM externe pour la démo : API compatible OpenAI, Groq par défaut
- **Contexte** : la démo en ligne ne peut pas faire tourner un LLM local de qualité.
- **Décision** : un provider générique `OpenAICompatibleProvider` (URL, clé et modèle configurables), utilisé avec Groq par défaut : offre gratuite sans carte bancaire, limitée en débit, très rapide.
- **Alternatives écartées** : Google AI Studio (Gemini), offre gratuite intéressante mais API différente, gardée en solution de repli ; OpenRouter, possible avec le même provider ; OpenAI et Anthropic, payants dès le départ.
- **Conséquences** : changer de fournisseur revient à changer trois variables d'environnement. Les limites de débit gratuites suffisent pour une démo, pas pour un usage intensif.

## [2026-10-18] Orchestrator à règles, mode choisi par l'utilisateur
- **Contexte** : un modèle de 3B classe mal les intentions ; un routage par LLM rendrait la démo imprévisible.
- **Décision** : l'utilisateur choisit le mode (`ask` ou `extract`) dans l'interface. L'Orchestrator applique un plan fixe par mode et le produit sous forme de liste d'étapes explicite.
- **Alternatives écartées** : classification de l'intention par le LLM (peu fiable en local) ; replanning dynamique (V2).
- **Conséquences** : comportement déterministe et facile à tester. En V2, le replanning modifiera la liste d'étapes sans toucher aux agents. Sur le CV : « rule-based orchestrator ».

## [2026-10-18] Retrieval traité comme un outil, pas comme un agent
- **Contexte** : le schéma de la vision place le retrieval avant le Writer.
- **Décision** : le retrieval est un outil déterministe appelé par l'Orchestrator. Les 5 agents restent ceux de la vision.
- **Alternatives écartées** : un sixième agent « Retriever », qui ne prendrait aucune décision.
- **Conséquences** : architecture plus honnête et plus simple à expliquer en entretien.

## [2026-10-18] Citations par identifiants de passages
- **Contexte** : un petit modèle recopie mal les noms de documents et les numéros de page, ou les invente.
- **Décision** : le Writer reçoit des passages numérotés `[S1]…[Sn]` et ne cite que ces identifiants. Le backend vérifie leur existence et les convertit en `[NomDocument, p. X]`.
- **Alternatives écartées** : laisser le LLM écrire directement `[Document, p. X]`.
- **Conséquences** : une citation inventée devient détectable par le code. Le Critic signale ces cas.

## [2026-10-18] Chunking par page
- **Contexte** : chaque citation doit pointer vers une page exacte.
- **Décision** : un chunk ne chevauche jamais deux pages. Valeurs de départ : ~1000 caractères, chevauchement de ~150, top-k = 5. Calibrage à l'étape 6.
- **Alternatives écartées** : chunking sur le texte continu du document (meilleur contexte, mais citations ambiguës).
- **Conséquences** : une phrase coupée en fin de page peut perdre du contexte. Compromis accepté pour la vérifiabilité.

## [2026-10-18] SQLite source de vérité, Chroma index reconstructible
- **Contexte** : il faut afficher le passage source et pouvoir changer de modèle d'embedding.
- **Décision** : le texte des chunks est stocké en SQLite. Chroma ne contient que les vecteurs et les métadonnées, sous le même id. Chaque collection enregistre le nom du modèle d'embedding.
- **Alternatives écartées** : Chroma comme seul stockage du texte (pas de réindexation possible sans reparser les fichiers).
- **Conséquences** : réindexation possible depuis SQLite. La migration vers PostgreSQL et Qdrant en V2 en est facilitée.

## [2026-10-18] Chroma plutôt que FAISS
- **Contexte** : point ouvert de l'architecture.
- **Décision** : Chroma en mode embarqué (`PersistentClient`), sans serveur séparé.
- **Alternatives écartées** : FAISS, très performant mais simple index de vecteurs : persistance, métadonnées et filtres par document seraient à coder soi-même.
- **Conséquences** : filtrage par document natif (utile pour les sessions). Performances largement suffisantes pour quelques dizaines de documents.

## [2026-10-18] Tesseract plutôt que PaddleOCR
- **Contexte** : point ouvert de l'architecture, machine de 8 Go.
- **Décision** : Tesseract via `pytesseract`, langue `eng`. OCR déclenché seulement pour les images et les pages sans texte exploitable.
- **Alternatives écartées** : PaddleOCR et EasyOCR (meilleurs sur les scans difficiles, mais dépendances lourdes et forte consommation de RAM) ; OCR cloud (contraire au local-first).
- **Conséquences** : qualité moyenne sur des scans de mauvaise qualité, indiquée dans les limitations. PaddleOCR reste possible en V2 derrière la même fonction.

## [2026-10-18] Modèles locaux : qwen2.5:3b et nomic-embed-text
- **Contexte** : 8 Go de RAM, donc des modèles de 1B à 3B maximum.
- **Décision** : `qwen2.5:3b`, confirmé le 2026-10-18 après un test comparatif avec `llama3.2:3b` (extraction JSON et refus). Les deux ont produit du JSON pur et refusé correctement, à vitesse équivalente (~50 tokens/s) ; `llama3.2:3b` a modifié les valeurs extraites sans qu'on le demande (format de date changé, devise supprimée). Embeddings : `nomic-embed-text`. `num_ctx` fixé à 4096.
- **Alternatives écartées** : `llama3.2:3b` (fidélité moindre aux valeurs) ; modèles de 7B et plus (trop lourds pour la machine) ; modèles de 1B (trop faibles pour le Critic et l'Extractor).
- **Conséquences** : réponses locales plus lentes et moins précises qu'en ligne. Les garde-fous sont placés dans le code.

## [2026-10-18] Documents de démo en anglais et fictifs
- **Contexte** : `nomic-embed-text` est surtout entraîné sur l'anglais ; le public visé (recruteurs, README) est anglophone.
- **Décision** : trois documents fictifs en anglais (contrat PDF, facture scannée, revue trimestrielle PPTX) et quatre scénarios (question citée, refus, extraction, export).
- **Alternatives écartées** : documents réels (confidentialité, droits) ; documents en français (retrieval moins bon, ou modèle d'embedding multilingue plus lourd).
- **Conséquences** : le support multilingue n'est pas revendiqué en V1.

## [2026-10-18] Ollama natif, développement hors Docker
- **Contexte** : sur Mac, Docker n'a pas accès au GPU Metal, et sa VM consomme de la RAM.
- **Décision** : Ollama tourne toujours en natif. Développement quotidien en natif (venv + `npm run dev`) ; Docker Compose sert à la validation et à la démo, et le backend y appelle `host.docker.internal:11434`.
- **Alternatives écartées** : Ollama dans Docker (lent, sans GPU) ; tout développer dans Docker (lourd avec 8 Go).
- **Conséquences** : le `docker-compose.yml` ne contient pas Ollama. Le README explique comment l'installer à part.

## [À dater] Orchestration simple en V1
- **Contexte** : l'ambition multi-agents risque de retarder la V1.
- **Décision** : routage simple selon le type de demande, sans replanning.
- **Alternatives écartées** : replanning automatique (reporté en V2).
- **Conséquences** : interface Orchestrator conçue pour être étendue.

## [À dater] Abstractions LLM, embeddings, stockage
- **Contexte** : démo en ligne impossible avec un LLM local de qualité sur Railway ou HF Spaces gratuits.
- **Décision** : interfaces `LLMProvider` et `EmbeddingProvider` (Ollama / API externe), stockage vectoriel et métadonnées derrière des interfaces.
- **Conséquences** : migration facile vers PostgreSQL et Qdrant en V2.

## [À dater] SQLite + Chroma pour la V1
- **Contexte** : besoin de simplicité et de déploiement facile.
- **Décision** : SQLite et Chroma en V1.
- **Alternatives écartées** : PostgreSQL et Qdrant (reportés en V2).