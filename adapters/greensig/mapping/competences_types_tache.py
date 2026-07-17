"""Correspondance type de tâche → compétence(s) requise(s) (§5.4).

Aucune table du schéma GreenSIG source ne relie `api_planification_typetache`
à `api_users_competence` — juste des noms proches, pas de correspondance
1:1, et souvent aucune correspondance du tout (vérifié sur
`backup_20260503.sql` : 41 types de tâche, 30 compétences, la plupart sans
équivalent évident). Un rapprochement automatique par similarité de texte
serait exactement le risque d'hallucination diagnostiqué côté
`agent_comprehension` (§5.4 bis), simplement déplacé dans du code Python —
donc : table curatée à la main, volontairement incomplète, à compléter avec
l'équipe métier GreenSIG plutôt qu'à deviner.

Chaque tuple de compétences est traité comme des synonymes d'une même
compétence réelle — hypothèse à confirmer avec GreenSIG, pas une certitude
métier (ex. "Désherbage" et "Desherbage manuel et mecanique" semblent être
la même compétence saisie deux fois, à l'accent/formulation près).

Type de tâche non présent ici → `translator.traduire` retombe sur
l'affectation historique (`equipes_ids`), voir `regles.md`.
"""

from __future__ import annotations

COMPETENCES_PAR_TYPE_TACHE: dict[int, frozenset[int]] = {
    1: frozenset({23, 11}),  # Nettoyage → "Nettoyage général" / "Nettoyage general" (doublon accent/typo)
    2: frozenset({21, 5}),  # Binage → "Binage" / "Binage des sols"
    3: frozenset({6}),  # Confection des cuvettes
    5: frozenset({9}),  # Arrosage
    18: frozenset({17, 1}),  # Tonte → "Tondeuse" / "Utilisation de tondeuse"
    20: frozenset({20, 4}),  # Désherbage → "Désherbage" / "Desherbage manuel et mecanique"
    136: frozenset({22, 8}),  # Taille de décoration (doublon accent)
}
