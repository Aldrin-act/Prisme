"""Démonstration avec les VRAIES données GreenSig (2165 tâches).

Extrait les données depuis la base PostgreSQL db_greensig (backup_20260503.sql)
et les convertit en InstanceTRCO via l'adaptateur greensig/.

Prérequis :
1. Docker Desktop démarré
2. docker compose --profile greensig up -d db_greensig
3. cmd /c "docker compose exec -T db_greensig psql -U greensig -d greensig -f - < backup_20260503.sql"
   (PowerShell) ou :
   docker compose exec -T db_greensig psql -U greensig -d greensig -f - < backup_20260503.sql
   (Bash/Git Bash)
"""

from __future__ import annotations

import sys
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger .env
try:
    from dotenv import load_dotenv

    load_dotenv(projet_root / ".env")
except ImportError:
    pass


def main():
    print("\n" + "🌿" * 35)
    print("  EXTRACTION GREENSIG - VRAIES DONNÉES")
    print("🌿" * 35 + "\n")

    # ═══════════════════════════════════════════════════════════════
    # EXTRACTION depuis la base PostgreSQL
    # ═══════════════════════════════════════════════════════════════

    print("=" * 70)
    print("  EXTRACTION DEPUIS DB_GREENSIG")
    print("=" * 70 + "\n")

    try:
        from adapters.greensig.extraction import extraire_payload
        from adapters.greensig.translator import traduire
    except ImportError as e:
        print(f"❌ Erreur d'import : {e}")
        print("\nVérifiez que psycopg est installé : uv sync --extra sandbox")
        sys.exit(1)

    print("📡 Connexion à la base GreenSig...")
    print("   (GREENSIG_DATABASE_URL depuis .env)\n")

    try:
        payload = extraire_payload()
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction : {e}\n")
        print("Vérifiez que :")
        print("  1. Docker Desktop est démarré")
        print("  2. Le conteneur db_greensig tourne :")
        print("     docker compose --profile greensig up -d db_greensig")
        print("  3. Le backup a été restauré :")
        print(  # noqa: E501 — commande shell à copier-coller telle quelle, ne pas la scinder
            '     PowerShell : cmd /c "docker compose exec -T db_greensig psql -U greensig -d greensig -f - < backup_20260503.sql"'
        )
        print(  # noqa: E501 — idem
            "     Bash/Git Bash : docker compose exec -T db_greensig psql -U greensig -d greensig -f - < backup_20260503.sql"
        )
        print()
        sys.exit(1)

    print("✅ Extraction réussie !\n")

    # ═══════════════════════════════════════════════════════════════
    # STATISTIQUES DU PAYLOAD GREENSIG
    # ═══════════════════════════════════════════════════════════════

    print("=" * 70)
    print("  PAYLOAD GREENSIG EXTRAIT")
    print("=" * 70 + "\n")

    print("📊 STATISTIQUES :")
    print(f"  • Tâches extraites : {len(payload.taches)}")
    print(f"  • Équipes : {len(payload.equipes)}")
    print(f"  • Types de tâches : {len(payload.types_tache)}")
    print(f"  • Opérateurs : {len(payload.operateurs)}")
    print(f"  • Compétences : {len(payload.competences)}")
    print()

    # Tâches supprimées
    taches_supprimees = [t for t in payload.taches if t.deleted_at is not None]
    print("📋 TÂCHES :")
    print(f"  • Actives : {len(payload.taches) - len(taches_supprimees)}")
    print(f"  • Supprimées (deleted_at) : {len(taches_supprimees)}")
    print()

    # Équipes actives/inactives
    equipes_actives = [e for e in payload.equipes if e.actif]
    equipes_inactives = [e for e in payload.equipes if not e.actif]
    print("👥 ÉQUIPES :")
    print(f"  • Actives : {len(equipes_actives)}")
    print(f"  • Inactives : {len(equipes_inactives)}")
    print()

    # Échantillon de types de tâches
    print("📝 TYPES DE TÂCHES (échantillon) :")
    for tt in payload.types_tache[:10]:
        print(f"  • [{tt.id}] {tt.nom_tache}")
    if len(payload.types_tache) > 10:
        print(f"  ... et {len(payload.types_tache) - 10} autres types")
    print()

    # ═══════════════════════════════════════════════════════════════
    # CONVERSION VERS T-R-C-O
    # ═══════════════════════════════════════════════════════════════

    print("=" * 70)
    print("  CONVERSION GREENSIG → T-R-C-O")
    print("=" * 70 + "\n")

    print("🔄 Traduction en cours...")
    print("   (filtre : équipes actives + tâches non supprimées)\n")

    try:
        instance = traduire(payload)
    except Exception as e:
        print(f"❌ Erreur lors de la traduction : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("✅ Instance T-R-C-O créée !\n")

    # ═══════════════════════════════════════════════════════════════
    # STATISTIQUES DE L'INSTANCE T-R-C-O
    # ═══════════════════════════════════════════════════════════════

    print("=" * 70)
    print("  INSTANCE T-R-C-O RÉSULTANTE")
    print("=" * 70 + "\n")

    from dsl.schema import CompatibiliteRessourceTache, Precedence

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    precedences = [c for c in instance.contraintes if isinstance(c, Precedence)]

    print("📊 STATISTIQUES :")
    print(f"  • Tâches : {len(instance.taches)}")
    print(f"  • Ressources : {len(instance.ressources)}")
    print(f"  • Contraintes : {len(instance.contraintes)}")
    print(f"    - Compatibilités ressource-tâche : {len(compatibilites)}")
    print(f"    - Précédences : {len(precedences)}")
    print(f"  • Objectifs : {len(instance.objectifs)}")
    print()

    # Distribution des compatibilités par tâche
    from collections import Counter

    compatibilites_par_tache = Counter(c.tache for c in compatibilites)

    print("📈 DISTRIBUTION DES COMPATIBILITÉS PAR TÂCHE :")
    min_comp = min(compatibilites_par_tache.values()) if compatibilites_par_tache else 0
    max_comp = max(compatibilites_par_tache.values()) if compatibilites_par_tache else 0
    avg_comp = (
        sum(compatibilites_par_tache.values()) / len(compatibilites_par_tache) if compatibilites_par_tache else 0
    )

    print(f"  • Min : {min_comp} équipes/tâche")
    print(f"  • Max : {max_comp} équipes/tâche")
    print(f"  • Moyenne : {avg_comp:.2f} équipes/tâche")
    print()

    # Tâches avec peu de compatibilités (goulots d'étranglement potentiels)
    taches_contraintes = [(tache, count) for tache, count in compatibilites_par_tache.items() if count <= 2]
    if taches_contraintes:
        print(f"⚠️  TÂCHES CONTRAINTES (≤2 équipes compatibles) : {len(taches_contraintes)}")
        for tache, count in sorted(taches_contraintes, key=lambda x: x[1])[:5]:
            print(f"  • {tache} : {count} équipe(s)")
        if len(taches_contraintes) > 5:
            print(f"  ... et {len(taches_contraintes) - 5} autres")
        print()

    # Durées
    durees = [c.duree for c in compatibilites]
    if durees:
        print("⏱️  DURÉES :")
        print(f"  • Min : {min(durees)} min")
        print(f"  • Max : {max(durees)} min")
        print(f"  • Moyenne : {sum(durees) / len(durees):.1f} min")
        print()

    # ═══════════════════════════════════════════════════════════════
    # SAUVEGARDE
    # ═══════════════════════════════════════════════════════════════

    print("=" * 70)
    print("  SAUVEGARDE")
    print("=" * 70 + "\n")

    import json

    # Payload GreenSig
    chemin_payload = projet_root / "greensig_payload_reel.json"
    with open(chemin_payload, "w", encoding="utf-8") as f:
        json.dump(payload.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"💾 Payload GreenSig : {chemin_payload}")
    print(f"   ({len(payload.taches)} tâches, {len(payload.equipes)} équipes)")

    # Instance T-R-C-O
    chemin_instance = projet_root / "greensig_instance_trco_reel.json"
    with open(chemin_instance, "w", encoding="utf-8") as f:
        json.dump(instance.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"💾 Instance T-R-C-O : {chemin_instance}")
    print(f"   ({len(instance.taches)} tâches, {len(instance.ressources)} ressources)")
    print()

    # ═══════════════════════════════════════════════════════════════
    # RÉSUMÉ
    # ═══════════════════════════════════════════════════════════════

    print("=" * 70)
    print("  ✅ EXTRACTION RÉUSSIE !")
    print("=" * 70 + "\n")

    print("🎉 Vous venez d'extraire les VRAIES données GreenSig :")
    print(f"  • {len(payload.taches)} tâches extraites de la base PostgreSQL")
    print(f"  • {len(instance.taches)} tâches actives dans l'instance T-R-C-O")
    print(f"  • {len(instance.ressources)} ressources actives")
    print(f"  • {len(compatibilites)} compatibilités dérivées")
    print()
    print("💡 Cette instance peut maintenant être passée au Benchmarker pour choisir l'algorithme adapté !")
    print()


if __name__ == "__main__":
    main()
