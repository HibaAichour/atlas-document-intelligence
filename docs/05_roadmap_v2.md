# Roadmap ATLAS V2

Cocher les cases au fur et à mesure. Durée totale estimée : 29 à 42 jours de travail effectif.

> Statut : V2 commencée le 2026-11-04. La V1 est terminée (`04_roadmap.md`) et reste la démo en ligne.

Règles de la V2 :
- Une étape à la fois, dans l'ordre ci-dessous ; plan validé avant de coder.
- Critères de mesure fixés avant la mesure.
- À la fin de chaque étape : README, `02_architecture.md` et CV mis à jour, uniquement avec ce qui est livré.

## Étape V2.0 : Préparation (0,5 jour)
- [x] Image `latest` publiée seulement pour un tag de version (workflow modifié), et non plus à chaque push sur `main`
- [x] Scénarios de démo vérifiés en ligne après le changement
- [x] Tag `v1.0.0` et GitHub Release « ATLAS V1 »
- [x] `05_roadmap_v2.md` ajouté
- **Fin** : un push sur `main` ne peut plus changer la démo en ligne

## Étape V2.1 : Tests dans la CI (1 jour)
- [x] Workflow `tests.yml` : pytest, Vitest, build et lint du frontend
- [x] Alertes ruff corrigées, ruff bloquant ; mypy non bloquant
- [x] Badge des tests dans le README
- **Fin** : CI verte sur `main` (574 et 147 tests), en moins de 5 minutes avec le cache, et rouge sur un test volontairement cassé

## Étape V2.2 : Benchmarks et ablation study (4 à 6 jours)
- [ ] Liste des configurations fixée avant la mesure (seuil, écart, top-k, Critic par le modèle, taille des chunks, modèle d'embedding)
- [ ] Script qui lance l'évaluation sur chaque configuration (justesse, citations, latence, jetons)
- [ ] Mesures en local, et deux ou trois configurations en ligne (quota de Groq)
- [ ] Tableau des résultats dans `eval/` et dans le README
- **Fin** : chaque ligne du tableau est reproductible par une seule commande

## Étape V2.3 : Replanning après le verdict du Critic (3 à 5 jours)
- [ ] Une relance du Writer au maximum, avec les problèmes « Certain » du Critic
- [ ] Relance visible dans la trace des agents
- [ ] Mesure contre la référence de V2.2
- **Fin** : gain ou absence de gain mesuré et publié

## Étape V2.4 : Qdrant derrière VectorStore (2 à 3 jours)
- [ ] `QdrantVectorStore` derrière l'interface existante
- [ ] Qdrant dans Docker Compose, RAM mesurée
- [ ] Chroma gardé et sélectionné par variable d'environnement
- **Fin** : tests verts avec les deux stores, même score d'évaluation qu'avec Chroma

## Étape V2.5 : Ingestion asynchrone, Redis et worker (4 à 6 jours)
- [ ] Le téléversement répond tout de suite, le worker traite le document
- [ ] Statut `processing` puis `ready` ou `failed` affiché dans l'interface
- [ ] SQLite partagé par l'API et le worker (mode WAL), RAM mesurée
- **Fin** : un PDF scanné de 10 pages ne bloque plus l'interface, et un worker redémarré reprend les tâches en attente

## Étape V2.6 : WebSocket (2 à 3 jours)
- [ ] Progression de l'ingestion en direct
- [ ] Étapes des agents affichées au moment où elles se terminent
- **Fin** : l'interface se met à jour sans rechargement ni interrogation répétée

## Étape V2.7 : PostgreSQL et migrations (3 à 4 jours)
- [ ] SQLAlchemy sur PostgreSQL, SQLite toujours possible
- [ ] Alembic à la place de `add_missing_columns`
- [ ] Migration d'une base SQLite existante
- **Fin** : migration sans perte, tests verts sur les deux bases

## Étape V2.8 : Comptes et permissions (5 à 7 jours)
- [ ] Connexion des utilisateurs
- [ ] Documents et sessions par utilisateur
- **Fin** : un utilisateur ne voit jamais les documents d'un autre (testé)

## Étape V2.9 : Validation humaine des extractions (3 à 4 jours)
- [ ] Correction et validation d'une valeur extraite avant l'export
- [ ] Correction enregistrée et tracée
- **Fin** : la valeur corrigée apparaît dans l'export, avec la trace de la correction

## Étape V2.10 : Clôture de la V2 (1 à 2 jours)
- [ ] README, `02_architecture.md` et captures à jour
- [ ] Vidéo de la V2 (si utile)
- [ ] CV mis à jour
- **Fin** : dépôt V2 présentable
