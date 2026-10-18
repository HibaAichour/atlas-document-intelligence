# Journal des décisions techniques — ATLAS V1

Format : une entrée par décision, la plus récente en haut.

## Modèle d'entrée
### [AAAA-MM-JJ] Titre de la décision
- **Contexte** : pourquoi la question se pose
- **Décision** : ce qui est choisi
- **Alternatives écartées** : et pourquoi
- **Conséquences** : impact sur le projet, lien avec la V2

---

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
