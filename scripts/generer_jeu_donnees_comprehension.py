"""Génère un jeu de données synthétiques pour tester l'agent de compréhension.

Crée des paires (données_brutes_erp, instance_trco_attendue) dans différents
formats pour mesurer le taux de succès de la traduction ERP → T-R-C-O.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExempleTraduction:
    """Une paire (input_erp, output_trco_attendu) pour tester l'agent."""

    id: str
    format_source: str  # "csv", "json_erp", "texte_libre", "json_simple"
    donnees_brutes: str
    instance_trco_attendue: dict[str, Any]
    difficulte: str  # "simple", "moyen", "complexe"
    caracteristiques: list[str]  # ["precedences", "multi_ressources", etc.]


# ============================================================================
# Générateurs par format
# ============================================================================


def generer_csv_simple(seed: int) -> ExempleTraduction:
    """Génère un exemple CSV basique."""
    random.seed(seed)

    n_taches = random.randint(2, 5)
    taches = [f"Task_{i+1}" for i in range(n_taches)]
    ressources = [f"Resource_{chr(65+i)}" for i in range(n_taches)]
    durees_h = [round(random.uniform(0.5, 4.0), 1) for _ in range(n_taches)]

    # CSV
    lignes_csv = ["Task,Resource,Duration_Hours"]
    for t, r, d in zip(taches, ressources, durees_h):
        lignes_csv.append(f"{t},{r},{d}")

    # T-R-C-O attendu
    instance = {
        "taches": [{"id": t, "nom": t.replace("_", " ")} for t in taches],
        "ressources": [{"id": r, "nom": f"{r} Station"} for r in ressources],
        "contraintes": [
            {
                "type": "compatibilite_ressource_tache",
                "tache": t,
                "ressource": r,
                "duree": int(d * 60),
            }
            for t, r, d in zip(taches, ressources, durees_h)
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    return ExempleTraduction(
        id=f"csv_simple_{seed}",
        format_source="csv",
        donnees_brutes="\n".join(lignes_csv),
        instance_trco_attendue=instance,
        difficulte="simple",
        caracteristiques=["une_ressource_par_tache", "pas_de_precedence"],
    )


def generer_json_erp_avec_precedences(seed: int) -> ExempleTraduction:
    """Génère un JSON ERP avec work orders et précédences."""
    random.seed(seed)

    n_wo = random.randint(3, 6)
    work_orders = []

    for i in range(n_wo):
        wo = {
            "wo_id": 1000 + i,
            "operation": f"Operation_{chr(65+i)}",
            "estimated_time_min": random.randint(15, 120),
            "priority": random.randint(1, 3),
        }

        # Ajouter précédence sur le WO précédent (chaîne)
        if i > 0:
            wo["must_finish_before_wo"] = 1000 + i

        work_orders.append(wo)

    workstations = [
        {"station_id": f"WS_{chr(65+i)}", "station_name": f"Workstation {chr(65+i)}"}
        for i in range(n_wo)
    ]

    donnees_erp = {"work_orders": work_orders, "workstations": workstations}

    # T-R-C-O attendu
    taches = [
        {"id": f"WO_{wo['wo_id']}", "nom": wo["operation"], "priorite": wo["priority"]}
        for wo in work_orders
    ]

    ressources = [
        {"id": ws["station_id"], "nom": ws["station_name"]} for ws in workstations
    ]

    contraintes = []

    # Précédences (chaîne)
    for i in range(1, n_wo):
        contraintes.append(
            {
                "type": "precedence",
                "avant": f"WO_{1000 + i - 1}",
                "apres": f"WO_{1000 + i}",
            }
        )

    # Compatibilités
    for i, wo in enumerate(work_orders):
        contraintes.append(
            {
                "type": "compatibilite_ressource_tache",
                "tache": f"WO_{wo['wo_id']}",
                "ressource": f"WS_{chr(65+i)}",
                "duree": wo["estimated_time_min"],
            }
        )

    instance = {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    return ExempleTraduction(
        id=f"json_erp_precedences_{seed}",
        format_source="json_erp",
        donnees_brutes=json.dumps(donnees_erp, indent=2),
        instance_trco_attendue=instance,
        difficulte="moyen",
        caracteristiques=["precedences_chaine", "priorities", "une_ressource_par_tache"],
    )


def generer_texte_libre_francais(seed: int) -> ExempleTraduction:
    """Génère une description en français naturel."""
    random.seed(seed)

    operations = [
        ("Découpe", "laser", 2.0),
        ("Soudure", "poste de soudure", 1.5),
        ("Peinture", "cabine de peinture", 3.0),
        ("Assemblage", "table d'assemblage", 2.5),
    ]

    n_ops = random.randint(2, 4)
    ops_choisies = random.sample(operations, n_ops)

    # Texte naturel
    lignes = [f"Voici les {n_ops} opérations à effectuer :"]
    for i, (op, ressource, duree_h) in enumerate(ops_choisies):
        duree_min = int(duree_h * 60)
        lignes.append(f"- {op} ({duree_min} minutes) sur {ressource}")

    # Ajouter précédences implicites
    if n_ops >= 2:
        lignes.append("")
        lignes.append(
            f"IMPORTANT : {ops_choisies[1][0]} ne peut commencer qu'après {ops_choisies[0][0]}."
        )

    if n_ops >= 3:
        lignes.append(
            f"{ops_choisies[2][0]} doit être faite après {ops_choisies[1][0]}."
        )

    # T-R-C-O attendu
    taches = [
        {"id": f"T_{op.upper()}", "nom": op} for op, _, _ in ops_choisies
    ]

    ressources = [
        {"id": f"R_{op.upper()[:3]}", "nom": ressource.capitalize()}
        for op, ressource, _ in ops_choisies
    ]

    contraintes = []

    # Compatibilités
    for i, (op, _, duree_h) in enumerate(ops_choisies):
        contraintes.append(
            {
                "type": "compatibilite_ressource_tache",
                "tache": f"T_{op.upper()}",
                "ressource": f"R_{op.upper()[:3]}",
                "duree": int(duree_h * 60),
            }
        )

    # Précédences (chaîne si n_ops >= 2)
    for i in range(1, n_ops):
        contraintes.append(
            {
                "type": "precedence",
                "avant": f"T_{ops_choisies[i-1][0].upper()}",
                "apres": f"T_{ops_choisies[i][0].upper()}",
            }
        )

    instance = {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    return ExempleTraduction(
        id=f"texte_libre_{seed}",
        format_source="texte_libre",
        donnees_brutes="\n".join(lignes),
        instance_trco_attendue=instance,
        difficulte="moyen",
        caracteristiques=["langage_naturel", "precedences_implicites"],
    )


def generer_json_multi_ressources(seed: int) -> ExempleTraduction:
    """Génère un cas avec plusieurs ressources compatibles par tâche (vrai FJSP)."""
    random.seed(seed)

    n_taches = random.randint(2, 4)
    n_ressources = random.randint(3, 6)

    taches_data = []
    for i in range(n_taches):
        # Chaque tâche peut être faite sur 2-3 ressources
        ressources_compatibles = random.sample(
            range(n_ressources), k=random.randint(2, min(3, n_ressources))
        )

        durees = {}
        for r_idx in ressources_compatibles:
            durees[f"R{r_idx+1}"] = random.randint(30, 120)

        taches_data.append(
            {"id": f"T{i+1}", "nom": f"Task {i+1}", "durations": durees}
        )

    ressources_data = [
        {"id": f"R{i+1}", "nom": f"Resource {i+1}"} for i in range(n_ressources)
    ]

    # Format JSON simple
    donnees = {"tasks": [], "resources": ressources_data}

    for t in taches_data:
        task_entry = {
            "task_id": t["id"],
            "task_name": t["nom"],
            "compatible_resources": [
                {"resource_id": r_id, "duration_min": dur}
                for r_id, dur in t["durations"].items()
            ],
        }
        donnees["tasks"].append(task_entry)

    # T-R-C-O attendu
    taches = [{"id": t["id"], "nom": t["nom"]} for t in taches_data]
    ressources = ressources_data

    contraintes = []
    for t in taches_data:
        for r_id, dur in t["durations"].items():
            contraintes.append(
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": t["id"],
                    "ressource": r_id,
                    "duree": dur,
                }
            )

    instance = {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    return ExempleTraduction(
        id=f"json_multi_ressources_{seed}",
        format_source="json_simple",
        donnees_brutes=json.dumps(donnees, indent=2),
        instance_trco_attendue=instance,
        difficulte="complexe",
        caracteristiques=["multi_ressources", "fjsp_flexible"],
    )


# ============================================================================
# Génération du catalogue
# ============================================================================


def generer_catalogue(n_par_format: int = 10) -> list[ExempleTraduction]:
    """Génère un catalogue d'exemples pour tous les formats."""
    exemples = []

    print(f"🏭 Génération de {n_par_format} exemples par format...")

    # CSV simple
    for i in range(n_par_format):
        exemples.append(generer_csv_simple(seed=1000 + i))

    # JSON ERP avec précédences
    for i in range(n_par_format):
        exemples.append(generer_json_erp_avec_precedences(seed=2000 + i))

    # Texte libre français
    for i in range(n_par_format):
        exemples.append(generer_texte_libre_francais(seed=3000 + i))

    # JSON multi-ressources (FJSP)
    for i in range(n_par_format):
        exemples.append(generer_json_multi_ressources(seed=4000 + i))

    return exemples


def sauvegarder_catalogue(
    exemples: list[ExempleTraduction], chemin: Path
) -> None:
    """Sauvegarde le catalogue en JSON."""
    chemin.parent.mkdir(parents=True, exist_ok=True)

    catalogue_data = {
        "metadata": {
            "total_exemples": len(exemples),
            "formats": list({ex.format_source for ex in exemples}),
            "difficultes": list({ex.difficulte for ex in exemples}),
        },
        "exemples": [
            {
                "id": ex.id,
                "format_source": ex.format_source,
                "difficulte": ex.difficulte,
                "caracteristiques": ex.caracteristiques,
                "donnees_brutes": ex.donnees_brutes,
                "instance_trco_attendue": ex.instance_trco_attendue,
            }
            for ex in exemples
        ],
    }

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(catalogue_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Catalogue sauvegardé : {chemin}")


def afficher_statistiques(exemples: list[ExempleTraduction]) -> None:
    """Affiche les statistiques du catalogue généré."""
    from collections import Counter

    print("\n📊 STATISTIQUES DU CATALOGUE")
    print("=" * 70)

    print(f"\n🔢 Total : {len(exemples)} exemples")

    print("\n📋 Par format :")
    formats = Counter(ex.format_source for ex in exemples)
    for fmt, count in formats.most_common():
        print(f"   - {fmt:20s} : {count:3d}")

    print("\n🎯 Par difficulté :")
    difficultes = Counter(ex.difficulte for ex in exemples)
    for diff, count in difficultes.most_common():
        print(f"   - {diff:20s} : {count:3d}")

    print("\n🏷️  Caractéristiques présentes :")
    toutes_carac = []
    for ex in exemples:
        toutes_carac.extend(ex.caracteristiques)

    carac_counter = Counter(toutes_carac)
    for carac, count in carac_counter.most_common(10):
        print(f"   - {carac:30s} : {count:3d}")

    print("\n" + "=" * 70)


# ============================================================================
# Main
# ============================================================================


def main():
    """Point d'entrée du script."""
    print("\n" + "=" * 70)
    print("  GÉNÉRATION DE JEU DE DONNÉES - AGENT DE COMPRÉHENSION")
    print("=" * 70)

    # Générer
    exemples = generer_catalogue(n_par_format=15)

    # Statistiques
    afficher_statistiques(exemples)

    # Sauvegarder
    chemin_sortie = (
        Path(__file__).parent.parent
        / "validation_engine"
        / "agent_comprehension_bench"
        / "catalogue_traductions.json"
    )

    sauvegarder_catalogue(exemples, chemin_sortie)

    print(f"\n✅ {len(exemples)} exemples générés et sauvegardés")
    print(f"📂 Fichier : {chemin_sortie}")
    print("\n💡 Utilisation suggérée :")
    print("   - Tester l'agent : scripts/tester_agent_comprehension.py")
    print("   - Mesurer taux de succès : comparer output réel vs attendu")
    print("   - Benchmark de traduction : mesurer précision par format\n")


if __name__ == "__main__":
    main()
