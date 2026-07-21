"""Validation statique par AST du code généré (§5.3, §5.6) — le tout premier
garde-fou, avant toute exécution, jamais après.

Approche par liste blanche, pas liste noire : seuls les imports
explicitement énumérés sont autorisés ; tout le reste — imports, appels,
attributs susceptibles de servir à une évasion (accès à `__builtins__`, aux
sous-classes de `object`, etc.) — est rejeté par défaut, plutôt que
d'essayer d'énumérer a priori tout ce qui est dangereux.

Ceci reste une vérification de code *texte*, pas une exécution isolée : la
véritable isolation (réseau coupé, privilèges restreints, conteneur jetable)
est l'Étape 7 (`sandbox/`). Ne jamais considérer cette validation seule
comme une garantie de sécurité suffisante pour exécuter du code non fiable
hors d'un environnement de développement contrôlé.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

PREFIXES_AUTORISES = (
    "__future__",
    "collections",
    "dataclasses",
    "typing",
    "ortools",
    "dsl",
    # `random`/`math` : uniquement utiles à un algorithme non-CP-SAT recommandé
    # par l'agent Benchmarker (génétique, ACO, recuit simulé...) — voir
    # generation/prompts/generation_solveur.md. Aucun des deux ne permet
    # d'accès réseau/fichier/système, donc pas de risque de sécurité ajouté.
    "random",
    "math",
)


def _prefixe_autorise(chemin: str) -> bool:
    """`chemin` est autorisé s'il est l'un des préfixes, ou un sous-module —
    ce qui couvre aussi bien `import ortools.sat.python.cp_model` que
    `from ortools.sat.python import cp_model` (module = `ortools.sat.python`)."""
    return any(chemin == prefixe or chemin.startswith(f"{prefixe}.") for prefixe in PREFIXES_AUTORISES)


APPELS_INTERDITS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "globals",
        "locals",
        "vars",
        "breakpoint",
    }
)

ATTRIBUTS_INTERDITS = frozenset(
    {
        "__subclasses__",
        "__globals__",
        "__builtins__",
        "__import__",
        "__loader__",
        "__code__",
        "__bases__",
        "__mro__",
    }
)


@dataclass(frozen=True)
class ResultatValidationStatique:
    valide: bool
    violations: tuple[str, ...]


def valider_code_genere(code: str) -> ResultatValidationStatique:
    try:
        arbre = ast.parse(code)
    except SyntaxError as erreur:
        return ResultatValidationStatique(False, (f"erreur de syntaxe : {erreur}",))

    violations: list[str] = []

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if not _prefixe_autorise(alias.name):
                    violations.append(f"import interdit : {alias.name!r}")
        elif isinstance(noeud, ast.ImportFrom):
            module = noeud.module or ""
            if not _prefixe_autorise(module):
                violations.append(f"import interdit : {module!r}")
        elif isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name):
            if noeud.func.id in APPELS_INTERDITS:
                violations.append(f"appel interdit : {noeud.func.id!r}")
        elif isinstance(noeud, ast.Attribute) and noeud.attr in ATTRIBUTS_INTERDITS:
            violations.append(f"attribut interdit : {noeud.attr!r}")

    return ResultatValidationStatique(valide=not violations, violations=tuple(violations))
