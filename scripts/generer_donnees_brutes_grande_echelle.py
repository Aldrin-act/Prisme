"""Génération de jeux de données brutes à grande échelle (100+ opérations).

Crée des instances réalistes simulant de vrais ateliers de production avec
environ 100 opérations par fichier, permettant de tester la scalabilité
de la pipeline PRISME.

Usage:
    python -m scripts.generer_donnees_brutes_grande_echelle
    python -m scripts.generer_donnees_brutes_grande_echelle --taille 150
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def generer_atelier_mecanique_large(n_operations: int = 100) -> dict:
    """Atelier de fabrication mécanique - grande échelle."""
    # Définir les types de postes et leurs caractéristiques (durées en jours)
    types_postes = {
        "DECOUPEUSE_LASER": {"duree_min": 1, "duree_max": 2, "capacite": 5},
        "DECOUPEUSE_PLASMA": {"duree_min": 1, "duree_max": 2, "capacite": 3},
        "PERCEUSE_CNC": {"duree_min": 1, "duree_max": 1, "capacite": 8},
        "FRAISEUSE_CNC": {"duree_min": 1, "duree_max": 3, "capacite": 6},
        "PRESSE_PLIAGE": {"duree_min": 1, "duree_max": 2, "capacite": 4},
        "PRESSE_EMBOUTISSAGE": {"duree_min": 1, "duree_max": 2, "capacite": 3},
        "POSTE_SOUDURE": {"duree_min": 1, "duree_max": 4, "capacite": 10},
        "ROBOT_SOUDURE": {"duree_min": 1, "duree_max": 3, "capacite": 4},
        "CABINE_PEINTURE": {"duree_min": 1, "duree_max": 3, "capacite": 6},
        "TUNNEL_PEINTURE": {"duree_min": 1, "duree_max": 2, "capacite": 3},
        "POSTE_ASSEMBLAGE": {"duree_min": 1, "duree_max": 2, "capacite": 12},
        "STATION_CONTROLE": {"duree_min": 1, "duree_max": 1, "capacite": 8},
        "POSTE_EBAVURAGE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "CENTRE_USINAGE": {"duree_min": 1, "duree_max": 4, "capacite": 5},
        "POSTE_POLISSAGE": {"duree_min": 1, "duree_max": 2, "capacite": 4},
    }

    # Créer les postes (instances multiples de chaque type)
    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    # Générer les opérations organisées en lots de production
    operations = []
    n_lots = n_operations // 10  # Environ 10 opérations par lot

    phases = [
        ("PREPARATION", ["DECOUPEUSE_LASER", "DECOUPEUSE_PLASMA", "PERCEUSE_CNC"]),
        ("USINAGE", ["FRAISEUSE_CNC", "CENTRE_USINAGE", "POSTE_EBAVURAGE"]),
        ("FORMAGE", ["PRESSE_PLIAGE", "PRESSE_EMBOUTISSAGE"]),
        ("SOUDURE", ["POSTE_SOUDURE", "ROBOT_SOUDURE"]),
        ("FINITION", ["POSTE_POLISSAGE", "POSTE_EBAVURAGE"]),
        ("PEINTURE", ["CABINE_PEINTURE", "TUNNEL_PEINTURE"]),
        ("ASSEMBLAGE", ["POSTE_ASSEMBLAGE"]),
        ("CONTROLE", ["STATION_CONTROLE"]),
    ]

    op_id = 1
    for lot in range(1, n_lots + 1):
        precedente = None

        # Chaque lot passe par 8-12 phases aléatoires
        n_phases_lot = random.randint(8, 12)
        phases_lot = random.sample(phases, min(n_phases_lot, len(phases)))

        for phase_nom, types_poste_phase in phases_lot:
            # Choisir un type de poste aléatoire pour cette phase
            type_poste = random.choice(types_poste_phase)

            # Choisir une instance de ce type de poste
            instances_disponibles = [
                p["code_poste"]
                for p in postes
                if p["code_poste"].startswith(type_poste)
            ]
            poste_choisi = random.choice(instances_disponibles)

            # Générer une durée aléatoire
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            # Créer l'opération
            code_op = f"LOT{lot:03d}_{phase_nom}_{op_id:04d}"
            operations.append({
                "code_operation": code_op,
                "duree_jours": duree,
                "poste_id": poste_choisi,
                "operation_precedente": precedente,
            })

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    # Compléter si nécessaire
    while len(operations) < n_operations:
        type_poste = random.choice(list(types_postes.keys()))
        instances_disponibles = [
            p["code_poste"]
            for p in postes
            if p["code_poste"].startswith(type_poste)
        ]
        poste_choisi = random.choice(instances_disponibles)
        specs = types_postes[type_poste]
        duree = random.randint(specs["duree_min"], specs["duree_max"])

        code_op = f"COMP_{op_id:04d}"
        operations.append({
            "code_operation": code_op,
            "duree_jours": duree,
            "poste_id": poste_choisi,
            "operation_precedente": None,
        })
        op_id += 1

    return {"operations": operations[:n_operations], "postes": postes}


def generer_assemblage_electronique_large(n_operations: int = 100) -> dict:
    """Assemblage électronique - grande échelle."""
    types_postes = {
        "PICK_PLACE": {"duree_min": 1, "duree_max": 3, "capacite": 6},
        "FOUR_REFUSION": {"duree_min": 1, "duree_max": 1, "capacite": 4},
        "AOI": {"duree_min": 1, "duree_max": 1, "capacite": 5},
        "POSTE_SOUDURE_MANUEL": {"duree_min": 1, "duree_max": 2, "capacite": 15},
        "BANC_TEST_ICT": {"duree_min": 1, "duree_max": 2, "capacite": 8},
        "BANC_TEST_FONCTIONNEL": {"duree_min": 1, "duree_max": 2, "capacite": 6},
        "ROBOT_COATING": {"duree_min": 1, "duree_max": 1, "capacite": 3},
        "STATION_ASSEMBLAGE": {"duree_min": 1, "duree_max": 2, "capacite": 10},
        "POSTE_DEPANNELISATION": {"duree_min": 1, "duree_max": 1, "capacite": 4},
        "STATION_PACKAGING": {"duree_min": 1, "duree_max": 1, "capacite": 8},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_cartes = n_operations // 8  # Environ 8 opérations par carte

    phases_pcb = [
        ("PREP", ["STATION_ASSEMBLAGE"]),
        ("POSE_CMS_A", ["PICK_PLACE"]),
        ("REFUSION_A", ["FOUR_REFUSION"]),
        ("AOI_A", ["AOI"]),
        ("POSE_CMS_B", ["PICK_PLACE"]),
        ("REFUSION_B", ["FOUR_REFUSION"]),
        ("SOUDURE_THT", ["POSTE_SOUDURE_MANUEL"]),
        ("TEST_ICT", ["BANC_TEST_ICT"]),
        ("TEST_FONC", ["BANC_TEST_FONCTIONNEL"]),
        ("COATING", ["ROBOT_COATING"]),
        ("DEPANEL", ["POSTE_DEPANNELISATION"]),
        ("PACKAGE", ["STATION_PACKAGING"]),
    ]

    op_id = 1
    for carte in range(1, n_cartes + 1):
        precedente = None

        # Chaque carte suit un processus standard
        n_phases = random.randint(8, len(phases_pcb))
        phases_carte = random.sample(phases_pcb, n_phases)

        for phase_nom, types_poste_phase in phases_carte:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [
                p["code_poste"]
                for p in postes
                if p["code_poste"].startswith(type_poste)
            ]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"PCB{carte:04d}_{phase_nom}_{op_id:04d}"
            operations.append({
                "code_operation": code_op,
                "duree_jours": duree,
                "poste_id": poste_choisi,
                "operation_precedente": precedente,
            })

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    while len(operations) < n_operations:
        type_poste = random.choice(list(types_postes.keys()))
        instances_disponibles = [
            p["code_poste"]
            for p in postes
            if p["code_poste"].startswith(type_poste)
        ]
        poste_choisi = random.choice(instances_disponibles)
        specs = types_postes[type_poste]
        duree = random.randint(specs["duree_min"], specs["duree_max"])

        code_op = f"EXTRA_{op_id:04d}"
        operations.append({
            "code_operation": code_op,
            "duree_jours": duree,
            "poste_id": poste_choisi,
            "operation_precedente": None,
        })
        op_id += 1

    return {"operations": operations[:n_operations], "postes": postes}


def generer_agroalimentaire_large(n_operations: int = 100) -> dict:
    """Production agro-alimentaire - grande échelle."""
    types_postes = {
        "QUAI_RECEPTION": {"duree_min": 1, "duree_max": 1, "capacite": 4},
        "TUNNEL_LAVAGE": {"duree_min": 1, "duree_max": 1, "capacite": 3},
        "LIGNE_EPLUCHAGE": {"duree_min": 1, "duree_max": 2, "capacite": 5},
        "ROBOT_DECOUPE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "AUTOCLAVE": {"duree_min": 2, "duree_max": 5, "capacite": 8},
        "TUNNEL_REFROIDISSEMENT": {"duree_min": 1, "duree_max": 3, "capacite": 4},
        "LIGNE_CONDITIONNEMENT": {"duree_min": 1, "duree_max": 2, "capacite": 10},
        "ETIQUETEUSE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "ROBOT_PALETTISEUR": {"duree_min": 1, "duree_max": 1, "capacite": 5},
        "POSTE_CONTROLE_QUALITE": {"duree_min": 1, "duree_max": 1, "capacite": 8},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_lots = n_operations // 9

    phases_production = [
        ("RECEPTION", ["QUAI_RECEPTION"]),
        ("LAVAGE", ["TUNNEL_LAVAGE"]),
        ("EPLUCHAGE", ["LIGNE_EPLUCHAGE"]),
        ("DECOUPE", ["ROBOT_DECOUPE"]),
        ("CUISSON", ["AUTOCLAVE"]),
        ("REFROIDISSEMENT", ["TUNNEL_REFROIDISSEMENT"]),
        ("CONDITIONNEMENT", ["LIGNE_CONDITIONNEMENT"]),
        ("ETIQUETAGE", ["ETIQUETEUSE"]),
        ("CONTROLE", ["POSTE_CONTROLE_QUALITE"]),
        ("PALETTISATION", ["ROBOT_PALETTISEUR"]),
    ]

    op_id = 1
    for lot in range(1, n_lots + 1):
        precedente = None
        n_phases = random.randint(7, len(phases_production))
        phases_lot = random.sample(phases_production, n_phases)

        for phase_nom, types_poste_phase in phases_lot:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [
                p["code_poste"]
                for p in postes
                if p["code_poste"].startswith(type_poste)
            ]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"BATCH{lot:03d}_{phase_nom}_{op_id:04d}"
            operations.append({
                "code_operation": code_op,
                "duree_jours": duree,
                "poste_id": poste_choisi,
                "operation_precedente": precedente,
            })

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    while len(operations) < n_operations:
        type_poste = random.choice(list(types_postes.keys()))
        instances_disponibles = [
            p["code_poste"]
            for p in postes
            if p["code_poste"].startswith(type_poste)
        ]
        poste_choisi = random.choice(instances_disponibles)
        specs = types_postes[type_poste]
        duree = random.randint(specs["duree_min"], specs["duree_max"])

        code_op = f"SUPP_{op_id:04d}"
        operations.append({
            "code_operation": code_op,
            "duree_jours": duree,
            "poste_id": poste_choisi,
            "operation_precedente": None,
        })
        op_id += 1

    return {"operations": operations[:n_operations], "postes": postes}


def sauvegarder_donnees(nom: str, data: dict, output_dir: Path) -> None:
    """Sauvegarde les données en JSON et CSV."""
    # JSON
    json_dir = output_dir / "json_erp"
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / f"{nom}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # CSV
    csv_dir = output_dir / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    # Operations CSV
    ops_path = csv_dir / f"{nom}_operations.csv"
    with open(ops_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["code_operation", "duree_jours", "poste_id", "operation_precedente"]
        )
        writer.writeheader()
        writer.writerows(data["operations"])

    # Postes CSV
    postes_path = csv_dir / f"{nom}_postes.csv"
    with open(postes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code_poste"])
        writer.writeheader()
        writer.writerows(data["postes"])

    return json_path, ops_path, postes_path


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Genere des jeux de donnees brutes a grande echelle (100+ operations)"
    )
    parser.add_argument(
        "--taille",
        type=int,
        default=100,
        help="Nombre d'operations par jeu de donnees (defaut: 100)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Repertoire de sortie (defaut: data/donnees_brutes_large)",
    )

    args = parser.parse_args()

    # Déterminer le répertoire de sortie
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = Path(__file__).parent.parent / "data" / "donnees_brutes_large"

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generation de jeux de donnees a grande echelle")
    print(f"Taille cible: {args.taille} operations par fichier")
    print(f"Repertoire de sortie: {output_dir}")
    print()

    # Générer les jeux de données
    datasets = [
        ("atelier_mecanique_large", generer_atelier_mecanique_large),
        ("assemblage_electronique_large", generer_assemblage_electronique_large),
        ("production_agroalimentaire_large", generer_agroalimentaire_large),
    ]

    for nom, generateur in datasets:
        print(f"[GENERATION] {nom}...")
        data = generateur(args.taille)

        json_path, ops_path, postes_path = sauvegarder_donnees(nom, data, output_dir)

        print(f"  Operations: {len(data['operations'])}")
        print(f"  Postes: {len(data['postes'])}")
        print(f"  JSON: {json_path.relative_to(output_dir.parent)}")
        print(f"  CSV Operations: {ops_path.relative_to(output_dir.parent)}")
        print(f"  CSV Postes: {postes_path.relative_to(output_dir.parent)}")
        print()

    # Créer un README
    readme_path = output_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"""# Données Brutes à Grande Échelle

Ce répertoire contient des jeux de données volumineux (~{args.taille} opérations par fichier)
pour tester la scalabilité de la pipeline PRISME.

## Jeux de Données

- **atelier_mecanique_large** : {args.taille}+ opérations, fabrication métallique
- **assemblage_electronique_large** : {args.taille}+ opérations, assemblage PCB
- **production_agroalimentaire_large** : {args.taille}+ opérations, transformation alimentaire

## Utilisation

### Transformation en instances TRCO

```bash
python -m scripts.transformer_donnees_brutes --input-dir data/donnees_brutes_large/json_erp
```

### Régénération

```bash
# Taille par défaut (100 opérations)
python -m scripts.generer_donnees_brutes_grande_echelle

# Taille personnalisée
python -m scripts.generer_donnees_brutes_grande_echelle --taille 150
python -m scripts.generer_donnees_brutes_grande_echelle --taille 200
```

## Caractéristiques

- Opérations organisées en lots de production réalistes
- Précédences entre opérations d'un même lot
- Multiples instances de chaque type de poste (haute capacité)
- Durées variables selon le type de poste
- Format compatible avec l'adaptateur ERP de référence

## Note

Ces instances volumineuses permettent de :
- Tester les performances du générateur LLM sur de grandes instances
- Valider la scalabilité du solveur CP-SAT
- Évaluer les temps d'exécution dans le sandbox
- Benchmarker la cascade de validation

Génération : {args.taille} opérations/fichier
Date : 2026-07-23
""")

    print(f"[OK] README cree: {readme_path}")
    print()
    print(f"Generation terminee ! {len(datasets)} jeux de donnees crees")
    print(f"Repertoire: {output_dir}")


if __name__ == "__main__":
    main()
