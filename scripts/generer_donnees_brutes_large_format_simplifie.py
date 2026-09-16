#!/usr/bin/env python
"""Génère des données brutes de grande taille au format simplifié avec compétences.

Ce script crée des instances volumineuses (50-200+ tâches) au format simplifié
avec compétences, similaire à instance_exemple.json mais à grande échelle.

Usage:
    uv run python -m scripts.generer_donnees_brutes_large_format_simplifie
"""

import json
import random
from pathlib import Path
from typing import Any


def _vers_compatibilite_explicite(donnee: dict[str, Any]) -> dict[str, Any]:
    """Remplace `duree_estimee_jours` (tâches) + `competence_requise` (contraintes) par des
    `compatibilite_ressource_tache` explicites — même logique que
    `adapters/competence_derivation.py::deriver_compatibilites_par_competence`, appliquée ici
    au moment de la génération plutôt qu'à l'ingestion (voir même fonction dans
    `scripts/generer_donnees_brutes_format_simplifie.py`)."""
    durees = {t["id"]: t.pop("duree_estimee_jours") for t in donnee["taches"] if "duree_estimee_jours" in t}
    competences_par_ressource = {r["id"]: set(r.get("competences", [])) for r in donnee["ressources"]}

    requises_par_tache: dict[str, set[str]] = {}
    autres_contraintes = []
    for contrainte in donnee["contraintes"]:
        if contrainte["type"] == "competence_requise":
            requises_par_tache.setdefault(contrainte["tache"], set()).add(contrainte["competence"])
        else:
            autres_contraintes.append(contrainte)

    donnee["contraintes"] = autres_contraintes
    for tache_id, requises in requises_par_tache.items():
        for ressource_id, competences in competences_par_ressource.items():
            if requises <= competences:
                donnee["contraintes"].append(
                    {
                        "type": "compatibilite_ressource_tache",
                        "tache": tache_id,
                        "ressource": ressource_id,
                        "duree": durees[tache_id],
                    }
                )
    return donnee


def generer_atelier_mecanique_large(nb_lots: int = 20) -> dict[str, Any]:
    """Génère un atelier mécanique de grande taille.

    Args:
        nb_lots: Nombre de lots à produire (chacun avec ~8-10 opérations)
    """
    phases = ["PREPARATION", "USINAGE", "FORMAGE", "SOUDURE", "FINITION", "PEINTURE", "ASSEMBLAGE", "CONTROLE"]

    competences_par_phase = {
        "PREPARATION": ["decoupe_laser", "decoupe_plasma", "percage"],
        "USINAGE": ["fraisage", "tournage", "ebavurage"],
        "FORMAGE": ["pliage", "emboutissage"],
        "SOUDURE": ["soudure_mig", "soudure_tig", "soudure_robot"],
        "FINITION": ["polissage", "ebavurage"],
        "PEINTURE": ["peinture_cabine", "peinture_tunnel"],
        "ASSEMBLAGE": ["assemblage_manuel", "assemblage_robot"],
        "CONTROLE": ["controle_visuel", "controle_dimensionnel"],
    }

    # Générer les tâches
    taches = []
    contraintes = []
    tache_id_counter = 1

    for lot_num in range(1, nb_lots + 1):
        # Chaque lot passe par 8-10 phases aléatoires
        nb_phases_lot = random.randint(8, 10)
        phases_lot = random.sample(phases, min(nb_phases_lot, len(phases)))

        taches_lot = []
        for phase in phases_lot:
            tache_id = f"T{tache_id_counter:04d}"
            duree = random.randint(1, 3)

            taches.append({"id": tache_id, "nom": f"Lot{lot_num:03d}_{phase}", "duree_estimee_jours": duree})

            # Ajouter compétence requise
            competence = random.choice(competences_par_phase[phase])
            contraintes.append({"type": "competence_requise", "tache": tache_id, "competence": competence})

            taches_lot.append(tache_id)
            tache_id_counter += 1

        # Ajouter précédences linéaires pour ce lot
        for i in range(len(taches_lot) - 1):
            contraintes.append({"type": "precedence", "avant": taches_lot[i], "apres": taches_lot[i + 1]})

    # Générer les ressources (plusieurs par type de compétence)
    ressources = []
    ressource_id_counter = 1

    for phase, competences in competences_par_phase.items():
        for competence in competences:
            # 2-5 ressources par compétence
            nb_ressources = random.randint(2, 5)
            for i in range(1, nb_ressources + 1):
                ressources.append(
                    {
                        "id": f"R{ressource_id_counter:04d}",
                        "nom": f"{competence.replace('_', ' ').title()} #{i}",
                        "competences": [competence],
                    }
                )
                ressource_id_counter += 1

    return {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_assemblage_electronique_large(nb_cartes: int = 30) -> dict[str, Any]:
    """Génère une production électronique de grande taille.

    Args:
        nb_cartes: Nombre de cartes PCB à produire
    """
    phases = [
        "PREP",
        "POSE_CMS_A",
        "REFUSION_A",
        "AOI_A",
        "POSE_CMS_B",
        "REFUSION_B",
        "SOUDURE_THT",
        "TEST_ICT",
        "TEST_FONC",
        "COATING",
        "DEPANEL",
        "PACKAGE",
    ]

    competences_par_phase = {
        "PREP": ["preparation_pcb"],
        "POSE_CMS_A": ["pick_place"],
        "REFUSION_A": ["refusion"],
        "AOI_A": ["inspection_aoi"],
        "POSE_CMS_B": ["pick_place"],
        "REFUSION_B": ["refusion"],
        "SOUDURE_THT": ["soudure_manuelle"],
        "TEST_ICT": ["test_ict"],
        "TEST_FONC": ["test_fonctionnel"],
        "COATING": ["coating"],
        "DEPANEL": ["depanelisation"],
        "PACKAGE": ["packaging"],
    }

    taches = []
    contraintes = []
    tache_id_counter = 1

    for carte_num in range(1, nb_cartes + 1):
        # Chaque carte passe par toutes les phases (workflow complet)
        taches_carte = []

        for phase in phases:
            tache_id = f"T{tache_id_counter:04d}"
            duree = random.randint(1, 2)

            taches.append({"id": tache_id, "nom": f"PCB{carte_num:03d}_{phase}", "duree_estimee_jours": duree})

            # Ajouter compétence requise
            competence = competences_par_phase[phase][0]
            contraintes.append({"type": "competence_requise", "tache": tache_id, "competence": competence})

            taches_carte.append(tache_id)
            tache_id_counter += 1

        # Ajouter précédences linéaires
        for i in range(len(taches_carte) - 1):
            contraintes.append({"type": "precedence", "avant": taches_carte[i], "apres": taches_carte[i + 1]})

    # Générer les ressources
    ressources = []
    ressource_id_counter = 1

    nb_ressources_par_type = {
        "preparation_pcb": 3,
        "pick_place": 6,
        "refusion": 4,
        "inspection_aoi": 5,
        "soudure_manuelle": 10,
        "test_ict": 8,
        "test_fonctionnel": 6,
        "coating": 3,
        "depanelisation": 4,
        "packaging": 8,
    }

    for competence, nb in nb_ressources_par_type.items():
        for i in range(1, nb + 1):
            ressources.append(
                {
                    "id": f"R{ressource_id_counter:04d}",
                    "nom": f"{competence.replace('_', ' ').title()} #{i}",
                    "competences": [competence],
                }
            )
            ressource_id_counter += 1

    return {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_production_agroalimentaire_large(nb_lots: int = 25) -> dict[str, Any]:
    """Génère une production agroalimentaire de grande taille.

    Args:
        nb_lots: Nombre de lots à produire
    """
    phases = [
        "RECEPTION",
        "LAVAGE",
        "TRIAGE",
        "DECOUPE",
        "TRAITEMENT",
        "CUISSON",
        "REFROIDISSEMENT",
        "CONDITIONNEMENT",
        "ETIQUETAGE",
        "CONTROLE",
    ]

    competences_par_phase = {
        "RECEPTION": ["reception_matieres"],
        "LAVAGE": ["lavage_industriel"],
        "TRIAGE": ["triage_qualite"],
        "DECOUPE": ["decoupe_automatique", "decoupe_manuelle"],
        "TRAITEMENT": ["traitement_thermique", "traitement_chimique"],
        "CUISSON": ["cuisson_four", "cuisson_vapeur"],
        "REFROIDISSEMENT": ["refroidissement_rapide"],
        "CONDITIONNEMENT": ["conditionnement_automatique", "conditionnement_manuel"],
        "ETIQUETAGE": ["etiquetage_automatique"],
        "CONTROLE": ["controle_qualite_alimentaire"],
    }

    taches = []
    contraintes = []
    tache_id_counter = 1

    for lot_num in range(1, nb_lots + 1):
        # Chaque lot suit le workflow complet
        taches_lot = []

        for phase in phases:
            tache_id = f"T{tache_id_counter:04d}"
            duree = random.randint(1, 4)  # Durées plus variables

            taches.append({"id": tache_id, "nom": f"Lot{lot_num:03d}_{phase}", "duree_estimee_jours": duree})

            # Ajouter compétence requise
            competence = random.choice(competences_par_phase[phase])
            contraintes.append({"type": "competence_requise", "tache": tache_id, "competence": competence})

            taches_lot.append(tache_id)
            tache_id_counter += 1

        # Précédences linéaires
        for i in range(len(taches_lot) - 1):
            contraintes.append({"type": "precedence", "avant": taches_lot[i], "apres": taches_lot[i + 1]})

    # Générer les ressources
    ressources = []
    ressource_id_counter = 1

    for phase, competences in competences_par_phase.items():
        for competence in competences:
            nb_ressources = random.randint(2, 6)
            for i in range(1, nb_ressources + 1):
                ressources.append(
                    {
                        "id": f"R{ressource_id_counter:04d}",
                        "nom": f"{competence.replace('_', ' ').title()} #{i}",
                        "competences": [competence],
                    }
                )
                ressource_id_counter += 1

    return {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_imprimerie_large(nb_commandes: int = 15) -> dict[str, Any]:
    """Génère une imprimerie de grande taille.

    Args:
        nb_commandes: Nombre de commandes à produire
    """
    phases = [
        "PREPRESSE",
        "GRAVURE",
        "CALAGE",
        "IMPRESSION_1C",
        "IMPRESSION_2C",
        "IMPRESSION_3C",
        "IMPRESSION_4C",
        "SECHAGE",
        "DECOUPE",
        "PLIAGE",
        "RELIURE",
        "FINITION",
    ]

    competences_par_phase = {
        "PREPRESSE": ["pao", "montage"],
        "GRAVURE": ["gravure_ctp"],
        "CALAGE": ["calage_presse"],
        "IMPRESSION_1C": ["impression_offset"],
        "IMPRESSION_2C": ["impression_offset"],
        "IMPRESSION_3C": ["impression_offset"],
        "IMPRESSION_4C": ["impression_offset"],
        "SECHAGE": ["sechage_uv", "sechage_air"],
        "DECOUPE": ["decoupe_massicot"],
        "PLIAGE": ["pliage_automatique"],
        "RELIURE": ["reliure_piqure", "reliure_colle"],
        "FINITION": ["pelliculage", "vernis"],
    }

    taches = []
    contraintes = []
    tache_id_counter = 1

    for cmd_num in range(1, nb_commandes + 1):
        # Certaines commandes sont plus complexes que d'autres
        nb_phases = random.randint(8, 12)
        phases_cmd = random.sample(phases, min(nb_phases, len(phases)))

        taches_cmd = []
        for phase in phases_cmd:
            tache_id = f"T{tache_id_counter:04d}"
            duree = random.randint(1, 3)

            taches.append({"id": tache_id, "nom": f"Cmd{cmd_num:03d}_{phase}", "duree_estimee_jours": duree})

            competence = random.choice(competences_par_phase[phase])
            contraintes.append({"type": "competence_requise", "tache": tache_id, "competence": competence})

            taches_cmd.append(tache_id)
            tache_id_counter += 1

        # Précédences linéaires
        for i in range(len(taches_cmd) - 1):
            contraintes.append({"type": "precedence", "avant": taches_cmd[i], "apres": taches_cmd[i + 1]})

    # Ressources
    ressources = []
    ressource_id_counter = 1

    for phase, competences in competences_par_phase.items():
        for competence in competences:
            nb_ressources = random.randint(1, 4)
            for i in range(1, nb_ressources + 1):
                ressources.append(
                    {
                        "id": f"R{ressource_id_counter:04d}",
                        "nom": f"{competence.replace('_', ' ').title()} #{i}",
                        "competences": [competence],
                    }
                )
                ressource_id_counter += 1

    return {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def main() -> None:
    """Génère toutes les données brutes large au format simplifié."""
    # Seed pour reproductibilité
    random.seed(42)

    print("Génération des données brutes large au format simplifié...\n")

    donnees = {
        "atelier_mecanique_large": generer_atelier_mecanique_large(nb_lots=20),
        "assemblage_electronique_large": generer_assemblage_electronique_large(nb_cartes=30),
        "production_agroalimentaire_large": generer_production_agroalimentaire_large(nb_lots=25),
        "imprimerie_large": generer_imprimerie_large(nb_commandes=15),
    }
    donnees = {nom: _vers_compatibilite_explicite(donnee) for nom, donnee in donnees.items()}

    # Créer le répertoire de destination
    output_dir = Path("data/donnees_brutes_large/format_simplifie")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Générer chaque fichier
    for nom, donnee in donnees.items():
        output_path = output_dir / f"{nom}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(donnee, f, indent=2, ensure_ascii=False)

        nb_taches = len(donnee["taches"])
        nb_ressources = len(donnee["ressources"])
        nb_contraintes = len(donnee["contraintes"])

        print(f"[OK] {nom}:")
        print(f"     - {nb_taches} taches")
        print(f"     - {nb_ressources} ressources")
        print(f"     - {nb_contraintes} contraintes")
        print(f"     -> {output_path}\n")

    # Créer un README
    readme_path = output_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            """# Données Brutes Large au Format Simplifié

Ce répertoire contient des données brutes de **grande taille** (50-360+ tâches) au format simplifié,
avec compatibilité ressource-tâche déjà explicite (durée comprise).

## Fichiers générés

"""
        )

        for nom, donnee in donnees.items():
            nb_taches = len(donnee["taches"])
            nb_ressources = len(donnee["ressources"])
            f.write(f"- **{nom}**: {nb_taches} tâches, {nb_ressources} ressources\n")

        f.write(
            """
## Format

Identique au format simplifié standard (voir `instance_exemple.json`):

```json
{
  "taches": [
    {"id": "T0001", "nom": "Lot001_PREPARATION"}
  ],
  "ressources": [
    {"id": "R0001", "nom": "Decoupe Laser #1"}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "T0001", "apres": "T0002"},
    {"type": "compatibilite_ressource_tache", "tache": "T0001", "ressource": "R0001", "duree": 2}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

## Différences avec les données brutes "normales"

**Données normales** (`data/donnees_brutes/format_simplifie/`):
- Instances petites à moyennes (2-10 tâches)
- Pour tests rapides, prototypage, démonstrations

**Données large** (ce répertoire):
- Instances volumineuses (50-360+ tâches)
- Pour tests de performance, benchmarks, algorithmes heuristiques
- Générées procéduralement avec seed aléatoire (seed=42 pour reproductibilité)

## Utilisation

Ces données permettent de tester:
1. **Scalabilité** du système de génération de solveur
2. **Choix d'algorithme** (CP-SAT vs heuristiques) par le Benchmarker
3. **Performance** des solveurs générés sur problèmes réalistes
4. **Limites** du sandbox et timeouts

## Regénération

```bash
uv run python -m scripts.generer_donnees_brutes_large_format_simplifie
```

La génération utilise un seed fixe (42) pour garantir la reproductibilité des instances.
"""
        )

    print(f"[OK] README créé: {readme_path}")
    print(f"\n[OK] {len(donnees)} fichiers générés dans {output_dir}")


if __name__ == "__main__":
    main()
