"""Configuration des objectifs pour les instances TRCO.

Ce script permet d'enrichir des instances TRCO existantes avec différentes
configurations d'objectifs, et optionnellement d'ajouter des échéances et
des compétences.

Usage:
    # Appliquer une configuration à toutes les instances
    python -m scripts.configurer_objectifs --config equilibrage

    # Appliquer à une instance spécifique
    python -m scripts.configurer_objectifs --input data/instances_trco/atelier_mecanique.json --config multi

    # Générer toutes les variantes
    python -m scripts.configurer_objectifs --all
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# Définitions des configurations d'objectifs
CONFIGURATIONS_OBJECTIFS = {
    "makespan": {
        "description": "Minimiser uniquement le makespan",
        "objectifs": [{"type": "minimiser_makespan", "poids": 1.0}],
    },
    "equilibrage": {
        "description": "Équilibrage de charge + makespan",
        "objectifs": [
            {"type": "equilibrer_charge", "poids": 0.6, "methode": "ecart_max"},
            {"type": "minimiser_makespan", "poids": 0.4},
        ],
    },
    "retards": {
        "description": "Minimiser les retards (avec échéances générées)",
        "objectifs": [
            {
                "type": "minimiser_retards",
                "poids": 0.7,
                "fonction_penalite": "quadratique",
                "seuil_grace": 10,
            },
            {"type": "minimiser_makespan", "poids": 0.3},
        ],
        "ajouter_echeances": True,
    },
    "utilisation": {
        "description": "Maximiser l'utilisation des ressources",
        "objectifs": [
            {"type": "maximiser_utilisation", "poids": 0.6},
            {"type": "minimiser_makespan", "poids": 0.4},
        ],
    },
    "changements": {
        "description": "Minimiser les changements de ressources",
        "objectifs": [
            {"type": "minimiser_changements", "poids": 0.5},
            {"type": "minimiser_makespan", "poids": 0.3},
            {"type": "equilibrer_charge", "poids": 0.2, "methode": "variance"},
        ],
    },
    "multi": {
        "description": "Configuration multi-objectifs complète",
        "objectifs": [
            {"type": "minimiser_makespan", "poids": 0.25, "makespan_cible": None},
            {"type": "equilibrer_charge", "poids": 0.25, "methode": "gini"},
            {"type": "minimiser_retards", "poids": 0.2, "fonction_penalite": "lineaire"},
            {"type": "maximiser_utilisation", "poids": 0.15},
            {"type": "minimiser_changements", "poids": 0.15},
        ],
        "ajouter_echeances": True,
    },
}


def charger_instance(chemin: Path) -> dict:
    """Charge une instance TRCO depuis JSON."""
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def sauvegarder_instance(instance: dict, chemin: Path) -> None:
    """Sauvegarde une instance TRCO en JSON."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(instance, f, indent=2, ensure_ascii=False)


def estimer_duree_totale(instance: dict) -> int:
    """Estime la durée totale d'une instance (somme des durées)."""
    duree_totale = 0
    for contrainte in instance.get("contraintes", []):
        if contrainte.get("type") == "compatibilite_ressource_tache":
            duree_totale += contrainte.get("duree", 0)
    return duree_totale


def ajouter_echeances(instance: dict, strategie: str = "uniforme") -> dict:
    """Ajoute des échéances aux tâches.

    Stratégies:
    - uniforme: Échéances uniformément distribuées
    - critique: Quelques tâches avec échéances critiques
    - progressive: Échéances de plus en plus serrées
    """
    n_taches = len(instance["taches"])
    duree_totale = estimer_duree_totale(instance)

    # Estimer un makespan approximatif (durée totale / nb ressources * facteur)
    n_ressources = len(instance["ressources"])
    makespan_estime = int(duree_totale / max(n_ressources, 1) * 1.5)

    # Sélectionner les tâches qui auront des échéances
    if strategie == "uniforme":
        # 50% des tâches ont des échéances
        n_echeances = max(3, n_taches // 2)
        taches_avec_echeance = random.sample(instance["taches"], n_echeances)

        for i, tache in enumerate(taches_avec_echeance):
            # Échéances distribuées uniformément entre 50% et 100% du makespan estimé
            echeance = int(makespan_estime * (0.5 + 0.5 * (i / n_echeances)))
            instance["contraintes"].append(
                {
                    "type": "echeance",
                    "tache": tache["id"],
                    "echeance": echeance,
                }
            )

    elif strategie == "critique":
        # 20% des tâches avec échéances très serrées
        n_critiques = max(2, n_taches // 5)
        taches_critiques = random.sample(instance["taches"], n_critiques)

        for tache in taches_critiques:
            # Échéances critiques (60-80% du makespan)
            echeance = int(makespan_estime * random.uniform(0.6, 0.8))
            instance["contraintes"].append(
                {
                    "type": "echeance",
                    "tache": tache["id"],
                    "echeance": echeance,
                }
            )

    elif strategie == "progressive":
        # Les échéances deviennent de plus en plus serrées
        n_echeances = max(4, n_taches // 3)
        taches_avec_echeance = random.sample(instance["taches"], n_echeances)

        for i, tache in enumerate(taches_avec_echeance):
            # Échéances de plus en plus serrées
            facteur = 1.0 - (i / n_echeances) * 0.4  # De 100% à 60%
            echeance = int(makespan_estime * facteur)
            instance["contraintes"].append(
                {
                    "type": "echeance",
                    "tache": tache["id"],
                    "echeance": echeance,
                }
            )

    return instance


def ajouter_competences(instance: dict, taux_specialisation: float = 0.3) -> dict:
    """Ajoute des compétences aux ressources et des exigences aux tâches.

    Une exigence n'est ajoutée que si toutes les ressources compatibles avec
    la tâche (via `compatibilite_ressource_tache`) possèdent déjà cette
    compétence — sinon `InstanceTRCO` rejette l'instance (§6.7, cohérence
    compétence/compatibilité) : tirer une compétence requise indépendamment
    des compétences réellement attribuées peut produire une instance
    invalide selon l'aléa.

    Args:
        taux_specialisation: Proportion de tâches nécessitant des compétences (0.0 à 1.0)
    """
    # Définir quelques compétences génériques
    competences_disponibles = [
        "usinage_precision",
        "soudure_certifiee",
        "assemblage_electronique",
        "controle_qualite",
        "manutention_lourde",
        "programmation_cnc",
        "peinture_industrielle",
        "maintenance_niveau2",
    ]

    # Attribuer aléatoirement des compétences aux ressources
    for ressource in instance["ressources"]:
        if "competences" not in ressource:
            ressource["competences"] = []

        # Chaque ressource a 1-3 compétences aléatoires
        n_competences = random.randint(1, 3)
        ressource["competences"] = random.sample(
            competences_disponibles, min(n_competences, len(competences_disponibles))
        )

    competences_par_ressource = {r["id"]: set(r["competences"]) for r in instance["ressources"]}
    ressources_compatibles_par_tache: dict[str, list[str]] = {}
    for contrainte in instance["contraintes"]:
        if contrainte.get("type") == "compatibilite_ressource_tache":
            ressources_compatibles_par_tache.setdefault(contrainte["tache"], []).append(contrainte["ressource"])

    # Ajouter des exigences de compétences à certaines tâches
    n_taches_specialisees = int(len(instance["taches"]) * taux_specialisation)
    taches_specialisees = random.sample(instance["taches"], n_taches_specialisees)

    for tache in taches_specialisees:
        ressources_compatibles = ressources_compatibles_par_tache.get(tache["id"], [])
        if not ressources_compatibles:
            continue

        # Compétences communes à toutes les ressources compatibles : seules
        # candidates possibles pour une exigence cohérente sur cette tâche.
        competences_communes = set.intersection(*(competences_par_ressource[r] for r in ressources_compatibles))
        if not competences_communes:
            continue

        n_competences_requises = min(random.randint(1, 2), len(competences_communes))
        competences_requises = random.sample(sorted(competences_communes), n_competences_requises)

        for competence in competences_requises:
            instance["contraintes"].append(
                {
                    "type": "competence_requise",
                    "tache": tache["id"],
                    "competence": competence,
                }
            )

    return instance


def appliquer_configuration(
    instance: dict,
    config_nom: str,
    ajouter_echeances_extra: bool = False,
    ajouter_competences_extra: bool = False,
) -> dict:
    """Applique une configuration d'objectifs à une instance."""
    config = CONFIGURATIONS_OBJECTIFS[config_nom]

    # Remplacer les objectifs
    instance["objectifs"] = config["objectifs"].copy()

    # Ajuster le makespan_cible si null
    for objectif in instance["objectifs"]:
        if objectif.get("type") == "minimiser_makespan" and objectif.get("makespan_cible") is None:
            duree_totale = estimer_duree_totale(instance)
            n_ressources = len(instance["ressources"])
            makespan_cible = int(duree_totale / max(n_ressources, 1) * 1.8)
            objectif["makespan_cible"] = makespan_cible

    # Ajouter des échéances si demandé
    if config.get("ajouter_echeances") or ajouter_echeances_extra:
        instance = ajouter_echeances(instance, strategie="uniforme")

    # Ajouter des compétences si demandé
    if ajouter_competences_extra:
        instance = ajouter_competences(instance, taux_specialisation=0.3)

    return instance


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(description="Configure les objectifs des instances TRCO")

    parser.add_argument(
        "--input",
        type=Path,
        help="Instance TRCO à enrichir (si non fourni, traite toutes les instances)",
    )
    parser.add_argument(
        "--config",
        choices=list(CONFIGURATIONS_OBJECTIFS.keys()),
        help="Configuration d'objectifs à appliquer",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Génère toutes les variantes pour toutes les instances",
    )
    parser.add_argument(
        "--add-echeances",
        action="store_true",
        help="Ajouter des échéances supplémentaires",
    )
    parser.add_argument(
        "--add-competences",
        action="store_true",
        help="Ajouter des compétences aux ressources et exigences aux tâches",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Répertoire de sortie (défaut: data/instances_trco_enrichies)",
    )

    args = parser.parse_args()

    # Déterminer le répertoire de sortie
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = Path(__file__).parent.parent / "data" / "instances_trco_enrichies"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Mode --all : générer toutes les variantes
    if args.all:
        instances_dir = Path(__file__).parent.parent / "data" / "instances_trco"
        fichiers = sorted(instances_dir.glob("*.json"))

        print("=" * 80)
        print("GENERATION DE TOUTES LES VARIANTES D'OBJECTIFS")
        print("=" * 80)
        print()

        total_variantes = 0

        for fichier in fichiers:
            instance_base = charger_instance(fichier)
            nom_base = fichier.stem

            print(f"[INSTANCE] {nom_base}")
            print("-" * 80)

            for config_nom, config_info in CONFIGURATIONS_OBJECTIFS.items():
                # Créer une copie de l'instance
                instance = json.loads(json.dumps(instance_base))

                # Appliquer la configuration
                instance = appliquer_configuration(
                    instance,
                    config_nom,
                    ajouter_competences_extra=args.add_competences,
                )

                # Sauvegarder
                nom_sortie = f"{nom_base}_{config_nom}.json"
                chemin_sortie = output_dir / nom_sortie
                sauvegarder_instance(instance, chemin_sortie)

                print(f"  [OK] {config_nom:<15} -> {nom_sortie}")
                total_variantes += 1

            print()

        print("=" * 80)
        print(f"TOTAL: {total_variantes} variantes generees dans {output_dir}")
        print("=" * 80)

    # Mode ciblé : une instance + une config
    elif args.input and args.config:
        print(f"Configuration de {args.input.name} avec '{args.config}'...")

        instance = charger_instance(args.input)
        instance = appliquer_configuration(
            instance,
            args.config,
            ajouter_echeances_extra=args.add_echeances,
            ajouter_competences_extra=args.add_competences,
        )

        nom_sortie = f"{args.input.stem}_{args.config}.json"
        chemin_sortie = output_dir / nom_sortie
        sauvegarder_instance(instance, chemin_sortie)

        print(f"Instance enrichie sauvegardee: {chemin_sortie}")
        print(f"  Objectifs: {len(instance['objectifs'])}")
        print(f"  Contraintes: {len(instance['contraintes'])}")

    else:
        print("ERREUR: Vous devez fournir soit --all, soit --input ET --config")
        parser.print_help()
        return

    # Afficher les configurations disponibles
    print()
    print("CONFIGURATIONS D'OBJECTIFS DISPONIBLES:")
    print("-" * 80)
    for nom, config in CONFIGURATIONS_OBJECTIFS.items():
        print(f"  {nom:<15} : {config['description']}")
        print(f"                  Objectifs: {len(config['objectifs'])}")
    print()


if __name__ == "__main__":
    main()
