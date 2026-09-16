"""
Générateur de données brutes à partir de configurations YAML de secteurs.

Ce script lit une configuration de secteur depuis data/configurations_secteurs/
et génère des données brutes au format ERP (JSON) — le vocabulaire fixe
`adapters.erp_reference.schema_erp.PayloadERP` (`code_operation`/`poste_id`/
`duree_jours`/`operation_precedente`), pour rester traduisible tel quel par
`adapters.erp_reference.translator.traduire`, comme les 6 secteurs "officiels"
de `scripts/generer_donnees_brutes.py`.

Usage:
    uv run python -m scripts.generer_donnees_depuis_config --secteur gestion_espaces_verts
    uv run python -m scripts.generer_donnees_depuis_config --secteur hopital_bloc_operatoire --taille 100
    uv run python -m scripts.generer_donnees_depuis_config --secteur restauration_collective --format json
    uv run python -m scripts.generer_donnees_depuis_config --tous --taille 50

Le format CSV (`--format csv`/`both`) produit le même contenu que le JSON, sérialisé en 3
fichiers `<secteur>_<taille>_{taches,ressources,contraintes}.csv` (compatible
`adapters.csv_import.traducteur.traduire`) — `sauvegarder_csv` reproduit fidèlement le mapping
de référence d'`adapters.erp_reference.translator.traduire` : compatibilité ressource-tâche
**explicite** (depuis `poste_id`/`duree_jours`), jamais seulement dérivée par compétence, plus
une contrainte `competence_requise` en signal additionnel (les deux mécanismes coexistent, voir
`adapters/csv_import/traducteur.py`).
"""

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

import yaml

# Les configs YAML expriment les durées en minutes (voir configurations_secteurs/README.md) ;
# `OperationERP.duree_jours` est en jours entiers (DSL, voir CLAUDE.md "DSL time unit is now
# jours") — journée ouvrée de 8h comme unité de conversion, jamais 0 jour (une opération de
# quelques minutes reste au moins 1 jour, même compromis que l'intégration GreenSIG réelle).
MINUTES_PAR_JOUR_OUVRE = 8 * 60


def charger_configuration(nom_secteur: str) -> dict[str, Any]:
    """Charge la configuration YAML d'un secteur."""
    chemin_config = Path("data/configurations_secteurs") / f"{nom_secteur}.yaml"

    if not chemin_config.exists():
        raise FileNotFoundError(
            f"Configuration introuvable: {chemin_config}\n"
            f"Vérifiez que le fichier existe dans data/configurations_secteurs/"
        )

    with open(chemin_config, encoding="utf-8") as f:
        return yaml.safe_load(f)


def lister_configurations_disponibles() -> list[str]:
    """Liste toutes les configurations de secteurs disponibles."""
    repertoire = Path("data/configurations_secteurs")
    if not repertoire.exists():
        return []

    return [fichier.stem for fichier in repertoire.glob("*.yaml")]


def generer_donnees_depuis_config(
    config: dict[str, Any],
    n_operations: int = 20,
) -> dict[str, Any]:
    """
    Génère un payload `PayloadERP` (`operations`/`postes`, vocabulaire
    `code_operation`/`poste_id`/`duree_jours`/`operation_precedente`) à
    partir d'une configuration de secteur.

    Chaque type de poste porte aussi sa compétence (nom du type de poste en
    minuscules — un type de poste ici représente un métier/une spécialité
    unique, ex. `EQUIPE_TONTE` -> `equipe_tonte`) et chaque opération déclare
    la compétence requise correspondante, sur le modèle de
    `creer_donnees_centre_appels_json` (`scripts/generer_donnees_brutes.py`)
    — ces 9 secteurs pilotés par config sont nouveaux, contrairement aux 6
    secteurs historiques volontairement pauvres en compétences (§5.4) :
    sans ce signal explicite, l'agent de compréhension (LLM) n'a aucune base
    pour affirmer une compatibilité ressource-tâche et rejette l'instance à
    raison (vérifié par appel réel, `poste_id` seul ne suffit pas à le
    convaincre).

    Args:
        config: Configuration du secteur chargée depuis YAML
        n_operations: Nombre d'opérations à générer

    Returns:
        Payload ERP au format JSON, directement passable à
        `adapters.erp_reference.schema_erp.PayloadERP(**payload)`.
    """
    types_postes = config["types_postes"]
    phases = config["phases_production"]
    generation = config.get("generation", {})

    ops_par_lot_min = generation.get("operations_par_lot_min", 4)
    ops_par_lot_max = generation.get("operations_par_lot_max", 8)

    # Calcul du nombre de lots nécessaires
    ops_par_lot_moyen = (ops_par_lot_min + ops_par_lot_max) / 2
    n_lots = max(1, int(n_operations / ops_par_lot_moyen))

    operations: list[dict[str, Any]] = []
    postes_crees: dict[str, dict[str, Any]] = {}
    op_id = 1

    # Génération par lots
    for _i_lot in range(n_lots):
        # Nombre d'opérations dans ce lot
        n_ops_lot = random.randint(ops_par_lot_min, ops_par_lot_max)

        # Sélectionner des phases pour ce lot
        phases_lot = random.sample(phases, min(len(phases), n_ops_lot))

        for i_op, phase in enumerate(phases_lot):
            # Choisir un type de poste compatible avec la phase
            type_poste_nom = random.choice(phase["types_poste"])
            type_poste_config = types_postes[type_poste_nom]

            # Créer le poste s'il n'existe pas encore (code_poste = nom du type, déjà unique) —
            # competence = nom du type de poste en minuscules, voir docstring.
            competence = type_poste_nom.lower()
            if type_poste_nom not in postes_crees:
                postes_crees[type_poste_nom] = {"code_poste": type_poste_nom, "competences": [competence]}

            # Durée générée en minutes (config), convertie en jours entiers (DSL)
            duree_minutes = random.randint(
                type_poste_config["duree_min"],
                type_poste_config["duree_max"],
            )
            duree_jours = max(1, round(duree_minutes / MINUTES_PAR_JOUR_OUVRE))

            operation = {
                "code_operation": f"{phase['nom']}_{op_id:03d}",
                "duree_jours": duree_jours,
                "poste_id": type_poste_nom,
                "competence_requise": competence,
            }

            # Précédence dans le lot uniquement (jamais entre lots, indépendants entre eux)
            if i_op > 0 and random.random() < 0.6:  # 60% de chance
                operation["operation_precedente"] = operations[-1]["code_operation"]

            operations.append(operation)
            op_id += 1

            if len(operations) >= n_operations:
                break

        if len(operations) >= n_operations:
            break

    return {"operations": operations, "postes": list(postes_crees.values())}


def sauvegarder_json(payload: dict[str, Any], nom_secteur: str, taille: str) -> Path:
    """Sauvegarde le payload au format JSON."""
    repertoire = Path("data/donnees_brutes/json_erp")
    repertoire.mkdir(parents=True, exist_ok=True)

    nom_fichier = f"{nom_secteur}_{taille}.json"
    chemin = repertoire / nom_fichier

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return chemin


def sauvegarder_csv(
    payload: dict[str, Any], prefixe: str, *, repertoire: Path | None = None
) -> tuple[Path, Path, Path]:
    """Sauvegarde le payload au format CSV à 3 fichiers (`taches`/`ressources`/`contraintes`),
    compatible `adapters.csv_import.traducteur.traduire` — voir docstring module pour le mapping.
    `nom` reste vide dans `taches.csv`/`ressources.csv` : le payload ERP (`OperationERP`/
    `PosteERP`, `adapters/erp_reference/schema_erp.py`) n'a pas ce champ, tout comme
    `translator.py` ne le renseigne jamais sur `Tache`/`Ressource` — même contenu que le JSON,
    juste une autre sérialisation. `repertoire` paramétrable (défaut `data/donnees_brutes/csv`)
    pour être réutilisée telle quelle par `scripts/generer_donnees_brutes_grande_echelle.py`
    (sortie dans `data/donnees_brutes_large/csv`) — un seul écrivain CSV pour tout le dépôt."""
    repertoire = repertoire or Path("data/donnees_brutes/csv")
    repertoire.mkdir(parents=True, exist_ok=True)

    chemin_taches = repertoire / f"{prefixe}_taches.csv"
    with open(chemin_taches, "w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom"])
        for op in payload["operations"]:
            ecrivain.writerow([op["code_operation"], ""])

    chemin_ressources = repertoire / f"{prefixe}_ressources.csv"
    with open(chemin_ressources, "w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom", "competences"])
        for poste in payload["postes"]:
            ecrivain.writerow([poste["code_poste"], "", ";".join(poste["competences"])])

    chemin_contraintes = repertoire / f"{prefixe}_contraintes.csv"
    with open(chemin_contraintes, "w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            ["type", "tache_avant", "tache_apres", "tache", "ressource", "duree_jours", "competence"]
        )
        for op in payload["operations"]:
            # Compatibilité explicite (poste_id/duree_jours) — même source de vérité que le
            # JSON (`translator.py::traduire`), jamais seulement dérivée par compétence.
            ecrivain.writerow(
                [
                    "compatibilite_ressource_tache",
                    "",
                    "",
                    op["code_operation"],
                    op["poste_id"],
                    op["duree_jours"],
                    "",
                ]
            )
            if op.get("operation_precedente"):
                ecrivain.writerow(["precedence", op["operation_precedente"], op["code_operation"], "", "", "", ""])
            if op.get("competence_requise"):
                ecrivain.writerow(
                    ["competence_requise", "", "", op["code_operation"], "", "", op["competence_requise"]]
                )

    return chemin_taches, chemin_ressources, chemin_contraintes


def main():
    parser = argparse.ArgumentParser(
        description="Génère des données brutes à partir d'une configuration YAML de secteur"
    )
    parser.add_argument(
        "--secteur",
        type=str,
        help="Nom du secteur (nom du fichier YAML sans extension)",
    )
    parser.add_argument(
        "--taille",
        type=int,
        default=20,
        help="Nombre d'opérations à générer (défaut: 20)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="Format de sortie (défaut: both)",
    )
    parser.add_argument(
        "--tous",
        action="store_true",
        help="Générer pour tous les secteurs configurés",
    )
    parser.add_argument(
        "--lister",
        action="store_true",
        help="Lister les secteurs disponibles et quitter",
    )

    args = parser.parse_args()

    # Lister les configurations disponibles
    if args.lister:
        configs = lister_configurations_disponibles()
        if configs:
            print("Configurations de secteurs disponibles:")
            for config in sorted(configs):
                print(f"  - {config}")
        else:
            print("Aucune configuration trouvée dans data/configurations_secteurs/")
        return

    # Vérifier les arguments
    if not args.tous and not args.secteur:
        parser.error("Vous devez spécifier --secteur <nom> ou --tous")

    # Déterminer la catégorie de taille
    if args.taille < 50:
        taille_str = "small"
    elif args.taille < 150:
        taille_str = "medium"
    else:
        taille_str = "large"

    # Liste des secteurs à traiter
    if args.tous:
        secteurs = lister_configurations_disponibles()
        if not secteurs:
            print("Erreur: Aucune configuration trouvée dans data/configurations_secteurs/")
            return
        print(f"Génération pour {len(secteurs)} secteurs...")
    else:
        secteurs = [args.secteur]

    # Génération pour chaque secteur
    resultats = []

    for nom_secteur in secteurs:
        try:
            print(f"\n[{nom_secteur}]")

            # Charger la configuration
            config = charger_configuration(nom_secteur)
            print(f"  Configuration chargée: {config.get('description', 'N/A')}")

            # Générer les données
            payload = generer_donnees_depuis_config(config, args.taille)
            n_ops = len(payload["operations"])
            n_postes = len(payload["postes"])
            print(f"  Données générées: {n_ops} opérations, {n_postes} postes")

            # Sauvegarder
            fichiers_crees = []

            if args.format in ["json", "both"]:
                chemin_json = sauvegarder_json(payload, nom_secteur, taille_str)
                fichiers_crees.append(chemin_json)
                print(f"  JSON: {chemin_json}")

            if args.format in ["csv", "both"]:
                chemin_taches, chemin_ressources, chemin_contraintes = sauvegarder_csv(
                    payload, f"{nom_secteur}_{taille_str}"
                )
                fichiers_crees.extend([chemin_taches, chemin_ressources, chemin_contraintes])
                print(f"  CSV: {chemin_taches}")
                print(f"       {chemin_ressources}")
                print(f"       {chemin_contraintes}")

            resultats.append(
                {
                    "secteur": nom_secteur,
                    "operations": n_ops,
                    "postes": n_postes,
                    "fichiers": fichiers_crees,
                }
            )

        except Exception as e:
            print(f"  Erreur: {e}")
            continue

    # Résumé final
    print("\n" + "=" * 60)
    print(f"Génération terminée: {len(resultats)} secteur(s) traité(s)")
    print("=" * 60)

    for resultat in resultats:
        print(f"\n{resultat['secteur']}:")
        print(f"  - {resultat['operations']} opérations")
        print(f"  - {resultat['postes']} postes")
        print(f"  - {len(resultat['fichiers'])} fichier(s) créé(s)")


if __name__ == "__main__":
    main()
