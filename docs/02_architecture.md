# Architecture ATLAS V1

> Statut : complété à l'étape 1 (Cadrage), le 2026-10-18. Modèle local confirmé après le test de l'étape 0. Reste à confirmer : la plateforme de déploiement (à l'étape 12).

## 1. Stack V1 (validée)
| Brique | Choix V1 | Évolution V2 |
|---|---|---|
| Backend | Python 3.11+ + FastAPI | + workers Redis |
| Frontend | React + TypeScript + Vite | + WebSocket |
| Base de données | SQLite (source de vérité, y compris le texte des chunks) | PostgreSQL |
| Base vectorielle | Chroma en mode embarqué (`PersistentClient`, sans serveur) | Qdrant |
| OCR | Tesseract (via `pytesseract`), langue `eng` | PaddleOCR possible |
| LLM local | Ollama natif sur le Mac, `qwen2.5:3b` (confirmé à l'étape 0) | |
| LLM démo en ligne | API compatible OpenAI, Groq par défaut | |
| Embeddings local | `nomic-embed-text` via Ollama | |
| Embeddings démo en ligne | À choisir à l'étape 3, derrière `EmbeddingProvider` | |
| Export | python-docx, python-pptx | |
| Déploiement | Docker Compose (local), plateforme en ligne à confirmer à l'étape 12 | |

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
Plateforme d'hébergement
└── Conteneur unique (backend + frontend compilé servi par FastAPI)
    └── LLM et embeddings via API externe (pas de modèle local)
```
Les documents de démo sont indexés au démarrage du conteneur. Le disque des hébergeurs gratuits n'est souvent pas persistant, donc l'application ne doit pas dépendre de données conservées entre deux redémarrages.

### 3.4 Budget mémoire local (estimations, à mesurer à l'étape 0)
| Composant | RAM approximative |
|---|---|
| macOS + navigateur + VS Code | 3 à 4 Go |
| `qwen2.5:3b` (quantisé Q4, contexte 4096) | 2 à 2,5 Go |
| `nomic-embed-text` | ~0,3 Go |
| Backend Python + Chroma | 0,3 à 0,5 Go |
| VM Docker Desktop (si utilisée) | 1 à 2 Go |

Conséquences : développer en natif, limiter la mémoire de Docker Desktop, fixer `num_ctx` à 4096 (la RAM consommée augmente avec la taille du contexte).

## 4. Structure du dépôt
```
atlas/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── agents/       # orchestrator, analyst, extractor, writer, critic
│   │   ├── llm/          # LLMProvider, OllamaProvider, OpenAICompatibleProvider
│   │   ├── ingestion/    # PDF/DOCX/PPTX/image parsers, OCR, chunking
│   │   ├── retrieval/    # EmbeddingProvider, VectorStore, retriever
│   │   ├── export/       # docx, pptx
│   │   ├── db/           # models, repositories (SQLite)
│   │   └── core/         # config, logging
│   └── tests/
├── frontend/
│   └── src/
├── demo_documents/       # fictional demo files (English)
├── eval/                 # question set + scoring script (step 11)
├── docs/                 # vision, architecture, decisions, roadmap
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

## 7. Chunking et retrieval (valeurs de départ, à calibrer à l'étape 6)
- Un chunk ne chevauche jamais deux pages.
- Taille : ~1000 caractères, chevauchement de ~150 caractères à l'intérieur d'une même page.
- Top-k : 5 passages.
- Seuil de pertinence : à calibrer sur les documents de démo. En dessous, refus sans appel au LLM.
- Chaque collection Chroma enregistre le nom du modèle d'embedding. On ne mélange jamais deux modèles dans un même index. Changer de modèle implique de réindexer depuis SQLite.

## 8. Citations
- Le Writer reçoit des passages numérotés `[S1]`, `[S2]`, etc., et cite ces identifiants.
- Le backend vérifie que chaque identifiant cité existe, puis le convertit en `[NomDocument, p. X]`.
- Le frontend rend chaque citation cliquable vers le passage source.
- Une réponse dont une citation est inexistante est signalée par le Critic.

## 9. Modèle de données
- `documents` : id (uuid), filename, mime_type, page_count, ocr_used, status (`uploaded` / `processing` / `ready` / `failed`), error, created_at
- `chunks` : id, document_id, page, position, text, created_at (vecteur et métadonnées dans Chroma, sous le même id)
- `sessions` : id, title, created_at, updated_at
- `messages` : id, session_id, role (`user` / `assistant`), mode (`ask` / `extract`), content, sources (JSON), agent_trace (JSON), created_at
- `session_documents` : session_id, document_id

## 10. Configuration (variables d'environnement)
| Variable | Exemple local | Exemple démo en ligne |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `openai_compatible` |
| `LLM_MODEL` | `qwen2.5:3b` | modèle choisi chez le fournisseur |
| `LLM_BASE_URL` | `http://localhost:11434` | URL de l'API du fournisseur |
| `LLM_API_KEY` | (vide) | secret de la plateforme |
| `LLM_NUM_CTX` | `4096` | (ignoré) |
| `EMBEDDING_PROVIDER` | `ollama` | à définir à l'étape 3 |
| `EMBEDDING_MODEL` | `nomic-embed-text` | à définir à l'étape 3 |
| `DATA_DIR` | `./data` | `/tmp/atlas` ou volume |

## 11. MVP et scénarios de démo
Documents de démo : **en anglais et fictifs** (créés pour le projet, sans données réelles ni contenu protégé).

| Document | Format | Ce qu'il démontre |
|---|---|---|
| Contrat de prestation de services (5 à 8 pages) | PDF texte | RAG cité, extraction de clauses |
| Facture scannée | Image ou PDF scanné | OCR + extraction structurée |
| Revue trimestrielle d'activité | PPTX | Parsing PPTX, question chiffrée, export |

Scénarios (alignés sur la vidéo de 1 à 2 minutes) :
1. **Question citée** : « What is the termination notice period? » → réponse avec `[Contract, p. X]` cliquable.
2. **Refus** : « What is the CEO's salary? » → réponse indiquant que l'information est absente des documents.
3. **Extraction** : « Extract invoice number, date, total and due date » sur la facture → JSON, trace Analyst → Extractor → Critic visible.
4. **Export** : export en .docx et .pptx du résultat, sources incluses.

Le MVP est atteint quand ces quatre scénarios fonctionnent de bout en bout, en local avec Ollama et en ligne avec l'API externe.

## 12. Limitations connues (pour le README)
- En local, un modèle de 3B produit des réponses moins précises et plus lentes que l'API externe.
- La pagination des DOCX est approximative (sections numérotées).
- L'OCR Tesseract est sensible à la qualité des scans.
- Traitement synchrone : l'ingestion d'un gros document bloque la requête (asynchrone prévu en V2).

## 13. Points ouverts
- **Embeddings en ligne** : API d'embeddings ou petit modèle léger dans le conteneur. Décision à l'étape 3.
- **Plateforme de déploiement** : les conditions de Hugging Face Spaces et de Railway sont à revérifier à l'étape 12. L'image doit rester légère (aucun modèle local en production) pour être compatible avec une offre modeste.
