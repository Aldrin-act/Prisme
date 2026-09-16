#!/usr/bin/env python3
"""
Validation des fichiers au format simplifié.

Vérifie que tous les fichiers JSON du répertoire format_simplifie respectent:
- Le schéma de base (taches, ressources, contraintes, objectifs)
- La cohérence des références (IDs de tâches/ressources)
- Les contraintes de précédence (pas de cycles)
- Les compétences (chaque compétence requise existe dans au moins une ressource)

Usage:
    uv run python -m scripts.valider_format_simplifie
"""

import json
import sys
from pathlib import Path
from typing import Any


def charger_fichier_json(chemin: Path) -> dict[str, Any] | None:
    """Charge un fichier JSON et retourne son contenu ou None en cas d'erreur."""
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERREUR {chemin.name}: Erreur JSON - {e}")
        return None
    except Exception as e:
        print(f"ERREUR {chemin.name}: Erreur lecture - {e}")
        return None


def valider_schema_base(data: dict[str, Any], nom_fichier: str) -> bool:
    """Vérifie que le schéma de base est présent."""
    champs_requis = ["taches", "ressources", "contraintes", "objectifs"]
    champs_manquants = [c for c in champs_requis if c not in data]

    if champs_manquants:
        print(f"ERREUR {nom_fichier}: Champs manquants: {', '.join(champs_manquants)}")
        return False

    if not data["taches"]:
        print(f"ERREUR {nom_fichier}: Aucune tache definie")
        return False

    if not data["ressources"]:
        print(f"ERREUR {nom_fichier}: Aucune ressource definie")
        return False

    return True


def valider_ids_taches(data: dict[str, Any], nom_fichier: str) -> bool:
    """Vérifie que chaque tâche a un ID unique et les champs requis."""
    ids_taches = set()
    for i, tache in enumerate(data["taches"]):
        if "id" not in tache:
            print(f"ERREUR {nom_fichier}: Tache #{i} sans ID")
            return False

        tid = tache["id"]
        if tid in ids_taches:
            print(f"ERREUR {nom_fichier}: ID tache duplique: {tid}")
            return False

        ids_taches.add(tid)

        if "nom" not in tache:
            print(f"ERREUR {nom_fichier}: Tache {tid} sans nom")
            return False

    return True


def valider_ids_ressources(data: dict[str, Any], nom_fichier: str) -> bool:
    """Vérifie que chaque ressource a un ID unique et les champs requis."""
    ids_ressources = set()
    for i, ressource in enumerate(data["ressources"]):
        if "id" not in ressource:
            print(f"ERREUR {nom_fichier}: Ressource #{i} sans ID")
            return False

        rid = ressource["id"]
        if rid in ids_ressources:
            print(f"ERREUR {nom_fichier}: ID ressource duplique: {rid}")
            return False

        ids_ressources.add(rid)

        if "nom" not in ressource:
            print(f"ERREUR {nom_fichier}: Ressource {rid} sans nom")
            return False

        if "competences" not in ressource:
            print(f"ERREUR {nom_fichier}: Ressource {rid} sans competences")
            return False

        if not isinstance(ressource["competences"], list):
            print(f"ERREUR {nom_fichier}: Ressource {rid} competences non liste")
            return False

        if not ressource["competences"]:
            print(f"WARNING {nom_fichier}: Ressource {rid} sans aucune competence (liste vide)")

    return True


def valider_contraintes_precedence(data: dict[str, Any], nom_fichier: str) -> bool:
    """Vérifie que les contraintes de précédence référencent des tâches valides."""
    ids_taches = {t["id"] for t in data["taches"]}

    for i, contrainte in enumerate(data["contraintes"]):
        if contrainte.get("type") != "precedence":
            continue

        if "avant" not in contrainte or "apres" not in contrainte:
            print(f"ERREUR {nom_fichier}: Contrainte precedence #{i} incomplete")
            return False

        avant = contrainte["avant"]
        apres = contrainte["apres"]

        if avant not in ids_taches:
            print(f"ERREUR {nom_fichier}: Contrainte precedence #{i} reference tache inconnue: {avant}")
            return False

        if apres not in ids_taches:
            print(f"ERREUR {nom_fichier}: Contrainte precedence #{i} reference tache inconnue: {apres}")
            return False

        if avant == apres:
            print(f"ERREUR {nom_fichier}: Contrainte precedence #{i} auto-reference: {avant}")
            return False

    return True


def valider_contraintes_competence(data: dict[str, Any], nom_fichier: str) -> bool:
    """Vérifie que chaque compétence requise existe dans au moins une ressource."""
    ids_taches = {t["id"] for t in data["taches"]}
    competences_disponibles = set()

    for ressource in data["ressources"]:
        competences_disponibles.update(ressource.get("competences", []))

    for i, contrainte in enumerate(data["contraintes"]):
        if contrainte.get("type") != "competence_requise":
            continue

        if "tache" not in contrainte or "competence" not in contrainte:
            print(f"ERREUR {nom_fichier}: Contrainte competence #{i} incomplete")
            return False

        tache = contrainte["tache"]
        competence = contrainte["competence"]

        if tache not in ids_taches:
            print(f"ERREUR {nom_fichier}: Contrainte competence #{i} reference tache inconnue: {tache}")
            return False

        if competence not in competences_disponibles:
            print(
                f"ERREUR {nom_fichier}: Competence '{competence}' requise pour {tache} mais absente des ressources"
            )
            return False

    return True


def detecter_cycles(data: dict[str, Any], nom_fichier: str) -> bool:
    """Détecte les cycles dans le graphe de précédence (DFS)."""
    ids_taches = {t["id"] for t in data["taches"]}

    # Construire le graphe
    graphe: dict[str, list[str]] = {tid: [] for tid in ids_taches}
    for contrainte in data["contraintes"]:
        if contrainte.get("type") == "precedence":
            avant = contrainte["avant"]
            apres = contrainte["apres"]
            graphe[avant].append(apres)

    # DFS pour détecter cycles
    visite = set()
    pile_recurrence = set()

    def dfs(noeud: str) -> bool:
        """Retourne True si cycle détecté."""
        visite.add(noeud)
        pile_recurrence.add(noeud)

        for voisin in graphe[noeud]:
            if voisin not in visite:
                if dfs(voisin):
                    return True
            elif voisin in pile_recurrence:
                print(f"ERREUR {nom_fichier}: Cycle detecte impliquant {noeud} -> {voisin}")
                return True

        pile_recurrence.remove(noeud)
        return False

    for tid in ids_taches:
        if tid not in visite:
            if dfs(tid):
                return False

    return True


def valider_fichier(chemin: Path) -> bool:
    """Valide un fichier complet. Retourne True si valide."""
    nom = chemin.name

    data = charger_fichier_json(chemin)
    if data is None:
        return False

    validations = [
        valider_schema_base(data, nom),
        valider_ids_taches(data, nom),
        valider_ids_ressources(data, nom),
        valider_contraintes_precedence(data, nom),
        valider_contraintes_competence(data, nom),
        detecter_cycles(data, nom),
    ]

    if all(validations):
        nb_taches = len(data["taches"])
        nb_ressources = len(data["ressources"])
        nb_contraintes = len(data["contraintes"])
        print(f"OK {nom}: VALID ({nb_taches} taches, {nb_ressources} ressources, {nb_contraintes} contraintes)")
        return True

    return False


def main() -> int:
    """Point d'entrée principal."""
    print("Validation des fichiers format_simplifie\n")

    # Chemin du répertoire format_simplifie
    repo_root = Path(__file__).parent.parent
    repertoire = repo_root / "data" / "donnees_brutes" / "format_simplifie"

    if not repertoire.exists():
        print(f"ERREUR: Repertoire introuvable: {repertoire}")
        return 1

    # Lister tous les fichiers JSON (sauf README et CATALOGUE)
    fichiers = sorted([f for f in repertoire.glob("*.json")], key=lambda x: x.name)

    if not fichiers:
        print(f"WARNING: Aucun fichier JSON trouve dans {repertoire}")
        return 1

    print(f"Repertoire: {repertoire}")
    print(f"Fichiers a valider: {len(fichiers)}\n")

    # Valider chaque fichier
    resultats = [valider_fichier(f) for f in fichiers]

    # Résumé
    nb_ok = sum(resultats)
    nb_ko = len(resultats) - nb_ok

    print(f"\n{'=' * 60}")
    print(f"OK: Fichiers valides: {nb_ok}/{len(resultats)}")
    if nb_ko > 0:
        print(f"ERREUR: Fichiers invalides: {nb_ko}/{len(resultats)}")
        return 1

    print("\nTous les fichiers sont valides!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
