"""Cas de référence : DSL + planning attendu, écrits à la main (§6.2 brique 3).

Contrairement au banc synthétique (`synthetic_bench/`, construction inverse,
§6.4), l'optimalité n'est pas prouvée par construction ici — c'est un humain
qui décide, une fois, que ce planning précis est la bonne réponse à cette
instance. Ça permet d'attraper des erreurs qu'aucune propriété formelle
(légalité, makespan) ne peut détecter seule : traduire « A avant B » en
« B avant A » peut produire un planning tout aussi faisable et optimal...
pour le mauvais problème (§6.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsl.schema import InstanceTRCO, Planning

DOSSIER_CAS = Path(__file__).resolve().parent / "cases"


@dataclass(frozen=True)
class CasReference:
    nom: str
    description: str
    instance: InstanceTRCO
    planning_attendu: Planning


def _depuis_dict(donnees: dict[str, Any]) -> CasReference:
    return CasReference(
        nom=donnees["nom"],
        description=donnees["description"],
        instance=InstanceTRCO.model_validate(donnees["instance"]),
        planning_attendu=Planning.model_validate(donnees["planning_attendu"]),
    )


def charger_cas_reference(dossier: Path = DOSSIER_CAS) -> list[CasReference]:
    """Charge tous les cas de référence versionnés sous `dossier`, triés par nom."""
    return [
        _depuis_dict(json.loads(chemin.read_text(encoding="utf-8")))
        for chemin in sorted(dossier.glob("*.json"))
    ]
