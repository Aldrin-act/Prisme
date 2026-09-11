"""Génère un solveur avec Kimi (Moonshot AI) (utilise le .env)."""

from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le projet au PYTHONPATH
projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger le fichier .env
try:
    from dotenv import load_dotenv

    load_dotenv(projet_root / ".env")
    print("✅ Fichier .env chargé")
except ImportError:
    print("⚠️  python-dotenv non installé, utilise les variables d'environnement système")

# Imports du projet
try:
    import json

    from dsl.validation.validator import charger_instance
    from generation.agents.client_llm import construire_modele
    from generation.tentative_unique import tenter_generation_unique
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    print("\nAssurez-vous d'être dans le dossier du projet.")
    sys.exit(1)


def main():
    """Génère un solveur sur une instance simple."""

    print("\n" + "🤖" * 35)
    print("  GÉNÉRATION D'UN SOLVEUR AVEC KIMI (MOONSHOT AI)")
    print("🤖" * 35 + "\n")

    # ========================================================================
    # 1. Charger l'instance
    # ========================================================================

    print("📋 Étape 1 : Chargement de l'instance")

    chemin_instance = projet_root / "dsl/examples/valid/atelier_trois_taches.json"

    if not chemin_instance.exists():
        print(f"❌ Fichier introuvable : {chemin_instance}")
        sys.exit(1)

    try:
        with open(chemin_instance, encoding="utf-8") as f:
            instance_data = json.load(f)
        instance = charger_instance(instance_data)
        print("   ✅ Instance chargée :")
        print(f"      - {len(instance.taches)} tâches")
        print(f"      - {len(instance.ressources)} ressources")
        print(f"      - {len(instance.contraintes)} contraintes")
        print()
    except Exception as e:
        print(f"❌ Erreur de chargement : {e}")
        sys.exit(1)

    # ========================================================================
    # 2. Créer le client LLM
    # ========================================================================

    print("🔧 Étape 2 : Configuration du client LLM")

    try:
        modele = construire_modele()
        print("   ✅ Client Kimi créé")
        print()
    except Exception as e:
        print(f"❌ Erreur de configuration LLM : {e}")
        print("\nVérifiez :")
        print("  - KIMI_API_KEY dans .env")
        sys.exit(1)

    # ========================================================================
    # 3. Génération
    # ========================================================================

    print("🤖 Étape 3 : Génération du code par le LLM")
    print("   ⏱️  Cela peut prendre 30-90 secondes...")
    print("   💰 Coût estimé avec Kimi : ~$0.01-0.05")
    print()

    try:
        resultat = tenter_generation_unique(modele)

    except Exception as e:
        print(f"❌ Erreur lors de la génération : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # ========================================================================
    # 4. Résultats
    # ========================================================================

    print("\n" + "=" * 70)
    print("  RÉSULTATS DE LA GÉNÉRATION")
    print("=" * 70 + "\n")

    if resultat.code_source:
        print("✅ CODE GÉNÉRÉ AVEC SUCCÈS !")

        # Sauvegarder le code
        chemin_output = projet_root / "solveur_genere.py"
        with open(chemin_output, "w", encoding="utf-8") as f:
            f.write(resultat.code_source)

        print(f"\n💾 Code sauvegardé : {chemin_output}")
        print(f"   {len(resultat.code_source)} caractères")

        # Afficher un extrait
        lignes = resultat.code_source.split("\n")
        print("\n📄 Extrait (15 premières lignes) :")
        print("   " + "-" * 66)
        for ligne in lignes[:15]:
            print(f"   {ligne}")
        print("   " + "-" * 66)
        if len(lignes) > 15:
            print(f"   ... et {len(lignes) - 15} lignes supplémentaires")

        # Statut validation statique
        print(f"\n🔍 Validation statique : {resultat.validation_statique}")

        # Statut exécution
        if resultat.erreur_execution:
            print("\n❌ EXÉCUTION : Échec")
            print(f"   Erreur : {resultat.erreur_execution}")
        else:
            print("\n✅ EXÉCUTION : Succès")

        # Verdict cascade
        if resultat.verdict_cascade:
            print(f"\n📊 Verdict cascade : {resultat.verdict_cascade}")
        else:
            print("\n⚠️  Verdict cascade : Non disponible (cascade pas lancée)")

        print("\n🎯 Prochaines étapes :")
        print("   1. Examinez le code : cat solveur_genere.py")
        print("   2. Lancez la cascade complète pour validation")
        print("   3. Si VERT : enregistrez dans solver_store/")

    else:
        print("❌ GÉNÉRATION ÉCHOUÉE")
        print("\n❌ Aucun code généré")

    print()


if __name__ == "__main__":
    main()
