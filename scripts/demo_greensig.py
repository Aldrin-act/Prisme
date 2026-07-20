"""Démonstration de l'adaptateur GreenSig.

Montre comment des données GreenSig (format ERP) sont converties
en InstanceTRCO (format standard PRISME).
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

# Ajouter le projet au PYTHONPATH
projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Import direct pour éviter psycopg
import importlib.util
spec = importlib.util.spec_from_file_location(
    "schema_greensig",
    projet_root / "adapters" / "greensig" / "schema_greensig.py"
)
schema_greensig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema_greensig)

spec2 = importlib.util.spec_from_file_location(
    "translator",
    projet_root / "adapters" / "greensig" / "translator.py"
)
translator = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(translator)

EquipeGreenSIG = schema_greensig.EquipeGreenSIG
PayloadGreenSIG = schema_greensig.PayloadGreenSIG
TacheGreenSIG = schema_greensig.TacheGreenSIG
TypeTacheGreenSIG = schema_greensig.TypeTacheGreenSIG
OperateurGreenSIG = schema_greensig.OperateurGreenSIG
CompetenceGreenSIG = schema_greensig.CompetenceGreenSIG
traduire = translator.traduire
from dsl.schema import CompatibiliteRessourceTache, Precedence


def creer_donnees_greensig_exemple() -> PayloadGreenSIG:
    """Crée un exemple de données GreenSig (format ERP).

    Scénario : Gestion d'espaces verts
    - 4 tâches : Tonte, Taille, Désherbage, Arrosage
    - 3 équipes : Nord, Sud, Est
    - 5 compétences : Tonte, Taille, Désherbage, Arrosage, Binage
    - 6 opérateurs répartis dans les équipes
    """
    return PayloadGreenSIG(
        # Types de tâches (catalogue)
        types_tache=[
            TypeTacheGreenSIG(id=1, nom_tache="Tonte"),
            TypeTacheGreenSIG(id=2, nom_tache="Binage"),  # Type mappé
            TypeTacheGreenSIG(id=3, nom_tache="Taille d'arbres"),
            TypeTacheGreenSIG(id=4, nom_tache="Arrosage"),
        ],

        # Équipes (ressources planifiables)
        equipes=[
            EquipeGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True),
            EquipeGreenSIG(id=200, nom_equipe="Équipe Sud", actif=True),
            EquipeGreenSIG(id=300, nom_equipe="Équipe Est", actif=True),
        ],

        # Compétences disponibles
        competences=[
            CompetenceGreenSIG(id=21, nom_competence="Binage"),
            CompetenceGreenSIG(id=5, nom_competence="Binage des sols"),  # Doublon
            CompetenceGreenSIG(id=10, nom_competence="Tonte"),
            CompetenceGreenSIG(id=11, nom_competence="Taille"),
            CompetenceGreenSIG(id=12, nom_competence="Arrosage"),
        ],

        # Opérateurs (avec leurs compétences)
        operateurs=[
            # Équipe Nord
            OperateurGreenSIG(id=1, equipe_id=100, competences_ids=[10, 21]),  # Tonte + Binage
            OperateurGreenSIG(id=2, equipe_id=100, competences_ids=[11]),      # Taille

            # Équipe Sud
            OperateurGreenSIG(id=3, equipe_id=200, competences_ids=[21, 12]),  # Binage + Arrosage
            OperateurGreenSIG(id=4, equipe_id=200, competences_ids=[10]),      # Tonte

            # Équipe Est
            OperateurGreenSIG(id=5, equipe_id=300, competences_ids=[11, 12]),  # Taille + Arrosage
            OperateurGreenSIG(id=6, equipe_id=300, competences_ids=[5]),       # Binage (variante)
        ],

        # Tâches à planifier
        taches=[
            TacheGreenSIG(
                id=501,
                id_type_tache_id=1,  # Tonte
                charge_estimee_heures=2.5,
                equipes_ids=[100, 200],  # Affectation historique
                deleted_at=None
            ),
            TacheGreenSIG(
                id=502,
                id_type_tache_id=2,  # Binage (type mappé !)
                charge_estimee_heures=1.5,
                equipes_ids=[300],  # Affectation historique
                deleted_at=None
            ),
            TacheGreenSIG(
                id=503,
                id_type_tache_id=3,  # Taille
                charge_estimee_heures=3.0,
                equipes_ids=[100, 300],
                deleted_at=None
            ),
            TacheGreenSIG(
                id=504,
                id_type_tache_id=4,  # Arrosage
                charge_estimee_heures=None,  # Charge manquante → 30min par défaut
                equipes_ids=[200, 300],
                deleted_at=None
            ),
        ],
    )


def afficher_payload_greensig(payload: PayloadGreenSIG):
    """Affiche le payload GreenSig (format ERP)."""
    print("="*70)
    print("  DONNÉES GREENSIG (FORMAT ERP)")
    print("="*70 + "\n")

    print("📋 TYPES DE TÂCHES")
    print("─"*70)
    for tt in payload.types_tache:
        print(f"  • [{tt.id}] {tt.nom_tache}")
    print()

    print("👥 ÉQUIPES (Ressources)")
    print("─"*70)
    for eq in payload.equipes:
        print(f"  • [{eq.id}] {eq.nom_equipe} {'✅' if eq.actif else '❌'}")
    print()

    print("🎓 COMPÉTENCES")
    print("─"*70)
    for comp in payload.competences:
        print(f"  • [{comp.id}] {comp.nom_competence}")
    print()

    print("👤 OPÉRATEURS (avec compétences)")
    print("─"*70)
    for op in payload.operateurs:
        equipe = next((e.nom_equipe for e in payload.equipes if e.id == op.equipe_id), "Sans équipe")
        competences = [c.nom_competence for c in payload.competences if c.id in op.competences_ids]
        print(f"  • Opérateur #{op.id} - {equipe}")
        print(f"    Compétences : {', '.join(competences)}")
    print()

    print("📌 TÂCHES À PLANIFIER")
    print("─"*70)
    for tache in payload.taches:
        type_nom = next((t.nom_tache for t in payload.types_tache if t.id == tache.id_type_tache_id), "?")
        equipes_noms = [e.nom_equipe for e in payload.equipes if e.id in tache.equipes_ids]
        charge = f"{tache.charge_estimee_heures}h" if tache.charge_estimee_heures else "Non définie"
        print(f"  • Tâche #{tache.id} - {type_nom}")
        print(f"    Charge estimée : {charge}")
        print(f"    Équipes historiques : {', '.join(equipes_noms)}")
    print()


def afficher_instance_trco(instance):
    """Affiche l'InstanceTRCO (format standard PRISME)."""
    print("="*70)
    print("  INSTANCE T-R-C-O (FORMAT STANDARD PRISME)")
    print("="*70 + "\n")

    print("📌 TÂCHES")
    print("─"*70)
    for tache in instance.taches:
        print(f"  • {tache.id}")
    print()

    print("🏭 RESSOURCES")
    print("─"*70)
    for ressource in instance.ressources:
        print(f"  • {ressource.id}")
    print()

    print("🔗 CONTRAINTES")
    print("─"*70)

    # Compatibilités ressource-tâche
    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    print(f"\n  Compatibilités Ressource-Tâche : {len(compatibilites)}")
    for comp in sorted(compatibilites, key=lambda c: (c.tache, c.ressource)):
        print(f"    • {comp.tache} peut être faite par {comp.ressource} en {comp.duree} minutes")

    # Précédences
    precedences = [c for c in instance.contraintes if isinstance(c, Precedence)]
    print(f"\n  Précédences : {len(precedences)}")
    if precedences:
        for prec in precedences:
            print(f"    • {prec.avant} → {prec.apres}")
    else:
        print("    (aucune)")
    print()

    print("🎯 OBJECTIFS")
    print("─"*70)
    for obj in instance.objectifs:
        print(f"  • {obj.type}")
    print()


def main():
    print("\n" + "🌿"*35)
    print("  DÉMONSTRATION ADAPTATEUR GREENSIG")
    print("🌿"*35 + "\n")

    # 1. Créer données GreenSig
    print("📥 Création des données GreenSig (format ERP)...\n")
    payload = creer_donnees_greensig_exemple()

    # 2. Afficher payload GreenSig
    afficher_payload_greensig(payload)

    # 3. Conversion vers T-R-C-O
    print("="*70)
    print("  CONVERSION GreenSig → T-R-C-O")
    print("="*70 + "\n")

    print("🔄 Traduction en cours...\n")
    instance = traduire(payload)

    # 4. Afficher InstanceTRCO
    afficher_instance_trco(instance)

    # 5. Analyses
    print("="*70)
    print("  ANALYSES")
    print("="*70 + "\n")

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]

    print("📊 Statistiques :")
    print(f"  • Tâches GreenSig : {len(payload.taches)}")
    print(f"  • Tâches T-R-C-O : {len(instance.taches)}")
    print(f"  • Équipes GreenSig : {len(payload.equipes)}")
    print(f"  • Ressources T-R-C-O : {len(instance.ressources)}")
    print(f"  • Compatibilités générées : {len(compatibilites)}")
    print()

    # Analyse par tâche
    print("🔍 Détail par tâche :")
    for tache_gs in payload.taches:
        tache_id_trco = f"T{tache_gs.id}"
        comps_tache = [c for c in compatibilites if c.tache == tache_id_trco]
        type_nom = next((t.nom_tache for t in payload.types_tache if t.id == tache_gs.id_type_tache_id), "?")

        print(f"\n  Tâche #{tache_gs.id} ({type_nom})")
        print(f"    Charge GreenSig : {tache_gs.charge_estimee_heures}h")
        print(f"    Équipes historiques : {len(tache_gs.equipes_ids)}")
        print(f"    Ressources compatibles T-R-C-O : {len(comps_tache)}")

        if tache_gs.id_type_tache_id == 2:  # Binage (type mappé)
            print(f"    ⚠️  Type MAPPÉ : utilise compétences réelles, pas historique")

    print()

    # 6. Sauvegarder
    print("="*70)
    print("  SAUVEGARDE")
    print("="*70 + "\n")

    # Sauver payload GreenSig
    chemin_payload = projet_root / "greensig_payload.json"
    with open(chemin_payload, "w", encoding="utf-8") as f:
        json.dump(payload.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"📁 Payload GreenSig : {chemin_payload}")

    # Sauver instance T-R-C-O
    chemin_instance = projet_root / "greensig_instance_trco.json"
    with open(chemin_instance, "w", encoding="utf-8") as f:
        json.dump(instance.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"📁 Instance T-R-C-O : {chemin_instance}")

    print()


if __name__ == "__main__":
    main()
