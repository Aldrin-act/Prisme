"""
Génère un solveur IA pour une instance TRCO spécifique.

Ce script génère un solveur via l'IA (Kimi) et l'enregistre
dans le solver_store pour l'utiliser avec notre instance.

Usage:
    python -m scripts.generer_solveur_pour_instance --instance <fichier.json> --client-id <id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Charger le fichier .env
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from dsl.schema import InstanceTRCO
from generation.graph import tenter_generation_avec_boucle
from solver_store.registry import Registre


def main():
    parser = argparse.ArgumentParser(description="Génère un solveur IA pour une instance TRCO")
    parser.add_argument("--instance", type=Path, required=True, help="Chemin vers l'instance TRCO (JSON)")
    parser.add_argument("--client-id", type=str, default="agro_client", help="ID du client (défaut: agro_client)")
    parser.add_argument(
        "--max-tentatives", type=int, default=3, help="Nombre maximum de tentatives de génération (défaut: 3)"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("GENERATION DE SOLVEUR IA")
    print("=" * 80)

    # Charger l'instance
    print(f"\n[1/3] Chargement de l'instance : {args.instance.name}")
    try:
        with open(args.instance, encoding="utf-8") as f:
            data = json.load(f)
        instance = InstanceTRCO(**data)
        print(f"      [OK] {len(instance.taches)} taches, {len(instance.ressources)} ressources")
    except Exception as e:
        print(f"      [ERREUR] Impossible de charger l'instance : {e}")
        sys.exit(1)

    # Générer le solveur
    print("\n[2/3] Generation du solveur avec IA...")
    print(f"      Pipeline multi-agents avec boucle (max {args.max_tentatives} tentatives)")
    print("      Duree estimee : 2-5 minutes")
    print("      Cout estime : ~$0.50-1.00")
    print()

    try:
        resultat = tenter_generation_avec_boucle(instance_exemple=instance.model_dump(mode="json"))
    except Exception as e:
        print(f"      [ERREUR] Generation echouee : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Vérifier le succès
    if not resultat.reussi:
        print("\n      [ECHEC] Le solveur n'a pas passe la validation")
        if resultat.erreur_execution:
            print(f"              Erreur d'execution : {resultat.erreur_execution[:200]}")
        if resultat.verdict_cascade:
            print(f"              Verdict cascade : {resultat.verdict_cascade}")
        sys.exit(1)

    print("      [OK] Solveur genere avec succes")

    # Sauvegarder le code
    output_dir = Path("data/solveurs_generes")
    output_dir.mkdir(parents=True, exist_ok=True)

    code_path = output_dir / f"solveur_{args.client_id}_ia.py"
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(resultat.code_final)
    print(f"           Code sauvegarde : {code_path}")

    # Enregistrer dans le store
    print("\n[3/3] Enregistrement dans le solver store...")
    try:
        registre = Registre()

        # Déterminer la signature des contraintes
        types_contraintes = sorted(set(c.type for c in instance.contraintes))
        signature = ",".join(types_contraintes)

        # Enregistrer
        id_solveur = registre.enregistrer(
            client_id=args.client_id, code_source=resultat.code_final, signature_contraintes=signature
        )

        print(f"      [OK] Solveur enregistre avec l'ID : {id_solveur}")
        print(f"           Client ID : {args.client_id}")
        print(f"           Signature : {signature}")

    except Exception as e:
        print(f"      [ERREUR] Impossible d'enregistrer le solveur : {e}")
        print(f"               Le code est quand meme disponible dans : {code_path}")
        sys.exit(1)

    # Résumé
    print("\n" + "=" * 80)
    print("GENERATION TERMINEE AVEC SUCCES")
    print("=" * 80)
    print(f"\nID Solveur : {id_solveur}")
    print(f"Client ID  : {args.client_id}")
    print(f"Code       : {code_path}")
    print(f"Lignes     : {len(resultat.code_final.splitlines())}")
    print()

    # Boucle de réparation
    if resultat.boucle_reparation:
        boucle = resultat.boucle_reparation
        print(f"Tentatives : {boucle.nb_tentatives}")
        if boucle.nb_tentatives > 1:
            print("  -> Corrections automatiques effectuees")

    print("\nProchaines etapes :")
    print(f"  1. Tester le solveur : python -m scripts.tester_solveur_ia --solveur-id {id_solveur}")
    print(f"  2. Utiliser via API  : POST /execution/{{instance_id}}?client_id={args.client_id}")
    print()


if __name__ == "__main__":
    main()
