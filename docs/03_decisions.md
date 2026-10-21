# Journal des décisions techniques — ATLAS V1

Format : une entrée par décision, la plus récente en haut.

## Modèle d'entrée
### [AAAA-MM-JJ] Titre de la décision
- **Contexte** : pourquoi la question se pose
- **Décision** : ce qui est choisi
- **Alternatives écartées** : et pourquoi
- **Conséquences** : impact sur le projet, lien avec la V2

---
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