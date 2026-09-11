"""Génération avec BOUCLE + Exécution avec données GreenSig.

Utilise le pipeline avec boucle de réparation (3 tentatives max)
pour augmenter les chances de succès.
"""

from __future__ import annotations

import sys
import os
import time
import json
from pathlib import Path

# Ajouter le projet au PYTHONPATH
projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger .env
try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass


def creer_instance_greensig_test():
    """Crée une instance GreenSig de test."""
    return {
        "types_tache": [
            {"id": 1, "nom_tache": "Tonte"},
            {"id": 2, "nom_tache": "Taille"},
        ],
        "equipes": [
            {"id": 100, "nom_equipe": "Équipe Nord", "actif": True},
            {"id": 200, "nom_equipe": "Équipe Sud", "actif": True},
        ],
        "competences": [],
        "operateurs": [],
        "taches": [
            {"id": 1, "id_type_tache_id": 1, "charge_estimee_heures": 2.0, "equipes_ids": [100, 200], "deleted_at": None},
            {"id": 2, "id_type_tache_id": 2, "charge_estimee_heures": 1.5, "equipes_ids": [100], "deleted_at": None},
            {"id": 3, "id_type_tache_id": 1, "charge_estimee_heures": 1.0, "equipes_ids": [200], "deleted_at": None},
        ],
    }


def convertir_greensig_vers_trco(payload_dict):
    """Convertit un payload GreenSig (dict) en InstanceTRCO."""
    from dsl.schema import (
        InstanceTRCO,
        Tache,
        Ressource,
        CompatibiliteRessourceTache,
        MinimiserMakespan,
    )

    taches = [Tache(id=f"T{t['id']}") for t in payload_dict["taches"]]
    ressources = [Ressource(id=f"E{e['id']}") for e in payload_dict["equipes"]]

    contraintes = []
    for tache_gs in payload_dict["taches"]:
        tache_id = f"T{tache_gs['id']}"
        charge_h = tache_gs["charge_estimee_heures"]
        duree_min = int(charge_h * 60) if charge_h else 30

        for eq_id in tache_gs["equipes_ids"]:
            ressource_id = f"E{eq_id}"
            contraintes.append(
                CompatibiliteRessourceTache(tache=tache_id, ressource=ressource_id, duree=duree_min)
            )

    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()]
    )


def main():
    print("\n" + "🔄"*35)
    print("  GÉNÉRATION AVEC BOUCLE + EXÉCUTION GREENSIG")
    print("🔄"*35 + "\n")

    # MOMENT 1 : GÉNÉRATION AVEC BOUCLE
    print("="*70)
    print("  MOMENT 1 : GÉNÉRATION AVEC BOUCLE DE RÉPARATION")
    print("="*70 + "\n")

    print("🔄 Pipeline avec boucle (max 3 tentatives de correction)...\n")

    debut_generation = time.time()

    try:
        from generation.graph import tenter_generation_avec_boucle

        resultat = tenter_generation_avec_boucle()

    except Exception as e:
        print(f"❌ Erreur durant la génération : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    duree_generation = time.time() - debut_generation

    # Afficher tentatives de la boucle
    print("\n" + "─"*70)
    print("  BOUCLE DE RÉPARATION")
    print("─"*70 + "\n")

    boucle = resultat.boucle_reparation
    print(f"Nombre de tentatives : {boucle.nombre_tentatives} / 3\n")

    for i, tentative in enumerate(boucle.tentatives, 1):
        print(f"Tentative #{i} :")
        print(f"  Reviewer : {'✅ APPROUVÉ' if tentative.revue.approuve else '❌ REJETÉ'}")
        if tentative.reussi:
            print(f"  Résultat : 🎉 SUCCÈS")
        else:
            print(f"  Résultat : 🔄 RETRY")
        print()

    if not resultat.reussi:
        print(f"\n❌ GÉNÉRATION ÉCHOUÉE après {duree_generation:.1f}s et {boucle.nombre_tentatives} tentatives")
        print("\n💡 Le Debugger a essayé de corriger mais n'a pas réussi après 3 tentatives.")
        print("   Ceci montre les limites du LLM sur ce problème complexe.")
        sys.exit(1)

    print(f"✅ Génération réussie en {duree_generation:.1f}s après {boucle.nombre_tentatives} tentative(s)")
    print(f"📏 Code généré : {len(resultat.code_final)} caractères\n")

    # Sauvegarder
    chemin_solveur = projet_root / "solveur_greensig_boucle.py"
    with open(chemin_solveur, "w", encoding="utf-8") as f:
        f.write(resultat.code_final)
    print(f"💾 Solveur sauvegardé : {chemin_solveur}\n")

    # MOMENT 2 : EXÉCUTION
    print("="*70)
    print("  MOMENT 2 : EXÉCUTION AVEC DONNÉES GREENSIG")
    print("="*70 + "\n")

    # Créer instance
    print("📥 Chargement des données GreenSig...\n")
    payload_greensig = creer_instance_greensig_test()
    instance_trco = convertir_greensig_vers_trco(payload_greensig)

    print(f"Instance : {len(instance_trco.taches)} tâches, {len(instance_trco.ressources)} ressources\n")

    # Charger solveur
    print("📦 Chargement du solveur...\n")
    from generation.executer import executer_code_genere
    solveur = executer_code_genere(resultat.code_final)

    # Exécuter
    print("⚙️  Résolution...\n")
    debut_resolution = time.time()
    planning = solveur(instance_trco)
    duree_resolution = time.time() - debut_resolution

    # Résultat
    print("="*70)
    print("  RÉSULTAT")
    print("="*70 + "\n")

    if planning is None:
        print("❌ INSTANCE INFAISABLE")
        sys.exit(1)

    print(f"✅ SOLUTION TROUVÉE en {duree_resolution:.3f}s\n")
    print(f"Opérations planifiées : {len(planning.operations)}\n")

    from dsl.schema import CompatibiliteRessourceTache
    for op in sorted(planning.operations, key=lambda o: o.debut):
        duree = next(c.duree for c in instance_trco.contraintes
                     if isinstance(c, CompatibiliteRessourceTache)
                     and c.tache == op.tache and c.ressource == op.ressource)
        print(f"  • {op.tache} sur {op.ressource} : début={op.debut} min, durée={duree} min")

    makespan = max(op.debut + next(c.duree for c in instance_trco.contraintes
                                    if isinstance(c, CompatibiliteRessourceTache)
                                    and c.tache == op.tache and c.ressource == op.ressource)
                   for op in planning.operations)

    print(f"\n🎯 MAKESPAN : {makespan} minutes ({makespan/60:.1f}h)\n")

    # Statistiques
    print("="*70)
    print("  STATISTIQUES")
    print("="*70 + "\n")

    print(f"⏱️  Génération : {duree_generation:.1f}s (avec {boucle.nombre_tentatives} tentative(s))")
    print(f"⏱️  Résolution : {duree_resolution:.3f}s")
    print(f"📊 Makespan : {makespan} minutes")
    print()

    print("✅ CYCLE COMPLET RÉUSSI AVEC BOUCLE DE RÉPARATION !\n")


if __name__ == "__main__":
    main()
