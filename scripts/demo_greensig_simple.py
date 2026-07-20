"""Démonstration simplifiée des données GreenSig.

Montre la structure des données GreenSig (format ERP) sans exécuter
la traduction complète (pour éviter les dépendances psycopg).
"""

from __future__ import annotations

import json
from pathlib import Path


def main():
    print("\n" + "🌿"*35)
    print("  STRUCTURE DES DONNÉES GREENSIG")
    print("🌿"*35 + "\n")

    # Exemple de données GreenSig (format JSON)
    payload_greensig = {
        "types_tache": [
            {"id": 1, "nom_tache": "Tonte"},
            {"id": 2, "nom_tache": "Binage"},
            {"id": 3, "nom_tache": "Taille d'arbres"},
            {"id": 4, "nom_tache": "Arrosage"},
        ],

        "equipes": [
            {"id": 100, "nom_equipe": "Équipe Nord", "actif": True},
            {"id": 200, "nom_equipe": "Équipe Sud", "actif": True},
            {"id": 300, "nom_equipe": "Équipe Est", "actif": True},
        ],

        "competences": [
            {"id": 21, "nom_competence": "Binage"},
            {"id": 5, "nom_competence": "Binage des sols"},
            {"id": 10, "nom_competence": "Tonte"},
            {"id": 11, "nom_competence": "Taille"},
            {"id": 12, "nom_competence": "Arrosage"},
        ],

        "operateurs": [
            {"id": 1, "equipe_id": 100, "competences_ids": [10, 21]},  # Tonte + Binage
            {"id": 2, "equipe_id": 100, "competences_ids": [11]},      # Taille
            {"id": 3, "equipe_id": 200, "competences_ids": [21, 12]},  # Binage + Arrosage
            {"id": 4, "equipe_id": 200, "competences_ids": [10]},      # Tonte
            {"id": 5, "equipe_id": 300, "competences_ids": [11, 12]},  # Taille + Arrosage
            {"id": 6, "equipe_id": 300, "competences_ids": [5]},       # Binage (variante)
        ],

        "taches": [
            {
                "id": 501,
                "id_type_tache_id": 1,  # Tonte
                "charge_estimee_heures": 2.5,
                "equipes_ids": [100, 200],
                "deleted_at": None
            },
            {
                "id": 502,
                "id_type_tache_id": 2,  # Binage
                "charge_estimee_heures": 1.5,
                "equipes_ids": [300],
                "deleted_at": None
            },
            {
                "id": 503,
                "id_type_tache_id": 3,  # Taille
                "charge_estimee_heures": 3.0,
                "equipes_ids": [100, 300],
                "deleted_at": None
            },
            {
                "id": 504,
                "id_type_tache_id": 4,  # Arrosage
                "charge_estimee_heures": None,  # Charge manquante
                "equipes_ids": [200, 300],
                "deleted_at": None
            },
        ],
    }

    # Affichage du payload
    print("="*70)
    print("  DONNÉES GREENSIG (FORMAT ERP)")
    print("="*70 + "\n")

    print("📋 TYPES DE TÂCHES")
    print("─"*70)
    for tt in payload_greensig["types_tache"]:
        print(f"  • [{tt['id']}] {tt['nom_tache']}")
    print()

    print("👥 ÉQUIPES (Ressources)")
    print("─"*70)
    for eq in payload_greensig["equipes"]:
        print(f"  • [{eq['id']}] {eq['nom_equipe']} {'✅' if eq['actif'] else '❌'}")
    print()

    print("🎓 COMPÉTENCES")
    print("─"*70)
    for comp in payload_greensig["competences"]:
        print(f"  • [{comp['id']}] {comp['nom_competence']}")
    print()

    print("👤 OPÉRATEURS (avec compétences)")
    print("─"*70)
    comp_map = {c["id"]: c["nom_competence"] for c in payload_greensig["competences"]}
    eq_map = {e["id"]: e["nom_equipe"] for e in payload_greensig["equipes"]}

    for op in payload_greensig["operateurs"]:
        equipe = eq_map.get(op["equipe_id"], "Sans équipe")
        competences = [comp_map[cid] for cid in op["competences_ids"]]
        print(f"  • Opérateur #{op['id']} - {equipe}")
        print(f"    Compétences : {', '.join(competences)}")
    print()

    print("📌 TÂCHES À PLANIFIER")
    print("─"*70)
    type_map = {t["id"]: t["nom_tache"] for t in payload_greensig["types_tache"]}

    for tache in payload_greensig["taches"]:
        type_nom = type_map.get(tache["id_type_tache_id"], "?")
        equipes_noms = [eq_map[eid] for eid in tache["equipes_ids"]]
        charge = f"{tache['charge_estimee_heures']}h" if tache["charge_estimee_heures"] else "Non définie"
        print(f"  • Tâche #{tache['id']} - {type_nom}")
        print(f"    Charge estimée : {charge}")
        print(f"    Équipes historiques : {', '.join(equipes_noms)}")
    print()

    # Conversion vers T-R-C-O (exemple simplifié)
    print("="*70)
    print("  APRÈS CONVERSION → T-R-C-O")
    print("="*70 + "\n")

    print("📌 TÂCHES (format T-R-C-O)")
    print("─"*70)
    for tache in payload_greensig["taches"]:
        print(f"  • T{tache['id']}")
    print()

    print("🏭 RESSOURCES (format T-R-C-O)")
    print("─"*70)
    for eq in payload_greensig["equipes"]:
        print(f"  • E{eq['id']} ({eq['nom_equipe']})")
    print()

    print("🔗 COMPATIBILITÉS RESSOURCE-TÂCHE (exemple)")
    print("─"*70)
    for tache in payload_greensig["taches"]:
        type_nom = type_map.get(tache["id_type_tache_id"], "?")
        duree_min = int(tache["charge_estimee_heures"] * 60) if tache["charge_estimee_heures"] else 30
        print(f"\n  Tâche T{tache['id']} ({type_nom}) :")
        for eq_id in tache["equipes_ids"]:
            eq_nom = eq_map[eq_id]
            print(f"    • Peut être faite par E{eq_id} ({eq_nom}) en {duree_min} minutes")
    print()

    # Statistiques
    print("="*70)
    print("  STATISTIQUES")
    print("="*70 + "\n")

    total_comps = sum(len(op["competences_ids"]) for op in payload_greensig["operateurs"])
    print(f"📊 Nombre de tâches : {len(payload_greensig['taches'])}")
    print(f"📊 Nombre d'équipes : {len(payload_greensig['equipes'])}")
    print(f"📊 Nombre d'opérateurs : {len(payload_greensig['operateurs'])}")
    print(f"📊 Nombre de compétences : {len(payload_greensig['competences'])}")
    print(f"📊 Compétences attribuées : {total_comps}")
    print()

    # Sauvegarder
    print("="*70)
    print("  SAUVEGARDE")
    print("="*70 + "\n")

    chemin = Path(__file__).parent.parent / "greensig_payload_exemple.json"
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(payload_greensig, f, indent=2, ensure_ascii=False)

    print(f"📁 Données sauvegardées : {chemin}")
    print()

    # Informations supplémentaires
    print("="*70)
    print("  INFORMATIONS IMPORTANTES")
    print("="*70 + "\n")

    print("🎯 Format GreenSig :")
    print("  • Provient d'un ERP réel de gestion d'espaces verts")
    print("  • Tables : api_planification_tache, api_users_equipe, etc.")
    print("  • Pas de précédences entre tâches (limitation de cet ERP)")
    print("  • Durée unique par tâche (pas de durée variable par équipe)")
    print()

    print("🔄 Conversion vers T-R-C-O :")
    print("  • Tâche GreenSig → Tâche T-R-C-O (ID: T{id})")
    print("  • Équipe GreenSig → Ressource T-R-C-O (ID: E{id})")
    print("  • Charge heures → Durée minutes (×60)")
    print("  • Équipes historiques → Compatibilités ressource-tâche")
    print("  • Type mappé (Binage) → Utilise compétences réelles")
    print()

    print("⚡ Pour tester la traduction complète :")
    print("  uv run pytest tests/unit/test_greensig_adapter.py")
    print()


if __name__ == "__main__":
    main()
