"""Génération de solveur + Exécution avec données GreenSig.

Workflow complet :
1. MOMENT 1 (Génération) : Pipeline multi-agents génère le code
2. MOMENT 2 (Exécution) : Le code généré résout une instance GreenSig

Ce script montre le cycle complet Generate-Once, Execute-Many.
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
    """Crée une instance GreenSig de test (format dict pour éviter dépendances)."""
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
            {
                "id": 1,
                "id_type_tache_id": 1,
                "charge_estimee_heures": 2.0,
                "equipes_ids": [100, 200],
                "deleted_at": None
            },
            {
                "id": 2,
                "id_type_tache_id": 2,
                "charge_estimee_heures": 1.5,
                "equipes_ids": [100],
                "deleted_at": None
            },
            {
                "id": 3,
                "id_type_tache_id": 1,
                "charge_estimee_heures": 1.0,
                "equipes_ids": [200],
                "deleted_at": None
            },
        ],
    }


def convertir_greensig_vers_trco(payload_dict):
    """Convertit un payload GreenSig (dict) en InstanceTRCO.

    Version simplifiée sans importer l'adaptateur complet.
    """
    from dsl.schema import (
        InstanceTRCO,
        Tache,
        Ressource,
        CompatibiliteRessourceTache,
        MinimiserMakespan,
    )

    # Tâches
    taches = [
        Tache(id=f"T{t['id']}")
        for t in payload_dict["taches"]
    ]

    # Ressources (équipes)
    ressources = [
        Ressource(id=f"E{e['id']}")
        for e in payload_dict["equipes"]
    ]

    # Compatibilités ressource-tâche
    contraintes = []
    for tache_gs in payload_dict["taches"]:
        tache_id = f"T{tache_gs['id']}"
        charge_h = tache_gs["charge_estimee_heures"]
        duree_min = int(charge_h * 60) if charge_h else 30

        for eq_id in tache_gs["equipes_ids"]:
            ressource_id = f"E{eq_id}"
            contraintes.append(
                CompatibiliteRessourceTache(
                    tache=tache_id,
                    ressource=ressource_id,
                    duree=duree_min
                )
            )

    # Instance T-R-C-O
    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()]
    )


def main():
    print("\n" + "🚀"*35)
    print("  GÉNÉRATION + EXÉCUTION AVEC GREENSIG")
    print("🚀"*35 + "\n")

    provider = os.getenv('PRISME_LLM_PROVIDER', 'mistral')
    print(f"📡 Provider LLM : {provider}\n")

    # ═══════════════════════════════════════════════════════════════
    # MOMENT 1 : GÉNÉRATION (Offline, une fois)
    # ═══════════════════════════════════════════════════════════════

    print("="*70)
    print("  MOMENT 1 : GÉNÉRATION DU SOLVEUR")
    print("="*70 + "\n")

    print("🤖 Lancement du pipeline multi-agents...\n")
    print("Étapes :")
    print("  1. Orchestrateur → Plan général")
    print("  2. Analyste → Spécification")
    print("  3. Architecte → Modèle CP-SAT")
    print("  4. Développeur → Code Python")
    print("  5. Testeur → Tests pytest")
    print("  6. Reviewer → Revue de code")
    print("  7. Validation → Statique + Exécution + Cascade")
    print("  8. Optimiseur → Amélioration (si succès)")
    print("  9. Documentation → Doc Markdown")
    print()

    debut_generation = time.time()

    try:
        from generation.agents.client_llm import construire_appel_llm
        from generation.pipeline_multi_agents import tenter_generation_multi_agents

        appel_llm = construire_appel_llm()
        resultat = tenter_generation_multi_agents(appel_llm)

    except Exception as e:
        print(f"❌ Erreur durant la génération : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    duree_generation = time.time() - debut_generation

    if not resultat.reussi:
        print(f"\n❌ GÉNÉRATION ÉCHOUÉE après {duree_generation:.1f}s")
        if resultat.erreur_execution:
            print(f"Erreur : {resultat.erreur_execution}")
        sys.exit(1)

    print(f"✅ Génération réussie en {duree_generation:.1f}s ({duree_generation/60:.1f} min)")
    print(f"📏 Code généré : {len(resultat.code_final)} caractères")
    print()

    # Sauvegarder le code
    chemin_solveur = projet_root / "solveur_greensig.py"
    with open(chemin_solveur, "w", encoding="utf-8") as f:
        f.write(resultat.code_final)
    print(f"💾 Solveur sauvegardé : {chemin_solveur}")
    print()

    # ═══════════════════════════════════════════════════════════════
    # MOMENT 2 : EXÉCUTION (Runtime, avec données GreenSig)
    # ═══════════════════════════════════════════════════════════════

    print("="*70)
    print("  MOMENT 2 : EXÉCUTION AVEC DONNÉES GREENSIG")
    print("="*70 + "\n")

    # 1. Créer données GreenSig
    print("📥 Chargement des données GreenSig...\n")
    payload_greensig = creer_instance_greensig_test()

    print("Données GreenSig :")
    print(f"  • {len(payload_greensig['taches'])} tâches")
    print(f"  • {len(payload_greensig['equipes'])} équipes")
    print()

    for t in payload_greensig["taches"]:
        type_nom = next((tt["nom_tache"] for tt in payload_greensig["types_tache"] if tt["id"] == t["id_type_tache_id"]), "?")
        charge = f"{t['charge_estimee_heures']}h" if t["charge_estimee_heures"] else "Non définie"
        print(f"  Tâche #{t['id']} : {type_nom} ({charge})")
    print()

    # 2. Conversion GreenSig → T-R-C-O
    print("🔄 Conversion GreenSig → T-R-C-O...\n")
    instance_trco = convertir_greensig_vers_trco(payload_greensig)

    print("Instance T-R-C-O :")
    print(f"  • Tâches : {[t.id for t in instance_trco.taches]}")
    print(f"  • Ressources : {[r.id for r in instance_trco.ressources]}")
    print(f"  • Contraintes : {len(instance_trco.contraintes)}")
    print()

    from dsl.schema import CompatibiliteRessourceTache
    compatibilites = [c for c in instance_trco.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    print("Compatibilités :")
    for comp in compatibilites:
        print(f"    • {comp.tache} + {comp.ressource} → {comp.duree} min")
    print()

    # 3. Charger le code généré
    print("📦 Chargement du solveur généré...\n")

    try:
        from generation.executer import executer_code_genere
        solveur = executer_code_genere(resultat.code_final)
        print("✅ Solveur chargé avec succès")
    except Exception as e:
        print(f"❌ Erreur au chargement : {e}")
        sys.exit(1)

    print()

    # 4. Exécution du solveur
    print("⚙️  Exécution du solveur sur l'instance GreenSig...\n")

    debut_resolution = time.time()

    try:
        planning = solveur(instance_trco)
    except Exception as e:
        print(f"❌ Erreur durant la résolution : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    duree_resolution = time.time() - debut_resolution

    # 5. Affichage du résultat
    print("="*70)
    print("  RÉSULTAT")
    print("="*70 + "\n")

    if planning is None:
        print("❌ INSTANCE INFAISABLE (aucune solution trouvée)")
        sys.exit(1)

    print(f"✅ SOLUTION TROUVÉE en {duree_resolution:.3f}s\n")

    print("📋 PLANNING GÉNÉRÉ :")
    print("─"*70)

    # Trier par date de début
    operations_triees = sorted(planning.operations, key=lambda op: op.debut)

    makespan = max(op.debut + next(
        c.duree for c in instance_trco.contraintes
        if isinstance(c, CompatibiliteRessourceTache)
        and c.tache == op.tache
        and c.ressource == op.ressource
    ) for op in operations_triees)

    for op in operations_triees:
        # Trouver la durée
        duree = next(
            c.duree for c in instance_trco.contraintes
            if isinstance(c, CompatibiliteRessourceTache)
            and c.tache == op.tache
            and c.ressource == op.ressource
        )
        fin = op.debut + duree

        # Nom de la tâche (depuis GreenSig)
        tache_id_gs = int(op.tache[1:])  # T1 → 1
        tache_gs = next((t for t in payload_greensig["taches"] if t["id"] == tache_id_gs), None)
        type_nom = "?"
        if tache_gs:
            type_nom = next(
                (tt["nom_tache"] for tt in payload_greensig["types_tache"] if tt["id"] == tache_gs["id_type_tache_id"]),
                "?"
            )

        # Nom de la ressource (depuis GreenSig)
        eq_id_gs = int(op.ressource[1:])  # E100 → 100
        eq_nom = next(
            (e["nom_equipe"] for e in payload_greensig["equipes"] if e["id"] == eq_id_gs),
            "?"
        )

        print(f"  • {op.tache} ({type_nom})")
        print(f"    Ressource : {op.ressource} ({eq_nom})")
        print(f"    Début : {op.debut} min")
        print(f"    Durée : {duree} min")
        print(f"    Fin : {fin} min")
        print()

    print("─"*70)
    print(f"🎯 MAKESPAN TOTAL : {makespan} minutes ({makespan/60:.1f} heures)")
    print()

    # ═══════════════════════════════════════════════════════════════
    # STATISTIQUES FINALES
    # ═══════════════════════════════════════════════════════════════

    print("="*70)
    print("  STATISTIQUES FINALES")
    print("="*70 + "\n")

    print("⏱️  DURÉES :")
    print(f"  • Génération du code : {duree_generation:.1f}s ({duree_generation/60:.1f} min)")
    print(f"  • Résolution instance : {duree_resolution:.3f}s")
    print(f"  • Total : {duree_generation + duree_resolution:.1f}s")
    print()

    print("📊 INSTANCE :")
    print(f"  • Tâches GreenSig : {len(payload_greensig['taches'])}")
    print(f"  • Équipes GreenSig : {len(payload_greensig['equipes'])}")
    print(f"  • Compatibilités T-R-C-O : {len(compatibilites)}")
    print()

    print("📋 SOLUTION :")
    print(f"  • Opérations planifiées : {len(planning.operations)}")
    print(f"  • Makespan : {makespan} minutes")
    print()

    print("💾 FICHIERS GÉNÉRÉS :")
    print(f"  • Solveur : {chemin_solveur}")
    print(f"  • Tests : test_solveur_genere.py")
    if resultat.documentation:
        print(f"  • Documentation : solveur_genere_doc.md")
    print()

    print("="*70)
    print("  ✅ CYCLE COMPLET RÉUSSI !")
    print("="*70 + "\n")

    print("🎉 Vous venez de voir le cycle Generate-Once, Execute-Many :")
    print("  1. MOMENT 1 : Les agents ont généré le code (une fois)")
    print("  2. MOMENT 2 : Le code a résolu une instance GreenSig (runtime)")
    print()
    print("💡 Le même code peut maintenant résoudre TOUTE instance GreenSig")
    print("   sans jamais appeler les agents à nouveau !")
    print()


if __name__ == "__main__":
    main()
