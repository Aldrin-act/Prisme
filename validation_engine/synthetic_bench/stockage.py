"""(Dé)sérialisation JSON des cas du banc synthétique — le format sur disque
du catalogue versionné sous `instances/` (§6.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dsl.schema import InstanceTRCO, Planning

from .construction_inverse import InstanceSynthetique


def vers_dict(cas: InstanceSynthetique) -> dict[str, Any]:
    return {
        "nom": cas.nom,
        "optimum": cas.optimum,
        "instance": cas.instance.model_dump(mode="json"),
        "planning_optimal": cas.planning_optimal.model_dump(mode="json"),
    }


def depuis_dict(donnees: dict[str, Any]) -> InstanceSynthetique:
    return InstanceSynthetique(
        nom=donnees["nom"],
        instance=InstanceTRCO.model_validate(donnees["instance"]),
        planning_optimal=Planning.model_validate(donnees["planning_optimal"]),
        optimum=donnees["optimum"],
    )


def sauvegarder(cas: InstanceSynthetique, dossier: Path) -> Path:
    chemin = dossier / f"{cas.nom}.json"
    chemin.write_text(
        json.dumps(vers_dict(cas), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return chemin


def charger(nom: str, dossier: Path) -> InstanceSynthetique:
    chemin = dossier / f"{nom}.json"
    return depuis_dict(json.loads(chemin.read_text(encoding="utf-8")))
