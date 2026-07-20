"""Script de vérification rapide de la base GreenSig.

Vérifie que :
1. Docker est actif
2. Le conteneur db_greensig tourne
3. La base est accessible
4. Les données sont restaurées
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger .env
try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass


def verifier_docker():
    """Vérifie que Docker est actif."""
    print("🔍 Vérification de Docker...")
    try:
        subprocess.run(["docker", "ps"], capture_output=True, check=True, timeout=5)
        print("   ✅ Docker est actif\n")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("   ❌ Docker n'est pas actif ou pas installé")
        print("   ➡️  Lancez Docker Desktop et réessayez\n")
        return False


def verifier_conteneur():
    """Vérifie que db_greensig tourne."""
    print("🔍 Vérification du conteneur db_greensig...")
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )

        import json
        services = [json.loads(line) for line in result.stdout.strip().split('\n') if line]

        greensig_service = next((s for s in services if 'greensig' in s.get('Service', '')), None)

        if greensig_service and greensig_service.get('State') == 'running':
            health = greensig_service.get('Health', 'unknown')
            print(f"   ✅ Conteneur actif (health: {health})\n")
            return True
        else:
            print("   ❌ Conteneur db_greensig n'est pas actif")
            print("   ➡️  Lancez : docker compose --profile greensig up -d db_greensig\n")
            return False

    except Exception as e:
        print(f"   ❌ Impossible de vérifier le conteneur : {e}")
        print("   ➡️  Lancez : docker compose --profile greensig up -d db_greensig\n")
        return False


def verifier_connexion():
    """Vérifie que la base est accessible."""
    print("🔍 Vérification de la connexion PostgreSQL...")

    try:
        import psycopg
        from adapters.greensig.extraction import dsn_par_defaut

        # Adapter le DSN pour localhost (depuis l'hôte)
        dsn = os.environ.get("GREENSIG_DATABASE_URL", "")
        if "db_greensig" in dsn:
            # Remplacer db_greensig:5432 par localhost:5433
            dsn = dsn.replace("db_greensig:5432", "localhost:5433")

        with psycopg.connect(dsn, connect_timeout=5) as conn:
            print("   ✅ Connexion réussie\n")
            return True, conn

    except ImportError:
        print("   ❌ psycopg pas installé")
        print("   ➡️  Lancez : uv sync --extra sandbox\n")
        return False, None
    except Exception as e:
        print(f"   ❌ Connexion échouée : {e}")
        print("   ➡️  Vérifiez que le conteneur est actif et healthy\n")
        return False, None


def verifier_donnees(conn):
    """Vérifie que les données sont restaurées."""
    print("🔍 Vérification des données...")

    try:
        with conn.cursor() as cur:
            # Vérifier que les tables existent
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'api_planification_tache'
            """)

            if cur.fetchone()[0] == 0:
                print("   ❌ Table api_planification_tache n'existe pas")
                print("   ➡️  Restaurez le backup (voir GUIDE_GREENSIG.md)\n")
                return False

            # Compter les tâches
            cur.execute("SELECT COUNT(*) FROM api_planification_tache")
            nb_taches = cur.fetchone()[0]

            # Compter les équipes
            cur.execute("SELECT COUNT(*) FROM api_users_equipe")
            nb_equipes = cur.fetchone()[0]

            # Compter les opérateurs
            cur.execute("SELECT COUNT(*) FROM api_users_operateur WHERE statut = 'ACTIF'")
            nb_operateurs = cur.fetchone()[0]

            print(f"   ✅ Données trouvées :")
            print(f"      • Tâches : {nb_taches}")
            print(f"      • Équipes : {nb_equipes}")
            print(f"      • Opérateurs actifs : {nb_operateurs}")
            print()

            if nb_taches == 0:
                print("   ⚠️  Aucune tâche trouvée (restauration incomplète ?)")
                return False

            return True

    except Exception as e:
        print(f"   ❌ Erreur lors de la vérification : {e}\n")
        return False


def main():
    print("\n" + "="*70)
    print("  VÉRIFICATION GREENSIG")
    print("="*70 + "\n")

    checks = []

    # 1. Docker
    checks.append(("Docker", verifier_docker()))

    if not checks[-1][1]:
        afficher_resultat(checks)
        return

    # 2. Conteneur
    checks.append(("Conteneur db_greensig", verifier_conteneur()))

    if not checks[-1][1]:
        afficher_resultat(checks)
        return

    # 3. Connexion
    ok_connexion, conn = verifier_connexion()
    checks.append(("Connexion PostgreSQL", ok_connexion))

    if not ok_connexion:
        afficher_resultat(checks)
        return

    # 4. Données
    checks.append(("Données restaurées", verifier_donnees(conn)))
    conn.close()

    # Résumé
    afficher_resultat(checks)


def afficher_resultat(checks):
    """Affiche le résultat des vérifications."""
    print("="*70)
    print("  RÉSUMÉ")
    print("="*70 + "\n")

    for nom, ok in checks:
        status = "✅" if ok else "❌"
        print(f"{status} {nom}")

    print()

    if all(ok for _, ok in checks):
        print("🎉 Tout est prêt ! Vous pouvez lancer :")
        print("   uv run python -m scripts.demo_greensig_vraies_donnees")
        print()
    else:
        print("⚠️  Certaines vérifications ont échoué.")
        print("   Consultez GUIDE_GREENSIG.md pour l'installation complète.")
        print()


if __name__ == "__main__":
    main()
