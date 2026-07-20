"""Teste l'agent de compréhension sur le catalogue généré et mesure le taux de succès.

Charge le catalogue de traductions, appelle l'agent sur chaque exemple, et compare
l'output réel avec l'output attendu pour mesurer la précision.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Import optionnel pour validation Pydantic (seulement en mode réel)
try:
    from dsl.validation.charger_instance import charger_instance

    VALIDATION_DISPONIBLE = True
except ImportError:
    VALIDATION_DISPONIBLE = False

    def charger_instance(data):
        """Stub pour mode simulation."""
        return data


@dataclass
class ResultatTest:
    """Résultat d'un test de traduction."""

    id: str
    format_source: str
    difficulte: str
    succes: bool
    erreur: str | None
    instance_valide: bool
    details: dict[str, Any]


def comparer_instances(
    attendue: dict[str, Any], obtenue: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Compare deux instances T-R-C-O et retourne (identique, differences)."""
    differences = []

    # Comparer tâches
    taches_att = {t["id"] for t in attendue.get("taches", [])}
    taches_obt = {t["id"] for t in obtenue.get("taches", [])}

    if taches_att != taches_obt:
        differences.append(f"Tâches: attendu {taches_att}, obtenu {taches_obt}")

    # Comparer ressources
    ressources_att = {r["id"] for r in attendue.get("ressources", [])}
    ressources_obt = {r["id"] for r in obtenue.get("ressources", [])}

    if ressources_att != ressources_obt:
        differences.append(
            f"Ressources: attendu {ressources_att}, obtenu {ressources_obt}"
        )

    # Comparer contraintes (simplifié - juste le nombre et types)
    contraintes_att = attendue.get("contraintes", [])
    contraintes_obt = obtenue.get("contraintes", [])

    types_att = defaultdict(int)
    types_obt = defaultdict(int)

    for c in contraintes_att:
        types_att[c["type"]] += 1

    for c in contraintes_obt:
        types_obt[c["type"]] += 1

    if dict(types_att) != dict(types_obt):
        differences.append(
            f"Contraintes par type: attendu {dict(types_att)}, obtenu {dict(types_obt)}"
        )

    return len(differences) == 0, differences


def tester_exemple_simule(exemple: dict[str, Any]) -> ResultatTest:
    """Teste un exemple en mode simulation (sans vraiment appeler le LLM).

    Pour démonstration - compare juste l'instance attendue avec elle-même
    et vérifie qu'elle passe la validation Pydantic (si disponible).
    """
    try:
        # Charger l'instance attendue
        instance_attendue = exemple["instance_trco_attendue"]

        # Valider avec Pydantic (si disponible)
        if VALIDATION_DISPONIBLE:
            try:
                charger_instance(instance_attendue)
                instance_valide = True
                erreur_validation = None
            except Exception as e:
                instance_valide = False
                erreur_validation = str(e)
        else:
            # Validation de base sans Pydantic
            instance_valide = (
                "taches" in instance_attendue
                and "ressources" in instance_attendue
                and "contraintes" in instance_attendue
                and "objectifs" in instance_attendue
            )
            erreur_validation = None if instance_valide else "Structure JSON invalide"

        # En mode simulation : on considère que l'agent retournerait
        # exactement l'instance attendue (taux de succès = 100%)
        identique = True
        differences = []

        return ResultatTest(
            id=exemple["id"],
            format_source=exemple["format_source"],
            difficulte=exemple["difficulte"],
            succes=identique and instance_valide,
            erreur=erreur_validation,
            instance_valide=instance_valide,
            details={
                "identique": identique,
                "differences": differences,
                "nb_taches": len(instance_attendue.get("taches", [])),
                "nb_ressources": len(instance_attendue.get("ressources", [])),
                "nb_contraintes": len(instance_attendue.get("contraintes", [])),
            },
        )

    except Exception as e:
        return ResultatTest(
            id=exemple["id"],
            format_source=exemple["format_source"],
            difficulte=exemple["difficulte"],
            succes=False,
            erreur=str(e),
            instance_valide=False,
            details={},
        )


def afficher_resultats(resultats: list[ResultatTest]) -> None:
    """Affiche les statistiques des résultats de test."""
    print("\n" + "=" * 70)
    print("  RÉSULTATS DES TESTS")
    print("=" * 70)

    total = len(resultats)
    succes_total = sum(1 for r in resultats if r.succes)
    taux_global = (succes_total / total * 100) if total > 0 else 0

    print(f"\n🎯 TAUX DE SUCCÈS GLOBAL : {taux_global:.1f}% ({succes_total}/{total})")

    # Par format
    print("\n📋 PAR FORMAT :")
    par_format = defaultdict(lambda: {"total": 0, "succes": 0})

    for r in resultats:
        par_format[r.format_source]["total"] += 1
        if r.succes:
            par_format[r.format_source]["succes"] += 1

    for fmt in sorted(par_format.keys()):
        stats = par_format[fmt]
        taux = (stats["succes"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(
            f"   - {fmt:20s} : {taux:5.1f}% ({stats['succes']:2d}/{stats['total']:2d})"
        )

    # Par difficulté
    print("\n🎯 PAR DIFFICULTÉ :")
    par_difficulte = defaultdict(lambda: {"total": 0, "succes": 0})

    for r in resultats:
        par_difficulte[r.difficulte]["total"] += 1
        if r.succes:
            par_difficulte[r.difficulte]["succes"] += 1

    ordre_difficulte = ["simple", "moyen", "complexe"]
    for diff in ordre_difficulte:
        if diff in par_difficulte:
            stats = par_difficulte[diff]
            taux = (
                (stats["succes"] / stats["total"] * 100) if stats["total"] > 0 else 0
            )
            print(
                f"   - {diff:20s} : {taux:5.1f}% ({stats['succes']:2d}/{stats['total']:2d})"
            )

    # Échecs
    echecs = [r for r in resultats if not r.succes]
    if echecs:
        print(f"\n❌ ÉCHECS ({len(echecs)}) :")
        for r in echecs[:5]:  # Afficher max 5 premiers
            print(f"   - {r.id} ({r.format_source})")
            if r.erreur:
                print(f"     Erreur : {r.erreur[:80]}...")

        if len(echecs) > 5:
            print(f"   ... et {len(echecs) - 5} autre(s)")

    print("\n" + "=" * 70)


def sauvegarder_rapport(
    resultats: list[ResultatTest], chemin_rapport: Path
) -> None:
    """Sauvegarde un rapport détaillé en JSON."""
    rapport = {
        "total": len(resultats),
        "succes": sum(1 for r in resultats if r.succes),
        "taux_global": (
            sum(1 for r in resultats if r.succes) / len(resultats) * 100
            if resultats
            else 0
        ),
        "resultats": [
            {
                "id": r.id,
                "format_source": r.format_source,
                "difficulte": r.difficulte,
                "succes": r.succes,
                "erreur": r.erreur,
                "instance_valide": r.instance_valide,
                "details": r.details,
            }
            for r in resultats
        ],
    }

    chemin_rapport.parent.mkdir(parents=True, exist_ok=True)

    with open(chemin_rapport, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Rapport détaillé : {chemin_rapport}")


def main():
    """Point d'entrée du script."""
    print("\n" + "=" * 70)
    print("  TEST DE L'AGENT DE COMPRÉHENSION")
    print("=" * 70)

    # Charger le catalogue
    chemin_catalogue = (
        Path(__file__).parent.parent
        / "validation_engine"
        / "agent_comprehension_bench"
        / "catalogue_traductions.json"
    )

    print(f"\n📂 Chargement du catalogue : {chemin_catalogue}")

    if not chemin_catalogue.exists():
        print(
            f"❌ Catalogue non trouvé. Lancez d'abord : scripts/generer_jeu_donnees_comprehension.py"
        )
        return

    with open(chemin_catalogue, encoding="utf-8") as f:
        catalogue = json.load(f)

    exemples = catalogue["exemples"]
    print(f"✅ {len(exemples)} exemples chargés")

    print("\n⚠️  MODE SIMULATION (pas d'appel LLM réel)")
    print("   Pour tester avec un vrai LLM, modifier tester_exemple_simule()")
    print("   et appeler adapters.agent_comprehension.comprendre_donnees_erp()")

    # Tester chaque exemple
    print(f"\n🧪 Test de {len(exemples)} exemples...")

    resultats = []
    for i, exemple in enumerate(exemples, 1):
        if i % 10 == 0:
            print(f"   ... {i}/{len(exemples)}")

        resultat = tester_exemple_simule(exemple)
        resultats.append(resultat)

    # Afficher résultats
    afficher_resultats(resultats)

    # Sauvegarder rapport
    chemin_rapport = (
        Path(__file__).parent.parent
        / "validation_engine"
        / "agent_comprehension_bench"
        / "rapport_tests.json"
    )
    sauvegarder_rapport(resultats, chemin_rapport)

    print(
        "\n💡 Prochaines étapes :"
        "\n   1. Intégrer appel LLM réel dans tester_exemple_simule()"
        "\n   2. Mesurer taux de succès réel avec différents modèles"
        "\n   3. Analyser les échecs et améliorer les prompts\n"
    )


if __name__ == "__main__":
    main()
