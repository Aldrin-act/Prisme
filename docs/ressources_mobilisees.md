# Ressources mobilisées — PRISME

> Destiné à s'insérer dans le rapport de stage de fin d'études, au chapitre « Ressources,
> méthodologie et bilan du cadrage initial » (à la suite du chapitre « Enjeux et analyse du
> besoin »). Numérotation laissée générique (3.1, 3.1.1…) pour un rattachement direct au chapitre
> concerné ; à ajuster selon la numérotation finale du document.

## 3.1 Ressources mobilisées

La réalisation de ce projet a nécessité la mobilisation de ressources humaines, technologiques et
matérielles, dont la combinaison a permis d'assurer le bon déroulement des différentes phases du
projet, du cadrage du besoin jusqu'à la réalisation de la solution.

### 3.1.1 Ressources humaines

Le projet a été mené avec l'appui de deux encadrants aux rôles complémentaires. Un encadrement
professionnel a été assuré au sein de l'entreprise d'accueil, **BARAA Consult**, par **madame
CHOKRI Soumia** : son rôle a consisté à cadrer les attentes métier, orienter les choix techniques
et valider les livrables opérationnels au fil des itérations du projet. Un encadrement académique
a par ailleurs été assuré par le tuteur pédagogique, **monsieur Zakaria El makhlouki** (EIGSI
Casablanca), chargé de suivre l'avancement des travaux, de valider les choix méthodologiques et de
garantir la conformité du projet aux attendus pédagogiques du PFE (dominante Big Data & IA). Cet
encadrement à deux voix — entreprise et académique — a permis de confronter régulièrement les
choix de conception à la fois à leur pertinence métier et à leur rigueur méthodologique.

> [À compléter : si un ou plusieurs interlocuteurs côté client / utilisateurs finaux (Key Users,
> atelier pilote) ont participé au cadrage du besoin ou à la validation intermédiaire des
> livrables, les nommer ici avec la nature précise de leur contribution.]

Au-delà de l'encadrement, le projet a mobilisé, sur un seul système, les deux volets de la
spécialité Intelligence Artificielle & Big Data du stagiaire : l'orchestration d'agents génératifs
appuyés sur un LLM (compréhension, génération de code, correction), et l'ingénierie de données
nécessaire pour canoniser des exports industriels hétérogènes vers un modèle pivot unique —
auxquelles s'ajoutent des compétences de génie logiciel plus classiques : conception d'API REST,
sécurisation de l'exécution de code non fiable par construction, tests automatisés.

### 3.1.2 Ressources technologiques

Plusieurs outils et technologies ont été mobilisés pour la conception et le développement de la
solution, retenus en 100 % open-source. Le projet repose sur une architecture web organisée
autour d'une **API REST développée avec FastAPI** (Python 3.11, dépendances gérées par `uv`) pour
la partie back-end, ainsi qu'une application web développée avec **React 19, TypeScript et
TanStack Start** (routage et gestion d'état via TanStack Router/Query, Vite comme outil de build
sous-jacent, Tailwind CSS 4 et composants Radix UI pour l'interface) pour le tableau de bord
opérateur.

Le cœur algorithmique du projet s'appuie sur **OR-Tools CP-SAT** (Google), le seul solveur
*exact* du catalogue disponible à l'agent Benchmarker pour les instances de taille raisonnable —
une heuristique (génétique, ACO, tabou, recuit simulé, dispatching, greedy) prenant le relais sur
les instances trop grandes pour un solveur exact. Le pipeline de génération de code multi-agents
est orchestré avec **LangGraph** et **LangChain**, appuyé sur des fournisseurs LLM externes routés
individuellement par agent plutôt que sur un unique fournisseur figé.

La gestion des données repose sur **PostgreSQL** (conteneurisé via Docker, image `postgres:16`),
interrogé directement en SQL via le pilote **psycopg 3** plutôt que par un ORM — un choix cohérent
avec le volume et la structure du schéma applicatif (une table par axe du modèle pivot T-R-C-O et
par entité multi-tenant, plutôt qu'un mapping objet-relationnel complexe). L'ensemble des services
du projet (base de données, environnement de développement conteneurisé, tableau de bord, base de
référence GreenSIG) est orchestré avec **Docker et Docker Compose**, ce qui facilite l'isolation
des services ainsi que la portabilité de l'environnement entre postes de développement.

Plusieurs bibliothèques complémentaires assurent des fonctionnalités transverses : **Pydantic v2**
pour la validation stricte du modèle pivot T-R-C-O et des payloads d'API, **PyJWT** et
**Passlib** (hachage bcrypt) pour l'authentification et la sécurisation multi-tenant,
**python-dotenv** pour la gestion centralisée des variables d'environnement, **PyYAML** pour la
lecture des configurations sectorielles, et le **SDK Docker Python** pour le pilotage du bac à
sable d'exécution éphémère. Les tests et la qualité de code s'appuient sur **pytest** et **ruff**,
exécutés localement et en intégration continue (GitHub Actions).

> [À compléter : outil(s) effectivement utilisé(s) pour les maquettes d'interface et les
> diagrammes de conception (le cas échéant), et environnement de développement (éditeur/IDE).]

### 3.1.3 Ressources matérielles

Aucune ressource de calcul dédiée (GPU, cluster) n'a été nécessaire au projet : la génération de
code s'appuie sur un service LLM externe sollicité hors ligne, et l'exécution des solveurs — y
compris sur l'instance de test la plus volumineuse traitée (2 165 tâches) — reste un calcul CPU
classique, exécutable sur un poste de développement standard.

> [À compléter : ordinateur utilisé (marque/modèle, caractéristiques), accès réseau/connectivité,
> et toute autre ressource matérielle mobilisée pour le développement, les tests ou la
> démonstration du projet.]
