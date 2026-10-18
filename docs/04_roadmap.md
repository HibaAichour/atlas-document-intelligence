# Roadmap ATLAS V1

Cocher les cases au fur et à mesure. Durée totale estimée : 35 à 45 jours de travail effectif.

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
- [ ] Dépôt GitHub, structure backend/ et frontend/
- [ ] FastAPI avec `/health`
- [ ] React + TypeScript + Vite appelant le backend
- [ ] docker-compose.yml
- **Fin** : `docker compose up` affiche le frontend connecté au backend

## Étape 3 : Couche LLM abstraite (1 à 2 jours)
- [ ] Interface `LLMProvider` + Ollama + API externe
- [ ] Interface embeddings
- [ ] Sélection par variable d'environnement
- **Fin** : test passant avec les deux providers

## Étape 4 : Upload, parsing, OCR (3 à 4 jours)
- [ ] Upload de fichiers
- [ ] Extraction PDF, DOCX, PPTX avec numéro de page
- [ ] OCR Tesseract (scans et images)
- [ ] Métadonnées en SQLite
- **Fin** : un PDF scanné donne du texte page par page

## Étape 5 : Chunking, embeddings, indexation (2 à 3 jours)
- [ ] Chunking avec document, page, position
- [ ] Embeddings
- [ ] Chroma derrière une interface
- **Fin** : une requête retourne les bons passages avec sources

## Étape 6 : RAG avec citations + Writer (3 à 4 jours)
- [ ] Prompt forçant la réponse depuis les passages
- [ ] Citations `[Document, p. X]`
- [ ] Refus si information absente
- **Fin** : question dans l'API, réponse citée et vérifiable (premier jalon démontrable)

## Étape 7 : Frontend principal (4 à 5 jours)
- [ ] Page d'upload et liste des documents
- [ ] Interface de chat
- [ ] Sources cliquables
- **Fin** : parcours complet dans le navigateur

## Étape 8 : Historique des sessions (2 jours)
- [ ] Sessions, messages, documents associés en base
- [ ] Liste et reprise de session dans l'interface
- **Fin** : fermer l'onglet, revenir, tout est là

## Étape 9 : Agents et orchestration (5 à 7 jours)
- [ ] Critic
- [ ] Document Analyst
- [ ] Extractor (JSON structuré)
- [ ] Orchestrator (routage simple)
- [ ] Affichage des agents intervenus
- **Fin** : une extraction passe par Analyst, Extractor, Critic

## Étape 10 : Export Word et PowerPoint (2 à 3 jours)
- [ ] .docx avec python-docx
- [ ] .pptx avec python-pptx
- [ ] Bouton Exporter, sources incluses
- **Fin** : fichiers propres générés

## Étape 11 : Tests et mini-évaluation (2 à 3 jours)
- [ ] Tests unitaires des composants clés
- [ ] Jeu de 15 à 20 questions avec réponses attendues
- [ ] Script de score
- **Fin** : score affiché

## Étape 12 : Déploiement (2 à 3 jours)
- [ ] Docker de production
- [ ] Déploiement Railway ou HF Spaces avec LLM externe
- [ ] Documents de démo préchargés
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
