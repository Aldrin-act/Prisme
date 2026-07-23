"""Validation des instances TRCO avec objectifs variés.

Ce script vérifie que toutes les instances générées peuvent être chargées
et respectent les contraintes du DSL.

Usage:
    uv run python -m scripts.valider_instances_objectifs_varies
"""

from __future__ import annotations

import json
from pathlib import Path


def valider_instances() -> None:
    """Valide toutes les instances générées."""
    instances_dir = Path(__file__).parent.parent / "dsl" / "examples" / "objectifs_varies"

    if not instances_dir.exists():
        print(f"ERREUR: Le repertoire {instances_dir} n'existe pas")
        print("Executez d'abord: python -m scripts.generer_instances_objectifs_varies")
        return

    fichiers_json = sorted(instances_dir.glob("*.json"))

    if not fichiers_json:
        print(f"ERREUR: Aucun fichier JSON trouve dans {instances_dir}")
        return

    print(f"Validation de {len(fichiers_json)} instances...\n")

    erreurs_totales = 0
    succes_totaux = 0

    for fichier in fichiers_json:
        print(f"[TEST] {fichier.name}")

        try:
            # Charger le JSON
            with open(fichier, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Vérifications de base
            erreurs = []

            # Vérifier les clés obligatoires
            cles_requises = {"taches", "ressources", "contraintes", "objectifs"}
            cles_presentes = set(data.keys())
            cles_manquantes = cles_requises - cles_presentes
            if cles_manquantes:
                erreurs.append(f"Cles manquantes: {cles_manquantes}")

            # Vérifier que les listes ne sont pas vides
            if "taches" in data and not data["taches"]:
                erreurs.append("Liste de taches vide")
            if "ressources" in data and not data["ressources"]:
                erreurs.append("Liste de ressources vide")
            if "objectifs" in data and not data["objectifs"]:
                erreurs.append("Liste d'objectifs vide")

            # Vérifier les IDs uniques
            if "taches" in data:
                ids_taches = [t.get("id") for t in data["taches"]]
                if len(ids_taches) != len(set(ids_taches)):
                    erreurs.append("IDs de taches dupliques")

            if "ressources" in data:
                ids_ressources = [r.get("id") for r in data["ressources"]]
                if len(ids_ressources) != len(set(ids_ressources)):
                    erreurs.append("IDs de ressources dupliques")

            # Vérifier que chaque tâche a au moins une compatibilité
            if "taches" in data and "contraintes" in data:
                ids_taches = {t.get("id") for t in data["taches"]}
                taches_avec_compatibilite = {
                    c.get("tache")
                    for c in data["contraintes"]
                    if c.get("type") == "compatibilite_ressource_tache"
                }
                taches_sans_compatibilite = ids_taches - taches_avec_compatibilite
                if taches_sans_compatibilite:
                    erreurs.append(f"Taches sans compatibilite: {taches_sans_compatibilite}")

            # Vérifier que les contraintes référencent des entités existantes
            if "contraintes" in data:
                ids_taches = {t.get("id") for t in data.get("taches", [])}
                ids_ressources = {r.get("id") for r in data.get("ressources", [])}

                for i, contrainte in enumerate(data["contraintes"]):
                    type_contrainte = contrainte.get("type")

                    if type_contrainte == "precedence":
                        avant = contrainte.get("avant")
                        apres = contrainte.get("apres")
                        if avant not in ids_taches:
                            erreurs.append(f"Contrainte {i}: tache 'avant' inconnue: {avant}")
                        if apres not in ids_taches:
                            erreurs.append(f"Contrainte {i}: tache 'apres' inconnue: {apres}")

                    elif type_contrainte == "compatibilite_ressource_tache":
                        tache = contrainte.get("tache")
                        ressource = contrainte.get("ressource")
                        duree = contrainte.get("duree")
                        if tache not in ids_taches:
                            erreurs.append(f"Contrainte {i}: tache inconnue: {tache}")
                        if ressource not in ids_ressources:
                            erreurs.append(f"Contrainte {i}: ressource inconnue: {ressource}")
                        if not isinstance(duree, int) or duree <= 0:
                            erreurs.append(f"Contrainte {i}: duree invalide: {duree}")

                    elif type_contrainte == "echeance":
                        tache = contrainte.get("tache")
                        echeance = contrainte.get("echeance")
                        if tache not in ids_taches:
                            erreurs.append(f"Contrainte {i}: tache inconnue: {tache}")
                        if not isinstance(echeance, int) or echeance < 0:
                            erreurs.append(f"Contrainte {i}: echeance invalide: {echeance}")

            # Vérifier les objectifs
            if "objectifs" in data:
                types_objectifs_valides = {
                    "minimiser_makespan",
                    "equilibrer_charge",
                    "minimiser_retards",
                    "maximiser_utilisation",
                    "minimiser_changements",
                }

                for i, objectif in enumerate(data["objectifs"]):
                    type_obj = objectif.get("type")
                    if type_obj not in types_objectifs_valides:
                        erreurs.append(f"Objectif {i}: type inconnu: {type_obj}")

                    # Vérifier le poids
                    if "poids" in objectif:
                        poids = objectif.get("poids")
                        if not isinstance(poids, (int, float)) or poids < 0:
                            erreurs.append(f"Objectif {i}: poids invalide: {poids}")

            if erreurs:
                print(f"  [ERREUR] {len(erreurs)} probleme(s) trouve(s):")
                for erreur in erreurs:
                    print(f"    - {erreur}")
                erreurs_totales += len(erreurs)
            else:
                print("  [OK] Validation reussie")
                succes_totaux += 1

        except json.JSONDecodeError as e:
            print(f"  [ERREUR] JSON invalide: {e}")
            erreurs_totales += 1
        except Exception as e:
            print(f"  [ERREUR] Erreur inattendue: {e}")
            erreurs_totales += 1

        print()

    # Résumé
    print("=" * 60)
    print(f"RESULTAT: {succes_totaux}/{len(fichiers_json)} instances valides")
    if erreurs_totales > 0:
        print(f"ATTENTION: {erreurs_totales} erreur(s) totale(s) detectee(s)")
    else:
        print("SUCCES: Toutes les instances sont valides!")
    print("=" * 60)


if __name__ == "__main__":
    valider_instances()
