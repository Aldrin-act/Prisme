"""Exécution du solveur sur un SOUS-ENSEMBLE des données GreenSig.

Plus rapide et recommandé pour tester avant de résoudre les 2165 tâches complètes.

Permet de filtrer par:
- Nombre de tâches (ex: top 50, 100, 500)
- Type de tâche spécifique
- Équipe spécifique
- Durée (tâches courtes/longues)

Workflow:
1. Charge greensig_instance_trco_reel.json
2. Filtre un sous-ensemble selon vos critères
3. Résout avec le solveur de référence
4. Affiche les résultats et compare avec l'instance complète
"""

from __future__ import annotations

import sys
import json
import time
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))


def charger_instance_complete():
    """Charge l'instance T-R-C-O réelle complète."""
    chemin = projet_root / "greensig_instance_trco_reel.json"

    if not chemin.exists():
        print(f"❌ Fichier introuvable : {chemin}\n")
        print("Vous devez d'abord extraire les données :")
        print("   uv run python -m scripts.demo_greensig_vraies_donnees\n")
        sys.exit(1)

    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)

    from dsl.schema import InstanceTRCO
    return InstanceTRCO.model_validate(data)


def filtrer_top_n_taches(instance, n: int):
    """Garde les N premières tâches (par ordre d'ID)."""
    from dsl.schema import InstanceTRCO, CompatibiliteRessourceTache

    taches_gardees = instance.taches[:n]
    ids_taches = {t.id for t in taches_gardees}

    # Filtrer les contraintes
    contraintes_filtrees = [
        c for c in instance.contraintes
        if not isinstance(c, CompatibiliteRessourceTache) or c.tache in ids_taches
    ]

    # Ressources utilisées
    ressources_utilisees = {
        c.ressource for c in contraintes_filtrees
        if isinstance(c, CompatibiliteRessourceTache)
    }

    ressources_filtrees = [r for r in instance.ressources if r.id in ressources_utilisees]

    return InstanceTRCO(
        taches=taches_gardees,
        ressources=ressources_filtrees,
        contraintes=contraintes_filtrees,
        objectifs=instance.objectifs
    )


def filtrer_taches_courtes(instance, duree_max: int):
    """Garde uniquement les tâches ≤ duree_max minutes."""
    from dsl.schema import InstanceTRCO, CompatibiliteRessourceTache

    # Trouver les tâches courtes
    taches_courtes = set()
    for c in instance.contraintes:
        if isinstance(c, CompatibiliteRessourceTache) and c.duree <= duree_max:
            taches_courtes.add(c.tache)

    taches_filtrees = [t for t in instance.taches if t.id in taches_courtes]
    ids_taches = {t.id for t in taches_filtrees}

    # Filtrer contraintes
    contraintes_filtrees = [
        c for c in instance.contraintes
        if not isinstance(c, CompatibiliteRessourceTache) or c.tache in ids_taches
    ]

    # Ressources
    ressources_utilisees = {
        c.ressource for c in contraintes_filtrees
        if isinstance(c, CompatibiliteRessourceTache)
    }
    ressources_filtrees = [r for r in instance.ressources if r.id in ressources_utilisees]

    return InstanceTRCO(
        taches=taches_filtrees,
        ressources=ressources_filtrees,
        contraintes=contraintes_filtrees,
        objectifs=instance.objectifs
    )


def filtrer_par_ressource(instance, ressource_id: str):
    """Garde uniquement les tâches compatibles avec une ressource donnée."""
    from dsl.schema import InstanceTRCO, CompatibiliteRessourceTache

    # Tâches compatibles avec cette ressource
    taches_compatibles = {
        c.tache for c in instance.contraintes
        if isinstance(c, CompatibiliteRessourceTache) and c.ressource == ressource_id
    }

    taches_filtrees = [t for t in instance.taches if t.id in taches_compatibles]
    ids_taches = {t.id for t in taches_filtrees}

    # Contraintes
    contraintes_filtrees = [
        c for c in instance.contraintes
        if not isinstance(c, CompatibiliteRessourceTache) or c.tache in ids_taches
    ]

    # Ressources utilisées
    ressources_utilisees = {
        c.ressource for c in contraintes_filtrees
        if isinstance(c, CompatibiliteRessourceTache)
    }
    ressources_filtrees = [r for r in instance.ressources if r.id in ressources_utilisees]

    return InstanceTRCO(
        taches=taches_filtrees,
        ressources=ressources_filtrees,
        contraintes=contraintes_filtrees,
        objectifs=instance.objectifs
    )


def resoudre_instance(instance, timeout_seconds: int = 120):
    """Résout l'instance avec le solveur de référence."""
    from scripts._solveur_minimal import resoudre

    print(f"🚀 Démarrage de la résolution (timeout: {timeout_seconds}s)...\n")

    debut = time.time()
    planning = resoudre(instance, limite_temps_s=timeout_seconds)
    duree = time.time() - debut

    return planning, duree


def afficher_comparaison(instance_complete, instance_filtree):
    """Affiche la comparaison entre l'instance complète et filtrée."""
    print("="*70)
    print("  COMPARAISON")
    print("="*70 + "\n")

    print(f"Instance complète → Instance filtrée :")
    print(f"  • Tâches : {len(instance_complete.taches)} → {len(instance_filtree.taches)} "
          f"({len(instance_filtree.taches)/len(instance_complete.taches)*100:.1f}%)")
    print(f"  • Ressources : {len(instance_complete.ressources)} → {len(instance_filtree.ressources)} "
          f"({len(instance_filtree.ressources)/len(instance_complete.ressources)*100:.1f}%)")
    print(f"  • Contraintes : {len(instance_complete.contraintes)} → {len(instance_filtree.contraintes)} "
          f"({len(instance_filtree.contraintes)/len(instance_complete.contraintes)*100:.1f}%)")
    print()


def main():
    print("\n" + "🔬"*35)
    print("  RÉSOLUTION GREENSIG - SOUS-ENSEMBLE")
    print("🔬"*35 + "\n")

    # 1. Charger instance complète
    print("📂 Chargement de l'instance complète...\n")
    instance_complete = charger_instance_complete()

    print(f"✅ Instance chargée :")
    print(f"   • Tâches : {len(instance_complete.taches)}")
    print(f"   • Ressources : {len(instance_complete.ressources)}")
    print(f"   • Contraintes : {len(instance_complete.contraintes)}")
    print()

    # 2. Choisir le filtre
    print("="*70)
    print("  FILTRAGE")
    print("="*70 + "\n")

    print("Choisissez un filtre :\n")
    print("1. Top N tâches (ex: 50, 100, 500)")
    print("2. Tâches courtes (≤ X minutes)")
    print("3. Par ressource spécifique")
    print("4. Personnalisé (modifier le script)\n")

    choix = input("Votre choix [1-4] : ").strip()

    if choix == "1":
        n = input("Nombre de tâches à garder [défaut: 100] : ").strip()
        n = int(n) if n else 100
        print(f"\n🔍 Filtrage : top {n} tâches\n")
        instance_filtree = filtrer_top_n_taches(instance_complete, n)

    elif choix == "2":
        duree = input("Durée max en minutes [défaut: 60] : ").strip()
        duree = int(duree) if duree else 60
        print(f"\n🔍 Filtrage : tâches ≤ {duree} min\n")
        instance_filtree = filtrer_taches_courtes(instance_complete, duree)

    elif choix == "3":
        from dsl.schema import CompatibiliteRessourceTache
        ressources = sorted(set(
            c.ressource for c in instance_complete.contraintes
            if isinstance(c, CompatibiliteRessourceTache)
        ))
        print(f"\nRessources disponibles (échantillon) :")
        for r in ressources[:20]:
            nb_taches = sum(
                1 for c in instance_complete.contraintes
                if isinstance(c, CompatibiliteRessourceTache) and c.ressource == r
            )
            print(f"  • {r} : {nb_taches} tâches compatibles")
        if len(ressources) > 20:
            print(f"  ... et {len(ressources) - 20} autres")

        ressource = input("\nID ressource (ex: E100) : ").strip()
        print(f"\n🔍 Filtrage : tâches compatibles avec {ressource}\n")
        instance_filtree = filtrer_par_ressource(instance_complete, ressource)

    else:
        print("\n❌ Choix invalide. Utilisation du filtre par défaut (top 100).\n")
        instance_filtree = filtrer_top_n_taches(instance_complete, 100)

    # 3. Comparaison
    afficher_comparaison(instance_complete, instance_filtree)

    # 4. Résolution
    print("="*70)
    print("  RÉSOLUTION")
    print("="*70 + "\n")

    planning, duree = resoudre_instance(instance_filtree)

    # 5. Résultats
    print("="*70)
    print("  RÉSULTATS")
    print("="*70 + "\n")

    if planning is None:
        print(f"⚠️  AUCUNE SOLUTION TROUVÉE en {duree:.1f}s\n")
        print("💡 L'instance filtrée est peut-être infaisable.")
        print("   Essayez un autre filtre ou vérifiez les contraintes.\n")
        sys.exit(1)

    print(f"✅ SOLUTION TROUVÉE en {duree:.1f}s\n")

    from dsl.schema import CompatibiliteRessourceTache

    # Makespan
    makespan = 0
    for op in planning.operations:
        duree_op = next(
            c.duree for c in instance_filtree.contraintes
            if isinstance(c, CompatibiliteRessourceTache)
            and c.tache == op.tache
            and c.ressource == op.ressource
        )
        makespan = max(makespan, op.debut + duree_op)

    print("📊 STATISTIQUES :")
    print(f"   • Opérations planifiées : {len(planning.operations)}")
    print(f"   • Makespan : {makespan} min ({makespan/60:.1f}h)")
    print(f"   • Temps de résolution : {duree:.1f}s")
    print()

    # Timeline
    print("📅 TIMELINE (10 premières opérations) :")
    for op in sorted(planning.operations, key=lambda o: o.debut)[:10]:
        duree_op = next(
            c.duree for c in instance_filtree.contraintes
            if isinstance(c, CompatibiliteRessourceTache)
            and c.tache == op.tache
            and c.ressource == op.ressource
        )
        print(f"   • {op.tache} sur {op.ressource} : {op.debut} → {op.debut + duree_op} min")
    print()

    # 6. Sauvegarde
    print("="*70)
    print("  SAUVEGARDE")
    print("="*70 + "\n")

    chemin_instance = projet_root / "greensig_subset_instance.json"
    chemin_planning = projet_root / "greensig_subset_planning.json"

    with open(chemin_instance, "w", encoding="utf-8") as f:
        json.dump(instance_filtree.model_dump(), f, indent=2, ensure_ascii=False)

    with open(chemin_planning, "w", encoding="utf-8") as f:
        json.dump({
            "duree_resolution_secondes": duree,
            "planning": planning.model_dump()
        }, f, indent=2, ensure_ascii=False)

    print(f"💾 Instance filtrée : {chemin_instance}")
    print(f"💾 Planning : {chemin_planning}")
    print()

    # 7. Résumé
    print("="*70)
    print("  ✅ RÉSOLUTION RÉUSSIE !")
    print("="*70 + "\n")

    print("🎉 Le sous-ensemble a été résolu avec succès !")
    print(f"   • Tâches résolues : {len(instance_filtree.taches)}/{len(instance_complete.taches)}")
    print(f"   • Temps : {duree:.1f}s")
    print()
    print("💡 Si le résultat est satisfaisant, vous pouvez maintenant tenter")
    print("   l'instance complète avec :")
    print("   uv run python -m scripts.executer_greensig_2165_taches")
    print()


if __name__ == "__main__":
    main()
