"""Exécution avec données GreenSig et solveur de référence.

Utilise le solveur minimal (scripts/_solveur_minimal.py) qui est
déjà validé, pour démontrer le MOMENT 2 sans dépendre de la génération.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))


def creer_instance_greensig_test():
    """Crée une instance GreenSig de test."""
    return {
        "types_tache": [
            {"id": 1, "nom_tache": "Tonte"},
            {"id": 2, "nom_tache": "Taille"},
            {"id": 3, "nom_tache": "Arrosage"},
        ],
        "equipes": [
            {"id": 100, "nom_equipe": "Équipe Nord", "actif": True},
            {"id": 200, "nom_equipe": "Équipe Sud", "actif": True},
        ],
        "competences": [],
        "operateurs": [],
        "taches": [
            {
                "id": 1,
                "id_type_tache_id": 1,
                "charge_estimee_heures": 2.0,
                "equipes_ids": [100, 200],
                "deleted_at": None,
            },
            {
                "id": 2,
                "id_type_tache_id": 2,
                "charge_estimee_heures": 1.5,
                "equipes_ids": [100],
                "deleted_at": None,
            },
            {
                "id": 3,
                "id_type_tache_id": 1,
                "charge_estimee_heures": 1.0,
                "equipes_ids": [200],
                "deleted_at": None,
            },
            {
                "id": 4,
                "id_type_tache_id": 3,
                "charge_estimee_heures": 0.5,
                "equipes_ids": [100, 200],
                "deleted_at": None,
            },
        ],
    }


def convertir_greensig_vers_trco(payload_dict):
    """Convertit GreenSig → T-R-C-O."""
    from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Ressource, Tache

    taches = [Tache(id=f"T{t['id']}") for t in payload_dict["taches"]]
    ressources = [Ressource(id=f"E{e['id']}") for e in payload_dict["equipes"]]

    contraintes = []
    for tache_gs in payload_dict["taches"]:
        tache_id = f"T{tache_gs['id']}"
        charge_h = tache_gs["charge_estimee_heures"]
        duree_min = int(charge_h * 60) if charge_h else 30

        for eq_id in tache_gs["equipes_ids"]:
            contraintes.append(CompatibiliteRessourceTache(tache=tache_id, ressource=f"E{eq_id}", duree=duree_min))

    return InstanceTRCO(
        taches=taches, ressources=ressources, contraintes=contraintes, objectifs=[MinimiserMakespan()]
    )


def main():
    print("\n" + "✅" * 35)
    print("  EXÉCUTION AVEC SOLVEUR DE RÉFÉRENCE + GREENSIG")
    print("✅" * 35 + "\n")

    # Données GreenSig
    print("=" * 70)
    print("  DONNÉES GREENSIG (FORMAT ERP)")
    print("=" * 70 + "\n")

    payload = creer_instance_greensig_test()

    print(f"📊 {len(payload['taches'])} tâches :\n")
    type_map = {t["id"]: t["nom_tache"] for t in payload["types_tache"]}
    eq_map = {e["id"]: e["nom_equipe"] for e in payload["equipes"]}

    for t in payload["taches"]:
        type_nom = type_map[t["id_type_tache_id"]]
        equipes = [eq_map[eid] for eid in t["equipes_ids"]]
        charge = f"{t['charge_estimee_heures']}h" if t["charge_estimee_heures"] else "Non définie"
        print(f"  • Tâche #{t['id']} - {type_nom}")
        print(f"    Charge : {charge}")
        print(f"    Équipes : {', '.join(equipes)}")
    print()

    # Conversion
    print("=" * 70)
    print("  CONVERSION GREENSIG → T-R-C-O")
    print("=" * 70 + "\n")

    instance = convertir_greensig_vers_trco(payload)
    print("✅ Instance T-R-C-O créée")
    print(f"  • Tâches : {[t.id for t in instance.taches]}")
    print(f"  • Ressources : {[r.id for r in instance.ressources]}")
    print(f"  • Contraintes : {len(instance.contraintes)}")
    print()

    # Solveur
    print("=" * 70)
    print("  EXÉCUTION DU SOLVEUR")
    print("=" * 70 + "\n")

    print("📦 Chargement du solveur de référence...\n")
    from scripts._solveur_minimal import resoudre

    print("⚙️  Résolution de l'instance GreenSig...\n")
    debut = time.time()
    planning = resoudre(instance)
    duree = time.time() - debut

    # Résultat
    print("=" * 70)
    print("  RÉSULTAT")
    print("=" * 70 + "\n")

    if planning is None:
        print("❌ INSTANCE INFAISABLE")
        sys.exit(1)

    print(f"✅ SOLUTION TROUVÉE en {duree:.3f}s\n")

    from dsl.schema import CompatibiliteRessourceTache

    operations_triees = sorted(planning.operations, key=lambda o: o.debut)

    print("📋 PLANNING :")
    print("─" * 70 + "\n")

    for op in operations_triees:
        # Durée
        duree_op = next(
            c.duree
            for c in instance.contraintes
            if isinstance(c, CompatibiliteRessourceTache) and c.tache == op.tache and c.ressource == op.ressource
        )
        fin = op.debut + duree_op

        # Infos GreenSig
        tache_id_gs = int(op.tache[1:])
        tache_gs = next(t for t in payload["taches"] if t["id"] == tache_id_gs)
        type_nom = type_map[tache_gs["id_type_tache_id"]]

        eq_id_gs = int(op.ressource[1:])
        eq_nom = eq_map[eq_id_gs]

        print(f"  • {op.tache} ({type_nom})")
        print(f"    Ressource : {op.ressource} ({eq_nom})")
        print(f"    Horaire : {op.debut} → {fin} min ({duree_op} min)")
        print()

    makespan = max(
        op.debut
        + next(
            c.duree
            for c in instance.contraintes
            if isinstance(c, CompatibiliteRessourceTache) and c.tache == op.tache and c.ressource == op.ressource
        )
        for op in operations_triees
    )

    print("─" * 70)
    print(f"\n🎯 MAKESPAN TOTAL : {makespan} minutes ({makespan / 60:.2f} heures)\n")

    # Statistiques
    print("=" * 70)
    print("  STATISTIQUES")
    print("=" * 70 + "\n")

    print(f"📊 Tâches GreenSig : {len(payload['taches'])}")
    print(f"📊 Équipes GreenSig : {len(payload['equipes'])}")
    print(f"📊 Opérations planifiées : {len(planning.operations)}")
    print(f"⏱️  Temps de résolution : {duree:.3f}s")
    print(f"🎯 Makespan : {makespan} minutes")
    print()

    print("=" * 70)
    print("  ✅ EXÉCUTION RÉUSSIE !")
    print("=" * 70 + "\n")

    print("🎉 Vous venez de voir le MOMENT 2 (Exécution) :")
    print("  • Données GreenSig (ERP) → Instance T-R-C-O (standard)")
    print("  • Solveur de référence → Planning optimal")
    print("  • Cycle complet sans régénération de code !")
    print()


if __name__ == "__main__":
    main()
