"""Démonstration du workflow complet : Données brutes → Planning optimisé.

Ce script illustre le processus complet de transformation et d'utilisation
des données brutes dans la pipeline PRISME.

Usage:
    python -m scripts.demo_donnees_brutes
"""

from __future__ import annotations

import json
from pathlib import Path


def demo_workflow_complet():
    """Démontre le workflow complet de A à Z."""
    print("=" * 70)
    print("DEMO : Workflow Complet - Donnees Brutes -> Planning Optimise")
    print("=" * 70)
    print()

    # =========================================================================
    # ETAPE 1 : Charger les données brutes (format ERP)
    # =========================================================================
    print("[ETAPE 1] Chargement des donnees brutes (format ERP)")
    print("-" * 70)

    chemin_brut = Path(__file__).parent.parent / "data" / "donnees_brutes" / "json_erp" / "atelier_mecanique.json"

    with open(chemin_brut, "r", encoding="utf-8") as f:
        data_brute = json.load(f)

    print(f"Fichier: {chemin_brut.name}")
    print(f"Operations: {len(data_brute['operations'])}")
    print(f"Postes: {len(data_brute['postes'])}")
    print()

    print("Exemple d'operation:")
    print(json.dumps(data_brute["operations"][0], indent=2, ensure_ascii=False))
    print()

    # =========================================================================
    # ETAPE 2 : Traduire en instance TRCO (format canonique)
    # =========================================================================
    print("[ETAPE 2] Traduction ERP -> TRCO")
    print("-" * 70)

    from adapters.erp_reference.schema_erp import PayloadERP
    from adapters.erp_reference.translator import traduire

    # Charger le payload ERP
    payload_erp = PayloadERP(**data_brute)
    print(f"Payload ERP charge: {type(payload_erp).__name__}")

    # Traduire
    instance_trco = traduire(payload_erp)
    print(f"Instance TRCO creee: {type(instance_trco).__name__}")
    print(f"  - Taches: {len(instance_trco.taches)}")
    print(f"  - Ressources: {len(instance_trco.ressources)}")
    print(f"  - Contraintes: {len(instance_trco.contraintes)}")
    print(f"  - Objectifs: {len(instance_trco.objectifs)}")
    print()

    # Afficher quelques contraintes
    print("Exemple de contraintes:")
    for contrainte in instance_trco.contraintes[:3]:
        print(f"  - {contrainte.type}: {contrainte.model_dump(exclude={'type'})}")
    print(f"  - ... ({len(instance_trco.contraintes) - 3} autres)")
    print()

    # =========================================================================
    # ETAPE 3 : Validation de l'instance
    # =========================================================================
    print("[ETAPE 3] Validation de l'instance TRCO")
    print("-" * 70)

    # L'instance est déjà validée par Pydantic lors de la création
    print("Validations Pydantic passees:")
    print("  [OK] IDs uniques par axe")
    print("  [OK] Chaque tache a au moins une compatibilite ressource")
    print("  [OK] Les contraintes referencent des entites declarees")
    print()

    # =========================================================================
    # ETAPE 4 : Génération du solveur (simulée)
    # =========================================================================
    print("[ETAPE 4] Generation du solveur (necessite LLM)")
    print("-" * 70)

    print("NOTE: La generation necessite une cle API LLM configuree.")
    print("      Cette etape est sautee dans cette demo.")
    print()
    print("Commande pour generer reellement:")
    print("  from generation.tentative_unique import generer_et_tester_solveur")
    print("  resultat = generer_et_tester_solveur(instance_trco)")
    print()

    # =========================================================================
    # DEMONSTRATION : Utilisation d'un solveur de référence
    # =========================================================================
    print("[DEMO] Utilisation du solveur de reference (a la place du genere)")
    print("-" * 70)

    try:
        from scripts._solveur_minimal import resoudre

        planning = resoudre(instance_trco)

        if planning:
            print("Planning genere avec succes!")

            # Créer un dictionnaire des durées depuis les contraintes
            durees = {}
            for contrainte in instance_trco.contraintes:
                if contrainte.type == "compatibilite_ressource_tache":
                    durees[(contrainte.tache, contrainte.ressource)] = contrainte.duree

            # Calculer le makespan
            makespan = 0
            for op in planning.operations:
                duree = durees.get((op.tache, op.ressource), 0)
                fin = op.debut + duree
                makespan = max(makespan, fin)

            print(f"Makespan: {makespan} minutes")
            print(f"Nombre d'operations planifiees: {len(planning.operations)}")
            print()

            print("Planning detaille:")
            print(f"{'Tache':<20} {'Ressource':<20} {'Debut':>8} {'Duree':>8} {'Fin':>8}")
            print("-" * 70)

            for op in sorted(planning.operations, key=lambda x: x.debut):
                duree = durees.get((op.tache, op.ressource), 0)
                fin = op.debut + duree
                print(f"{op.tache:<20} {op.ressource:<20} {op.debut:>8} {duree:>8} {fin:>8}")

            print()
        else:
            print("ATTENTION: Aucune solution trouvee")
            print()

    except ImportError:
        print("ATTENTION: Solveur de reference non disponible")
        print("           Installez OR-Tools : pip install ortools")
        print()

    # =========================================================================
    # RESUME DU WORKFLOW
    # =========================================================================
    print("=" * 70)
    print("RESUME DU WORKFLOW")
    print("=" * 70)
    print()
    print("1. Donnees brutes (ERP)        ->  Format proprietaire (JSON/CSV)")
    print("2. Traduction (Adaptateur)     ->  Instance TRCO (canonique)")
    print("3. Validation (Pydantic)       ->  Garde-fou amont (§6.7)")
    print("4. Generation (LLM)            ->  Code solveur CP-SAT")
    print("5. Validation (Cascade)        ->  Tests faisabilite/optimalite")
    print("6. Persistance (Registre)      ->  Artifact freeze")
    print("7. Execution (Sandbox)         ->  Planning optimise")
    print()
    print("=" * 70)


def lister_jeux_donnees():
    """Liste tous les jeux de données disponibles."""
    print("\n" + "=" * 70)
    print("JEUX DE DONNEES DISPONIBLES")
    print("=" * 70)
    print()

    donnees_brutes_dir = Path(__file__).parent.parent / "data" / "donnees_brutes" / "json_erp"
    instances_trco_dir = Path(__file__).parent.parent / "data" / "instances_trco"

    if donnees_brutes_dir.exists():
        fichiers_bruts = sorted(donnees_brutes_dir.glob("*.json"))
        print(f"Donnees brutes (format ERP) : {len(fichiers_bruts)} fichiers")
        for f in fichiers_bruts:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                print(f"  - {f.name:<35} {len(data['operations']):>3} ops, {len(data['postes']):>3} postes")
        print()

    if instances_trco_dir.exists():
        fichiers_trco = sorted(instances_trco_dir.glob("*.json"))
        print(f"Instances TRCO (canoniques)  : {len(fichiers_trco)} fichiers")
        for f in fichiers_trco:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                print(
                    f"  - {f.name:<35} "
                    f"{len(data['taches']):>3} taches, "
                    f"{len(data['ressources']):>3} ressources, "
                    f"{len(data['contraintes']):>3} contraintes"
                )
        print()


def afficher_aide():
    """Affiche l'aide et les commandes utiles."""
    print("\n" + "=" * 70)
    print("COMMANDES UTILES")
    print("=" * 70)
    print()

    print("Generer les donnees brutes:")
    print("  python -m scripts.generer_donnees_brutes")
    print()

    print("Transformer en instances TRCO:")
    print("  python -m scripts.transformer_donnees_brutes")
    print()

    print("Afficher cette demo:")
    print("  python -m scripts.demo_donnees_brutes")
    print()

    print("Charger une instance dans votre code:")
    print("  from dsl.validation.charger_instance import charger_instance_depuis_json")
    print("  instance = charger_instance_depuis_json('data/instances_trco/atelier_mecanique.json')")
    print()

    print("Documentation complete:")
    print("  data/GUIDE_DONNEES.md")
    print("  data/README.md")
    print("  data/donnees_brutes/README.md")
    print()


if __name__ == "__main__":
    demo_workflow_complet()
    lister_jeux_donnees()
    afficher_aide()
