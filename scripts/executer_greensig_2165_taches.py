"""Exécution du solveur sur les VRAIES données GreenSig (2165 tâches).

⚠️ ATTENTION : Résoudre 2165 tâches avec le solveur de référence peut prendre beaucoup de temps
(minutes à heures selon la complexité). Un timeout est configuré par défaut.

Workflow:
1. Charge greensig_instance_trco_reel.json (généré par demo_greensig_vraies_donnees.py)
2. Utilise le solveur de référence (scripts/_solveur_minimal.py)
3. Configure un timeout raisonnable (300s par défaut)
4. Affiche la progression et les résultats

Prérequis:
- Avoir exécuté scripts/demo_greensig_vraies_donnees.py d'abord
- Le fichier greensig_instance_trco_reel.json doit exister
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))


def charger_instance_reelle():
    """Charge l'instance T-R-C-O réelle depuis le fichier JSON."""
    chemin = projet_root / "greensig_instance_trco_reel.json"

    if not chemin.exists():
        print(f"❌ Fichier introuvable : {chemin}\n")
        print("Vous devez d'abord extraire les données :")
        print("   uv run python -m scripts.demo_greensig_vraies_donnees\n")
        sys.exit(1)

    print(f"📂 Chargement : {chemin.name}")

    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)

    from dsl.schema import InstanceTRCO

    instance = InstanceTRCO.model_validate(data)

    print("✅ Instance chargée")
    print(f"   • Tâches : {len(instance.taches)}")
    print(f"   • Ressources : {len(instance.ressources)}")
    print(f"   • Contraintes : {len(instance.contraintes)}")
    print()

    return instance


def analyser_instance(instance):
    """Analyse la complexité de l'instance."""
    from dsl.schema import CompatibiliteRessourceTache

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]

    # Compatibilités par tâche
    comp_par_tache = {}
    for comp in compatibilites:
        comp_par_tache.setdefault(comp.tache, []).append(comp.ressource)

    nb_compatibilites = [len(ressources) for ressources in comp_par_tache.values()]

    print("=" * 70)
    print("  ANALYSE DE COMPLEXITÉ")
    print("=" * 70 + "\n")

    print("📊 Tailles :")
    print(f"   • Variables : ~{len(instance.taches) * len(instance.ressources)} (tâche × ressource)")
    print(f"   • Contraintes réelles : {len(compatibilites)}")
    print()

    print("📈 Flexibilité (équipes/tâche) :")
    print(f"   • Min : {min(nb_compatibilites)} équipe(s)")
    print(f"   • Max : {max(nb_compatibilites)} équipe(s)")
    print(f"   • Moyenne : {sum(nb_compatibilites) / len(nb_compatibilites):.1f} équipe(s)")
    print()

    # Tâches contraintes
    taches_contraintes = [(t, nb) for t, nb in zip(comp_par_tache.keys(), nb_compatibilites) if nb == 1]
    if taches_contraintes:
        print(f"⚠️  Tâches FIXES (1 seule équipe) : {len(taches_contraintes)}")
        print("   → Simplifient le problème (pas de choix)")
        print()

    # Estimation de difficulté
    if len(instance.taches) > 1000:
        print("⚠️  INSTANCE TRÈS GRANDE (>1000 tâches)")
        print("   • le solveur de référence peut prendre plusieurs minutes")
        print("   • Un timeout est fortement recommandé")
        print("   • Considérez filtrer un sous-ensemble pour tester")
        print()


def resoudre_avec_timeout(instance, timeout_seconds: int = 300):
    """Résout l'instance avec un timeout."""
    print("=" * 70)
    print("  RÉSOLUTION (solveur de référence)")
    print("=" * 70 + "\n")

    print(f"⏱️  Timeout configuré : {timeout_seconds}s ({timeout_seconds / 60:.1f} min)\n")

    try:
        # Import du solveur minimal avec timeout intégré
        from scripts._solveur_minimal import resoudre
    except ImportError:
        print("❌ Impossible d'importer le solveur de référence")
        print("   Vérifiez que scripts/_solveur_minimal.py existe")
        sys.exit(1)

    print("🚀 Démarrage de la résolution...\n")
    print("   le solveur de référence construit un planning par liste")
    print("   ou atteindre le timeout. Patience...\n")

    debut = time.time()

    try:
        # Le solveur minimal accepte un paramètre limite_temps_s
        planning = resoudre(instance, limite_temps_s=timeout_seconds)
        duree = time.time() - debut

    except Exception as e:
        duree = time.time() - debut
        print(f"\n❌ ERREUR durant la résolution ({duree:.1f}s) : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    return planning, duree


def afficher_resultats(instance, planning, duree):
    """Affiche les résultats de la résolution."""
    print("=" * 70)
    print("  RÉSULTATS")
    print("=" * 70 + "\n")

    if planning is None:
        print(f"⚠️  AUCUNE SOLUTION TROUVÉE en {duree:.1f}s\n")
        print("Raisons possibles :")
        print("  • Instance infaisable (contraintes contradictoires)")
        print("  • Timeout atteint avant de trouver une solution")
        print("  • le solveur de référence n'a pas trouvé de planning légal")
        print()
        print("💡 Suggestions :")
        print("  • Augmenter le timeout")
        print("  • Vérifier la faisabilité de l'instance")
        print("  • Tester sur un sous-ensemble de tâches d'abord")
        print()
        return False

    print(f"✅ SOLUTION TROUVÉE en {duree:.1f}s ({duree / 60:.1f} min)\n")

    from dsl.schema import CompatibiliteRessourceTache

    # Calculer makespan
    makespan = 0
    for op in planning.operations:
        duree_op = next(
            c.duree
            for c in instance.contraintes
            if isinstance(c, CompatibiliteRessourceTache) and c.tache == op.tache and c.ressource == op.ressource
        )
        fin = op.debut + duree_op
        makespan = max(makespan, fin)

    print("📊 STATISTIQUES :")
    print(f"   • Opérations planifiées : {len(planning.operations)}")
    print(f"   • Makespan total : {makespan} min ({makespan / 60:.1f}h)")
    print(f"   • Temps de résolution : {duree:.1f}s")
    print()

    # Utilisation des ressources
    from collections import Counter

    utilisation = Counter(op.ressource for op in planning.operations)

    print("🏭 UTILISATION DES RESSOURCES (top 10) :")
    for ressource, nb_ops in utilisation.most_common(10):
        print(f"   • {ressource} : {nb_ops} opérations")
    print()

    # Timeline (échantillon)
    print("📅 TIMELINE (10 premières opérations) :")
    operations_triees = sorted(planning.operations, key=lambda o: o.debut)[:10]

    for op in operations_triees:
        duree_op = next(
            c.duree
            for c in instance.contraintes
            if isinstance(c, CompatibiliteRessourceTache) and c.tache == op.tache and c.ressource == op.ressource
        )
        fin = op.debut + duree_op
        print(f"   • {op.tache} sur {op.ressource} : {op.debut} → {fin} min ({duree_op} min)")

    if len(planning.operations) > 10:
        print(f"   ... et {len(planning.operations) - 10} autres opérations")
    print()

    return True


def sauvegarder_planning(planning, duree):
    """Sauvegarde le planning dans un fichier JSON."""
    print("=" * 70)
    print("  SAUVEGARDE")
    print("=" * 70 + "\n")

    chemin = projet_root / "greensig_planning_reel.json"

    resultat = {"duree_resolution_secondes": duree, "planning": planning.model_dump() if planning else None}

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(resultat, f, indent=2, ensure_ascii=False)

    print(f"💾 Planning sauvegardé : {chemin}")
    print()


def main():
    print("\n" + "🚀" * 35)
    print("  RÉSOLUTION GREENSIG - 2165 TÂCHES RÉELLES")
    print("🚀" * 35 + "\n")

    # 1. Charger instance
    print("=" * 70)
    print("  CHARGEMENT DE L'INSTANCE")
    print("=" * 70 + "\n")

    instance = charger_instance_reelle()

    # 2. Analyser complexité
    analyser_instance(instance)

    # 3. Demander confirmation
    print("=" * 70)
    print("  CONFIRMATION")
    print("=" * 70 + "\n")

    print("⚠️  Vous allez résoudre une instance de production avec le solveur de référence.")
    print("   Cela peut prendre du temps selon la complexité.\n")

    reponse = input("Continuer ? [o/N] : ").strip().lower()
    if reponse not in ("o", "oui", "y", "yes"):
        print("\n❌ Annulé par l'utilisateur.\n")
        sys.exit(0)

    print()

    # 4. Résoudre
    planning, duree = resoudre_avec_timeout(instance, timeout_seconds=300)

    # 5. Afficher résultats
    succes = afficher_resultats(instance, planning, duree)

    # 6. Sauvegarder
    sauvegarder_planning(planning, duree)

    # 7. Résumé
    print("=" * 70)
    if succes:
        print("  ✅ RÉSOLUTION RÉUSSIE !")
    else:
        print("  ⚠️  RÉSOLUTION SANS SOLUTION")
    print("=" * 70 + "\n")

    if succes:
        print("🎉 Le planning a été généré avec succès !")
        print("   • Fichier : greensig_planning_reel.json")
        print()
    else:
        print("💡 Suggestions :")
        print("   • Essayez d'abord avec un sous-ensemble (voir scripts/executer_greensig_subset.py)")
        print("   • Vérifiez la faisabilité de l'instance")
        print("   • Augmentez le timeout si nécessaire")
        print()


if __name__ == "__main__":
    main()
