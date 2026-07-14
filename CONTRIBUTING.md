# Contribuer à PRISME

## Convention de branches

- **`main` est protégée** : pas de push direct. Toute modification passe par une Pull Request
  avec au moins une revue et une CI verte avant fusion.
  Sur GitHub : *Settings → Branches → Add branch protection rule* sur `main`, avec
  *Require a pull request before merging* et *Require status checks to pass before merging* — coche
  le check `test` (job défini dans `.github/workflows/ci.yml`, PH0-T4) comme requis.
- Toute modification se fait sur une **branche de fonctionnalité**, créée depuis `main` à jour :

  ```bash
  git checkout main
  git pull
  git checkout -b <type>/<sujet-court>
  ```

- **Nommage** : `<type>/<sujet-court-en-kebab-case>`, où `<type>` est :

  | Préfixe | Usage |
  |---|---|
  | `feature/` | Nouvelle fonctionnalité ou étape de la roadmap (ex. `feature/cascade-validation`) |
  | `fix/` | Correction de bug |
  | `docs/` | Documentation seule (README, CLAUDE.md, `docs/`) |
  | `chore/` | Outillage, dépendances, CI, scripts — sans impact fonctionnel |
  | `refactor/` | Réécriture sans changement de comportement |

- **Commits** : messages courts à l'impératif, en français, qui disent *pourquoi* plutôt que
  *quoi* quand ce n'est pas évident (ex. `Ajoute la vérification de compatibilité machine-tâche`
  plutôt que `Modifie feasibility_checker.py`).
- **Fusion** : une fois la revue et la CI passées, fusionner via *Squash and merge* pour garder
  un historique linéaire sur `main` — une entrée par Pull Request.
- Supprimer la branche de fonctionnalité après fusion (option GitHub *Automatically delete head
  branches*, à activer une fois dans les réglages du dépôt).

## Avant d'ouvrir une Pull Request

- `uv run pytest` passe localement (voir [README.md](README.md#commandes) pour les sous-ensembles
  utiles sans OR-Tools/Docker), et `uv run ruff check .` / `uv run ruff format --check .` sont
  propres — la CI (`.github/workflows/ci.yml`) applique les trois.
- Si une dépendance a changé dans `pyproject.toml`, `uv.lock` a été régénéré (`uv lock`) et
  committé.
- Toute nouvelle brique respecte la philosophie de validation par couches (§6 de la
  [note de cadrage](<./PRISME_Note_de_Cadrage (2).md>)) — pas de test unitaire classique sur du
  code généré par IA.
- Le [CLAUDE.md](CLAUDE.md) est mis à jour si l'architecture ou les commandes changent.
