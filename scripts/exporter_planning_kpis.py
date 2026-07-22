"""Convertit un planning au format interne PRISME (operations avec
tache/ressource/debut, cf. dsl/schema/planning.py) vers un format d'export
plus lisible pour un consommateur externe : identifiant de planning, une
entree par tache avec sa fin calculee et son statut, et des KPI (makespan,
taux d'utilisation par machine en % du makespan).

Ce n'est pas le format retourne par api/routes/planning.py (canal
operationnel officiel, §5.1/§5.5) : c'est un export a la demande, pense pour
un consommateur externe (dashboard, rapport) qui veut start/end/status par
tache plutot que debut+duree separes.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))


def exporter(
    chemin_planning: Path,
    chemin_instance: Path,
    chemin_sortie: Path,
    planning_id: str,
) -> dict:
    from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO

    with open(chemin_instance, encoding="utf-8") as f:
        instance = InstanceTRCO.model_validate(json.load(f))

    duree_map: dict[tuple[str, str], int] = {
        (c.tache, c.ressource): c.duree
        for c in instance.contraintes
        if isinstance(c, CompatibiliteRessourceTache)
    }

    with open(chemin_planning, encoding="utf-8") as f:
        donnees_planning = json.load(f)

    operations = donnees_planning["planning"]["operations"]
    makespan = donnees_planning["makespan"]

    taches_export = []
    temps_occupe_par_ressource: dict[str, int] = defaultdict(int)

    for op in operations:
        duree = duree_map[(op["tache"], op["ressource"])]
        fin = op["debut"] + duree
        taches_export.append(
            {
                "id": op["tache"],
                "resource": op["ressource"],
                "start": op["debut"],
                "end": fin,
                "status": "scheduled",
            }
        )
        temps_occupe_par_ressource[op["ressource"]] += duree

    utilisation = {
        ressource: round(100 * temps_occupe / makespan, 1) if makespan else 0.0
        for ressource, temps_occupe in temps_occupe_par_ressource.items()
    }

    export = {
        "planning_id": planning_id,
        "makespan": makespan,
        "tasks": sorted(taches_export, key=lambda t: (t["start"], t["id"])),
        "kpis": {
            "makespan": makespan,
            "machine_utilization": dict(sorted(utilisation.items())),
        },
    }

    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)

    return export


def main() -> None:
    export = exporter(
        chemin_planning=projet_root / "planning_genere_2165.json",
        chemin_instance=projet_root / "greensig_instance_trco_simulee.json",
        chemin_sortie=projet_root / "planning_export_2165.json",
        planning_id="PLN-GREENSIG-2165-GENETIC",
    )
    print(f"Export : {len(export['tasks'])} taches, makespan={export['makespan']}")
    print(f"Fichier : {projet_root / 'planning_export_2165.json'}")


if __name__ == "__main__":
    main()
