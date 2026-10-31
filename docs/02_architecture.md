# Architecture ATLAS V1

> Statut : rédigé à l'étape 1 (Cadrage), le 2026-10-18, et mis à jour à l'étape 13, le 2026-10-31, pour décrire la V1 livrée. Le détail et la justification de chaque choix sont dans `03_decisions.md`.

## 1. Stack V1 (validée)
| Brique | Choix V1 | Évolution V2 |
|---|---|---|
| Backend | Python 3.11+ + FastAPI | + workers Redis |
| Frontend | React + TypeScript + Vite | + WebSocket |
| Base de données | SQLite (source de vérité, y compris le texte des chunks) | PostgreSQL |
| Base vectorielle | Chroma en mode embarqué (`PersistentClient`, sans serveur) | Qdrant |
| OCR | Tesseract (via `pytesseract`), langue `eng` | PaddleOCR possible |
| LLM local | Ollama natif sur le Mac, `qwen2.5:3b` (confirmé à l'étape 0) | |
| LLM démo en ligne | API compatible OpenAI, Groq par défaut (`openai/gpt-oss-20b`) | |
| Embeddings local | `bge-m3` via Ollama, multilingue (remplace `nomic-embed-text` depuis l'étape 10 bis) | |
| Embeddings démo en ligne | `gemini-embedding-001` (API Gemini, point d'accès compatible OpenAI) | |
| Export | python-docx, python-pptx | |
| Déploiement | Docker Compose (local) ; démo en ligne sur SnapDeploy, image construite par GitHub Actions | |
| Interface | Bilingue anglais et français (dictionnaire typé `lib/i18n.ts`) | |

## 2. Principes
- **Local-first** : tout fonctionne avec Ollama, sans clé API.
- **Abstractions** : LLM, embeddings, stockage des métadonnées et stockage vectoriel sont derrière des interfaces. La migration V2 se fait sans réécriture.
- **Simplicité** : orchestration à règles en V1, structurée pour accueillir un replanning en V2.
- **Traçabilité** : chaque chunk garde document, page et position. Une citation pointe toujours vers une page exacte.
- **Sobriété mémoire** : 8 Go de RAM en développement. Aucun composant lourd (PyTorch, serveur vectoriel, OCR à réseau de neurones) n'est ajouté en V1.
- **Le code vérifie ce que le LLM ne garantit pas** : validation du JSON, existence des citations, refus si aucun passage pertinent. Un modèle de 3B suit mal les consignes complexes, donc les garde-fous sont dans le code, pas seulement dans les prompts.

## 3. Environnement d'exécution

### 3.1 Développement quotidien (natif)
```
Mac
├── Ollama (natif, accès GPU Metal)      :11434
├── Backend FastAPI (venv Python)        :8000
└── Frontend Vite (npm run dev)          :5173
```

### 3.2 Validation et démo locale (Docker Compose)
```
Mac
├── Ollama (natif, hors Docker)          :11434
└── Docker Compose
    ├── backend  ──> http://host.docker.internal:11434
    └── frontend
```
Ollama ne tourne jamais dans Docker sur Mac : Docker n'y a pas accès au GPU Metal, et la VM Docker ajoute sa propre consommation de RAM.

### 3.3 Démo en ligne
```
GitHub
├── Dépôt (code)
└── GitHub Actions : à chaque push sur main, construit l'image ARM64
    └── GitHub Container Registry (image publique, sans aucune clé)

SnapDeploy (offre gratuite : 512 Mo, 0,25 vCPU)
└── Conteneur unique tiré de l'image publique
    ├── FastAPI : API /api + frontend compilé (STATIC_DIR)
    ├── DEMO_MODE : téléversement refusé (403)
    └── LLM (Groq, gpt-oss-20b) et embeddings (Gemini) via API externe
```
- Les documents de démo sont lus au build (`scripts/seed_demo.py`, OCR compris) ; leurs vecteurs sont calculés à chaque démarrage (`scripts/reindex.py`), car le disque n'est pas persistant.
- Les deux clés sont données au conteneur par l'hébergeur, jamais par l'image ni par le dépôt.
- SnapDeploy n'a aucun accès au compte GitHub : il tire seulement l'image publique.
- Le conteneur s'endort après environ 15 minutes sans visite et se réveille en environ une minute à la visite suivante ; les sessions repartent alors de zéro.

### 3.4 Budget mémoire local (estimations de l'étape 1)
| Composant | RAM approximative |
|---|---|
| macOS + navigateur + VS Code | 3 à 4 Go |
| `qwen2.5:3b` (quantisé Q4, contexte 4096) | 2 à 2,5 Go |
| `nomic-embed-text` | ~0,3 Go |
| Backend Python + Chroma | 0,3 à 0,5 Go |
| VM Docker Desktop (si utilisée) | 1 à 2 Go |

Conséquences : développer en natif, limiter la mémoire de Docker Desktop, fixer `num_ctx` à 4096 (la RAM consommée augmente avec la taille du contexte).

Mesures ultérieures : `bge-m3` occupe environ 673 Mo (contre 370 Mo pour `nomic-embed-text`) ; le conteneur de production, limité à 512 Mo et 0,1 processeur, est resté entre 285 et 301 Mo pendant les scénarios de démo.

## 4. Structure du dépôt
```
atlas/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── agents/       # orchestrator, analyst, extractor, writer, critic
│   │   ├── llm/          # LLMProvider, OllamaProvider, OpenAICompatibleProvider
│   │   ├── ingestion/    # PDF/DOCX/PPTX/image parsers, OCR, chunking
│   │   ├── retrieval/    # EmbeddingProvider, Embedder, VectorStore, Retriever
│   │   ├── rag/          # citations (S1 -> [Document, p. X]), answer result, refusal
│   │   ├── export/       # docx, pptx
│   │   ├── db/           # models, repositories (SQLite), schema upgrade
│   │   ├── core/         # config, provider factories, HTTP errors
│   │   └── frontend.py   # serves the compiled frontend (online demo)
│   ├── scripts/          # seed_demo, reindex, run_eval, probes, demo file generators
│   ├── tests/
│   └── Dockerfile        # backend image for Docker Compose (local)
├── frontend/
│   ├── src/              # api/, lib/, hooks/, components/
│   └── Dockerfile        # Nginx image for Docker Compose (local)
├── demo_documents/       # 4 fictional demo files (3 in English, 1 in French)
├── eval/                 # question set and results (local and online)
├── docs/                 # vision, architecture, decisions, roadmap
├── .github/workflows/    # publish-image.yml (image of the online demo)
├── Dockerfile            # production image (single container, online demo)
├── docker-compose.yml
└── README.md
```

## 5. Flux principaux

**Ingestion** : upload, détection du type, extraction du texte page par page (OCR Tesseract si la page n'a pas de texte exploitable ou si le fichier est une image), chunking par page, enregistrement des chunks en SQLite, calcul des embeddings, indexation dans Chroma, statut du document à `ready`.

Correspondance « page » selon le format :
- PDF : page réelle.
- PPTX : une diapositive = une page.
- Image : page 1.
- DOCX : le format ne stocke pas de pagination fiable. On découpe par sections (titres) et on numérote ces sections comme des « pages ». Cette limitation est indiquée dans le README.

**Question (RAG)** : question, Orchestrator (route `ask`), retrieval (top-k chunks), refus immédiat si aucun chunk ne dépasse le seuil de pertinence, Writer (réponse citée), Critic (vérification), réponse affichée avec ses sources.

**Extraction** : demande, Orchestrator (route `extract`), Document Analyst (profil du document et pages pertinentes), Extractor (JSON validé par un schéma Pydantic), Critic (vérification par rapport aux sources), résultat affiché.

**Export** : résultat validé, génération d'un .docx ou d'un .pptx avec la liste des sources.

## 6. Agents
| Agent | Appelle le LLM | Entrée | Sortie |
|---|---|---|---|
| Orchestrator | Non (règles) | Demande + mode choisi (`ask` / `extract`) | Plan : liste ordonnée d'étapes |
| Document Analyst | Oui | Document (pages) | Profil : type de document, sections, pages pertinentes |
| Extractor | Oui | Pages pertinentes + type d'extraction | JSON validé (Pydantic) |
| Writer | Oui | Question + passages numérotés `[S1]…[Sn]` | Réponse avec citations `[S1]` |
| Critic | Oui + contrôles code | Réponse ou JSON + passages | Verdict (`ok` / `issues`) + liste des problèmes |

Le retrieval est un **outil** utilisé par l'Orchestrator, pas un agent : c'est une recherche déterministe, sans décision.

Le plan produit par l'Orchestrator est une liste d'étapes explicite. En V2, un replanning pourra modifier cette liste après le verdict du Critic, sans changer les agents.

Chaque exécution d'agent est enregistrée (nom, durée, statut) dans le message. C'est cette trace qu'affiche l'interface (« agents intervenus »).

## 7. Chunking et retrieval
- Un chunk ne chevauche jamais deux pages.
- Taille : ~1000 caractères, chevauchement de ~150 caractères à l'intérieur d'une même page.
- Top-k : 5 passages.
- Seuil de pertinence : en dessous, refus sans appel au LLM. Écart au meilleur score : seuls les passages proches du meilleur sont envoyés au Writer.

| Réglage | Local (`bge-m3`) | Démo en ligne (Gemini) |
|---|---|---|
| `RETRIEVAL_MIN_SCORE` | 0,44 | 0,56 |
| `RETRIEVAL_MAX_GAP` | 0,05 | 1 (désactivé) |

Chaque valeur a été mesurée sur les documents de démo (`probe_scores`, `probe_margin`) avec des critères fixés avant la mesure.
- Chaque collection Chroma enregistre le nom du modèle d'embedding. On ne mélange jamais deux modèles dans un même index. Changer de modèle implique de réindexer depuis SQLite (`scripts/reindex.py`).

## 8. Citations
- Le Writer reçoit des passages numérotés `[S1]`, `[S2]`, etc., et cite ces identifiants.
- Le backend vérifie que chaque identifiant cité existe, puis le convertit en `[NomDocument, p. X]`.
- Le frontend rend chaque citation cliquable vers le passage source.
- Une réponse dont une citation est inexistante est signalée par le Critic.

## 9. Modèle de données
- `documents` : id (uuid), filename, mime_type, page_count, ocr_used, status (`uploaded` / `processing` / `ready` / `failed`), error, created_at
- `pages` : id, document_id, page_number, text, ocr_used (texte extrait, source de la ré-indexation)
- `chunks` : id (uuid), document_id, page_number, position, text, created_at (vecteur et métadonnées dans Chroma, sous le même id)
- `sessions` : id, title, created_at, updated_at
- `messages` : id, session_id, position, role (`user` / `assistant`), mode (`ask` / `extract`), content, sources (JSON, copie complète des citations), agent_trace (JSON), status, refusal_reason, invalid_citations, warnings, best_score, review (verdict du Critic), extraction (champs extraits), created_at
- `session_documents` : session_id, document_id

Les colonnes facultatives ajoutées après coup sont créées au démarrage par `add_missing_columns` (pas d'outil de migration en V1).

## 10. Configuration (variables d'environnement)
| Variable | Exemple local | Exemple démo en ligne |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `openai_compatible` |
| `LLM_MODEL` | `qwen2.5:3b` | `openai/gpt-oss-20b` (Groq) |
| `LLM_BASE_URL` | `http://localhost:11434` | URL de l'API du fournisseur |
| `LLM_API_KEY` | (vide) | secret de la plateforme |
| `LLM_NUM_CTX` | `4096` | (ignoré) |
| `EMBEDDING_PROVIDER` | `ollama` | `openai_compatible` |
| `EMBEDDING_MODEL` | `bge-m3` | `gemini-embedding-001` |
| `EMBEDDING_BASE_URL` | `http://localhost:11434` | point d'accès compatible OpenAI de Gemini |
| `EMBEDDING_API_KEY` | (vide) | secret de la plateforme |
| `RETRIEVAL_MIN_SCORE` | `0.44` | `0.56` |
| `RETRIEVAL_MAX_GAP` | `0.05` | `1` |
| `DEMO_MODE` | `false` | `true` |
| `STATIC_DIR` | (vide) | `/app/static` |
| `DATA_DIR` | `./data` | `/app/data` (non persistant) |

Les valeurs de la démo en ligne sont dans le `Dockerfile` de la racine, sauf les deux clés.

## 11. MVP et scénarios de démo
Documents de démo : **fictifs**, créés pour le projet, sans données réelles ni contenu protégé ; trois en anglais, puis un en français depuis l'étape 10 bis.

| Document | Format | Ce qu'il démontre |
|---|---|---|
| Contrat de prestation de services (5 à 8 pages) | PDF texte | RAG cité, extraction de clauses |
| Facture scannée | Image ou PDF scanné | OCR + extraction structurée |
| Revue trimestrielle d'activité | PPTX | Parsing PPTX, question chiffrée, export |
| Compte rendu de comité de pilotage (ajouté à l'étape 10 bis) | PDF texte, en français | Questions en français, recherche interlangue |

Scénarios (alignés sur la vidéo de 1 à 2 minutes) :
1. **Question citée** : « What is the termination notice period? » → réponse avec `[Contract, p. X]` cliquable.
2. **Refus** : « What is the CEO's salary? » → réponse indiquant que l'information est absente des documents.
3. **Extraction** : « Extract invoice number, date, total and due date » sur la facture → JSON, trace Analyst → Extractor → Critic visible.
4. **Export** : export en .docx et .pptx du résultat, sources incluses.

Le MVP est atteint quand ces quatre scénarios fonctionnent de bout en bout, en local avec Ollama et en ligne avec l'API externe : c'est le cas depuis l'étape 12, en anglais et en français. Évaluation (21 questions, 2 extractions) : en local avec `qwen2.5:3b`, 13 réponses justes et bien citées sur 21 et 15 champs sur 15 ; en ligne avec `gpt-oss-20b`, 18 sur 21 et 15 sur 15 (scores non comparables : autres modèles).

## 12. Limitations connues (pour le README)
- En local, un modèle de 3B produit des réponses moins précises et plus lentes que l'API externe.
- La pagination des DOCX est approximative (sections numérotées).
- L'OCR Tesseract est sensible à la qualité des scans.
- Traitement synchrone : l'ingestion d'un gros document bloque la requête (asynchrone prévu en V2).
- Démo en ligne : téléversement désactivé, sessions partagées entre visiteurs, réveil d'environ une minute après une mise en veille, 100 heures de fonctionnement par mois, quotas gratuits de Groq et de Gemini.
- La liste complète, mesurée, est dans le README.

## 13. Points tranchés à l'étape 12
- **Embeddings en ligne** : `gemini-embedding-001`, Groq n'en proposant pas (entrée du 2026-10-28).
- **Plateforme de déploiement** : SnapDeploy, offre gratuite sans carte bancaire ; Render demandait une carte et Hugging Face Spaces réserve Docker à son abonnement (entrées du 2026-10-31).
- **Image de production** : conteneur unique, images de base épinglées, construite et publiée par GitHub Actions (entrées du 2026-10-29 et du 2026-10-31).
