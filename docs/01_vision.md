# ATLAS V1 — Autonomous Multi-Agent Document Intelligence Platform

## 1. Objectif
ATLAS V1 est une plateforme web permettant de déposer des documents professionnels (PDF, DOCX, PPTX, images), puis d'interagir avec leur contenu grâce à plusieurs agents IA. C'est un projet portfolio destiné à des candidatures en AI Engineering : il doit être solide, stable et facile à démontrer à un recruteur.

## 2. Fonctionnalités V1

### 2.1 Ingestion et OCR
- Upload de PDF, DOCX, PPTX et images.
- OCR pour les documents scannés ou contenant des images.
- Extraction du texte avec conservation du numéro de page.
- Découpage (chunking) et indexation pour la recherche sémantique.

### 2.2 RAG fiable avec citations
- Recherche des passages pertinents pour chaque question.
- Réponse basée prioritairement sur ces passages.
- Citation systématique du document et de la page source : `[Document, p. X]`.
- Refus de répondre (ou signalement clair) si l'information est absente des documents.
- Objectif : réduire les hallucinations, rendre les réponses vérifiables.

### 2.3 Architecture multi-agents (5 agents)
| Agent | Rôle |
|---|---|
| Orchestrator | Reçoit la demande, choisit les agents et l'ordre d'exécution |
| Document Analyst | Analyse la structure et le contenu des documents |
| Extractor | Extrait des informations structurées (noms, dates, montants, clauses, chiffres) |
| Writer | Transforme les informations en réponses, synthèses, rapports |
| Critic | Vérifie cohérence, conformité aux sources, informations non justifiées |

Exemples de routage :
- Question documentaire : Retrieval/RAG, puis Writer.
- Demande d'extraction : Document Analyst, puis Extractor, puis Critic.

L'orchestration reste volontairement simple (pas de replanning automatique en V1), mais l'architecture doit permettre de l'ajouter proprement en V2.

### 2.4 Interface (React + TypeScript)
- Téléversement de documents.
- Liste des documents disponibles.
- Chat avec affichage des réponses et des sources.
- Lancement d'analyses.
- Consultation de l'historique des sessions.
- Affichage des agents intervenus.
- Design propre, moderne, professionnel.

### 2.5 Export
- Export des résultats en Word (.docx) et PowerPoint (.pptx), sources incluses.

### 2.6 Mode local (local-first)
- Exécution des modèles via Ollama, sans API payante obligatoire.
- Couche d'abstraction LLM : Ollama en local, API externe pour la démo en ligne.

### 2.7 Historique des sessions
- Chaque session conserve : demandes, documents utilisés, réponses générées.

### 2.8 Déploiement et livrables
- Docker / Docker Compose pour l'environnement de développement.
- Démo en ligne (Railway ou Hugging Face Spaces) avec un LLM externe.
- README GitHub professionnel en anglais : problème, objectifs, fonctionnalités, architecture, agents, RAG, citations, technologies, installation, mode Ollama, captures d'écran, limitations connues.
- Vidéo de démonstration de 1 à 2 minutes : import, question, sources, agents, Critic, export.

## 3. Hors périmètre V1
- Redis et workers, exécution asynchrone.
- Replanning automatique avancé.
- Observabilité temps réel (WebSocket).
- Benchmarks et ablation studies complets.
- Permissions et human-in-the-loop.
- PostgreSQL et Qdrant.

## 4. Évolution prévue
**V2 (production et systèmes distribués)** : Redis + workers, replanning, WebSocket, benchmarks et ablation studies, permissions et human-in-the-loop, PostgreSQL + Qdrant.

Compétences démontrées : V1 = AI Engineering, RAG, Multi-Agent Systems, backend/frontend, intégration LLM. V2 = systèmes distribués, fiabilité, observabilité, évaluation, production engineering.

## 5. Règle CV
Ne mentionner sur le CV que ce qui est réellement implémenté au moment de la candidature. Mettre à jour GitHub et CV à chaque évolution V2.

## 6. Ordre de travail
1. Phase 1, V1 puis candidature : Upload + OCR, RAG + citations, 5 agents, orchestration simple, React, Word/PPT, Ollama, historique, Docker/déploiement, README + vidéo.
2. Phase 2 : Redis + workers, asynchrone, WebSocket, replanning, robustesse.
3. Phase 3 : PostgreSQL + Qdrant, permissions, human-in-the-loop, benchmarks, ablation study, métriques, optimisation.
