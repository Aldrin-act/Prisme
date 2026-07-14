"""Exécution du code généré, jamais sans passer par la validation statique
d'abord (§5.3).

Avertissement de portée : ceci n'est **pas** le bac à sable éphémère
(Étape 7, `sandbox/`) — juste un espace de noms d'exécution dédié pour ce
premier contact avec l'IA (Étape 4). `exec()` n'offre aucune isolation
réelle par lui-même ; la seule barrière ici est la validation statique en
amont. Ne jamais exposer ce chemin à du code non fiable en dehors d'un
environnement de développement contrôlé — voir §5.3, Security posture.
"""

from __future__ import annotations

from generation.validation_statique import valider_code_genere
from validation_engine.cascade import Solveur


class ErreurExecutionGeneree(Exception):
    """Le code a échoué la validation statique, ou ne définit pas `resoudre`."""


def executer_code_genere(code: str) -> Solveur:
    resultat = valider_code_genere(code)
    if not resultat.valide:
        raise ErreurExecutionGeneree(f"validation statique refusée : {'; '.join(resultat.violations)}")

    espace_noms: dict[str, object] = {}
    exec(compile(code, "<solveur_genere>", "exec"), espace_noms)

    solveur = espace_noms.get("resoudre")
    if not callable(solveur):
        raise ErreurExecutionGeneree("le module généré ne définit pas de fonction `resoudre`")

    return solveur
