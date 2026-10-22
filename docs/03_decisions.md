# Journal des décisions techniques — ATLAS V1

Format : une entrée par décision, la plus récente en haut.

## Modèle d'entrée
### [AAAA-MM-JJ] Titre de la décision
- **Contexte** : pourquoi la question se pose
- **Décision** : ce qui est choisi
- **Alternatives écartées** : et pourquoi
- **Conséquences** : impact sur le projet, lien avec la V2

---
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