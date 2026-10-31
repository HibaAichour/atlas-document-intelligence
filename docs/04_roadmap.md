# Roadmap ATLAS V1

Cocher les cases au fur et à mesure. Durée totale estimée : 38 à 50 jours de travail effectif.

## Étape 0 : Préparer la machine (1 jour)
- [x] Git, Python 3.11+, Node 20+, Docker Desktop, VS Code
- [x] Ollama + modèle LLM (qwen2.5:3b, retenu après test comparatif) + nomic-embed-text
- [x] Tesseract OCR
- [x] Claude Code installé
- **Fin** : `ollama run` répond dans le terminal

## Étape 1 : Cadrage (1 à 2 jours)
- [x] Stack validée
- [x] `02_architecture.md` complété
- [x] MVP et cas d'usage de démo définis
- **Fin** : architecture et décisions écrites

## Étape 2 : Squelette du projet (2 jours)
- [x] Dépôt GitHub, structure backend/ et frontend/
- [x] FastAPI avec `/health`
- [x] React + TypeScript + Vite appelant le backend
- [x] docker-compose.yml
- **Fin** : `docker compose up` affiche le frontend connecté au backend

## Étape 3 : Couche LLM abstraite (1 à 2 jours)
- [x] Interface `LLMProvider` + Ollama + API externe
- [x] Interface embeddings
- [x] Sélection par variable d'environnement
- **Fin** : test passant avec les deux providers

## Étape 4 : Upload, parsing, OCR (3 à 4 jours)
- [x] Upload de fichiers
- [x] Extraction PDF, DOCX, PPTX avec numéro de page
- [x] OCR Tesseract (scans et images)
- [x] Métadonnées en SQLite
- **Fin** : un PDF scanné donne du texte page par page

## Étape 5 : Chunking, embeddings, indexation (2 à 3 jours)
- [x] Chunking avec document, page, position
- [x] Embeddings
- [x] Chroma derrière une interface
- **Fin** : une requête retourne les bons passages avec sources

## Étape 6 : RAG avec citations + Writer (3 à 4 jours)
- [x] Prompt forçant la réponse depuis les passages
- [x] Citations `[Document, p. X]`
- [x] Refus si information absente
- **Fin** : question dans l'API, réponse citée et vérifiable (premier jalon démontrable)

## Étape 7 : Frontend principal (4 à 5 jours)
- [x] Page d'upload et liste des documents
- [x] Interface de chat
- [x] Sources cliquables
- **Fin** : parcours complet dans le navigateur

## Étape 8 : Historique des sessions (2 jours)
- [x] Sessions, messages, documents associés en base
- [x] Liste et reprise de session dans l'interface
- **Fin** : fermer l'onglet, revenir, tout est là

## Étape 9 : Agents et orchestration (5 à 7 jours)
- [x] Critic
- [x] Document Analyst
- [x] Extractor (JSON structuré)
- [x] Orchestrator (routage simple)
- [x] Affichage des agents intervenus
- **Fin** : une extraction passe par Analyst, Extractor, Critic

## Étape 10 : Export Word et PowerPoint (2 à 3 jours)
- [x] .docx avec python-docx
- [x] .pptx avec python-pptx
- [x] Bouton Exporter, sources incluses
- **Fin** : fichiers propres générés

## Étape 10 bis : Bilingue FR/EN (3 à 5 jours)
- [x] Interface : dictionnaire français, sélecteur de langue, choix mémorisé
- [x] Messages du backend (erreurs, refus) dans la langue choisie
- [x] Agents : réponses, extractions et vérifications dans la langue de l'utilisateur
- [x] Modèle d'embedding multilingue (RAM mesurée), ré-indexation, nouveau calibrage du seuil
- [x] Document de démo en français
- [x] Export Word et PowerPoint traduit
- **Fin** : les scénarios de démo fonctionnent en français et en anglais

## Étape 11 : Tests et mini-évaluation (2 à 3 jours)
- [x] Scénario 1 : passages envoyés au Writer (écart de 0,05 au meilleur score ; « 30 days » en anglais : limite du 3B, vidéo en ligne)
- [x] Tests unitaires des composants clés (React Testing Library : Critic, extraction, chat)
- [x] Jeu de 15 à 20 questions avec réponses attendues (FR et EN) : 21 questions et 2 extractions
- [x] Script de score (noté par le code, résultats dans eval/results.json)
- **Fin** : score affiché

## Étape 12 : Déploiement (2 à 3 jours)
- [x] Docker de production
- [x] Déploiement sur SnapDeploy (offre gratuite ; Render demandait une carte) avec LLM externe
- [x] Documents de démo préchargés
- [x] Évaluation en ligne (run_eval) et scénario 1 avec gpt-oss-20b (18 sur 21, 15 champs sur 15)
- **Fin** : lien public fonctionnel

## Étape 13 : README et vidéo (2 à 3 jours)
- [ ] README en anglais complet
- [ ] Schéma d'architecture et captures
- [ ] Vidéo de 1 à 2 minutes
- **Fin** : dépôt GitHub présentable

## Étape 14 : Candidatures
- [ ] CV mis à jour (uniquement ce qui est implémenté)
- [ ] Liens GitHub, démo, vidéo
- [ ] Début des candidatures
- [ ] Démarrage de la V2 en parallèle