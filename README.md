# PRISME

Plateforme de génération et d'exécution de solveurs d'ordonnancement pilotée par IA.
PFE — EIGSI Casablanca × BARAA Consult.

Voir [`PRISME_Note_de_Cadrage (2).md`](<./PRISME_Note_de_Cadrage (2).md>) pour le cadrage complet
du projet (problème, architecture, stratégie de validation, roadmap), et
[`PRISME_Plan_Developpement.md`](./PRISME_Plan_Developpement.md) pour le découpage en tickets.

## Principe fondateur

Le code du solveur est **généré une seule fois** par une boucle multi-agent (`generation/`), puis
**persisté** (`solver_store/`) et **réexécuté** à chaque itération dans un conteneur éphémère
(`sandbox/`), sans nouvelle sollicitation de l'IA. Le problème résolu est le *Flexible Job-Shop
Scheduling Problem* (FJSP), via OR-Tools CP-SAT.

## État du projet

Scaffolding précoce. Étapes 1–5, 7 et 8 de la roadmap (§8) sont implémentées, dans un ordre qui
dévie volontairement de l'ordre listé (l'Étape 6, la boucle de réparation bornée, est sautée pour
l'instant — voir §8 de la note de cadrage pour le détail des dépendances). En dehors de `dsl/`,
`validation_engine/`, `solveur_reference/`, `generation/`, `solver_store/`, `sandbox/`,
`adapters/` et `api/`, chaque répertoire de module ne contient pour l'instant qu'un
`README.md` décrivant son contenu prévu (`diagnostics/`, `dashboard/`, `docs/`).

Rien dans `solver_store/`, `sandbox/`, `api/` ou `adapters/` n'a encore été exécuté en conditions
réelles (pas de Docker ni de connexion LLM disponibles au moment de leur écriture) — voir
[CLAUDE.md](CLAUDE.md) pour le détail de ce qui reste à vérifier.

## Prérequis

- [uv](https://docs.astral.sh/uv/) — gestionnaire de dépendances et d'environnements Python du
  projet (voir *Environnement Python* ci-dessous pour le choix par rapport à Poetry). Aucune
  version de Python n'est requise au préalable : `uv` télécharge et gère lui-même l'interpréteur
  épinglé par `.python-version`.
- Docker (uniquement pour l'exécution en sandbox et les tests d'intégration correspondants —
  ces tests sont automatiquement ignorés si Docker n'est pas disponible)
- Une clé API Anthropic ou OpenAI (uniquement pour appeler le générateur — `generation/`)

## Environnement Python

La gestion de dépendances utilise **uv** plutôt que Poetry : le projet expose déjà un
`pyproject.toml` au format standard PEP 621 (`[project]`, backend `hatchling`), qu'uv consomme
directement sans table `[tool.poetry]` propriétaire ni migration de format.

- `.python-version` épingle l'interpréteur à **3.11** — `ortools` ne publie pas encore de wheel
  pour les versions de Python plus récentes (vérifié : la résolution échoue sous Python 3.14, la
  version présente sur ce poste). `uv` télécharge et utilise 3.11 automatiquement, indépendamment
  du Python système.
- `uv.lock` fige les versions exactes de toutes les dépendances, y compris transitives — il est
  versionné dans le dépôt et doit être régénéré (`uv lock`) après toute modification des
  dépendances dans `pyproject.toml`.
- Les dépendances cœur (`ortools`, `pydantic`, `fastapi`, `pytest`) sont épinglées avec `==` dans
  `pyproject.toml` ; les autres dépendances gardent une borne `>=`.

### Reconstruire l'environnement complet (une seule commande)

```bash
uv sync --all-extras
```

## Installation

```bash
uv sync                 # dépendances de base (pydantic, ortools, fastapi, httpx)
uv sync --extra dev     # + pytest, uvicorn
uv sync --extra llm     # + anthropic, openai — pour appeler le générateur
uv sync --extra sandbox # + docker SDK — pour l'exécution en conteneur
uv sync --all-extras    # tout en une fois
```

`pyproject.toml` déclare `pythonpath = ["."]` pour pytest : les tests et les scripts lancés en
`python -m` résolvent les packages du dépôt sans installation préalable, une fois l'environnement
synchronisé.

## Commandes

```bash
# Tests
uv run pytest                                              # suite complète (tests Docker auto-ignorés si Docker indisponible)
uv run pytest tests/unit                                   # tests de couche 1 uniquement — ni OR-Tools ni Docker requis
uv run pytest tests/integration/test_solveur_reference.py  # un seul fichier
uv run pytest tests/unit/test_cascade.py::<nom_test>       # un seul test

# Lint / format (ruff)
uv run ruff check .            # lint
uv run ruff format --check .   # vérifie le formatage sans modifier (enlever --check pour appliquer)

# Scripts de développement (toujours en module, depuis la racine du dépôt)
uv run python -m scripts.generer_banc_synthetique          # régénère le banc synthétique après modification de construction_inverse.py
uv run python -m scripts.benchmarker_solveur_reference     # solveur de référence : makespan vs optimum + temps de résolution
uv run python -m scripts.mesurer_taux_succes_generation    # taux de succès du générateur tir unique (nécessite .[llm] + clé API)
uv run python -m scripts.enregistrer_solveur_reference     # enregistre le solveur de référence dans le store (idempotent)
uv run python -m scripts.demo_bout_en_bout                 # démo bout en bout Étape 8 (adaptateur → ingestion → exécution → planning → audit)

# API
uv run uvicorn api.app:app --reload                 # documentation OpenAPI disponible sur /docs

# Sandbox (setup d'environnement, jamais déclenché par le code applicatif)
docker build -t prisme-sandbox sandbox/container/
```

Lint et format : `ruff` (voir `[tool.ruff]` dans `pyproject.toml`). Aucun type-checker configuré.

## Intégration continue

`.github/workflows/ci.yml` (PH0-T4) tourne sur chaque push vers `main` et chaque Pull Request :
installation via `uv sync --all-extras`, puis `ruff check`, `ruff format --check`, et `pytest`
(suite complète — les runners GitHub `ubuntu-latest` embarquent Docker, donc les tests sandbox et
bout-en-bout s'exécutent réellement, pas seulement en `skip`). Un run rouge doit bloquer la fusion
(voir CONTRIBUTING.md pour activer ce garde-fou dans la protection de branche).

### Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `PRISME_LLM_PROVIDER` | Fournisseur LLM utilisé par `generation/` | `anthropic` |
| `PRISME_LLM_MODEL` | Modèle à utiliser chez ce fournisseur | dépend du fournisseur |

## Arborescence

```
dsl/                  Modèle pivot T-R-C-O — Tâches, Ressources, Contraintes, Objectifs (Étape 1)
validation_engine/    Cascade de validation : faisabilité → banc synthétique → cas de référence (Étapes 2, 3, 5)
solveur_reference/    Solveur CP-SAT écrit à la main, cible de fidélité pour `generation/` (hors roadmap, avant Étape 4)
generation/           Générateur tir unique piloté par LLM → code CP-SAT (Étape 4 ; boucle de réparation Étape 6 non faite)
solver_store/         Store des solveurs validés, code figé (Étape 7)
sandbox/              Exécution éphémère en conteneur jetable (Étape 7)
api/                  API PRISME — ingestion, exécution, canaux opérationnel/audit (Étape 8)
adapters/             Adaptateurs ERP (couche anti-corruption vers T-R-C-O) (Étape 8)
diagnostics/          Boucle d'amélioration — attribution code / données / DSL (pas encore implémenté)
dashboard/            Tableau de bord, alertes, validation humaine (pas encore implémenté)
tests/                Tests par couche : code manuel, propriétés du planning, stabilité de génération (§6)
docs/                 Documentation d'architecture et spécification du DSL (pas encore rédigée)
scripts/              Scripts utilitaires (dev, CI, génération de bancs synthétiques)
```

## Roadmap

Voir §8 de la note de cadrage. Ordre de construction prévu : DSL → vérificateur de faisabilité →
banc synthétique → générateur (tir unique) → cascade de validation → boucle
generate-test-repair → store + sandbox → API + adaptateur ERP → tableau de bord.

L'ordre de construction réel a dévié de cet ordre (cascade de validation avant le générateur,
Étape 6 sautée, API avant la boucle de réparation) — voir la section « Build order » de
[CLAUDE.md](CLAUDE.md) pour le détail et les raisons de chaque écart.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour la convention de branches et le processus de Pull
Request.

## Documentation

- [`PRISME_Note_de_Cadrage (2).md`](<./PRISME_Note_de_Cadrage (2).md>) — spécification de référence
- [`PRISME_Plan_Developpement.md`](./PRISME_Plan_Developpement.md) — plan de développement détaillé, par tickets
- [CLAUDE.md](CLAUDE.md) — guide d'architecture et de commandes pour Claude Code
- [CONTRIBUTING.md](CONTRIBUTING.md) — convention de branches et de contribution
