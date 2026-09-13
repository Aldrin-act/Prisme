"""Génère un premier solveur avec le LLM sur une instance simple.

Script pédagogique pour comprendre la génération.
"""

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
    pass  # python-dotenv pas installé, pas grave si variables déjà définies

# Vérifier que les dépendances LLM sont installées
try:
    from dsl.validation.charger_instance import charger_instance_depuis_fichier

    from generation.tentative_unique import generer_et_valider
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    print("\nVérifiez que vous êtes dans le bon répertoire et que les modules existent.")
    sys.exit(1)


def main():
    """Génère un solveur sur une instance simple."""

    print("\n" + "🤖" * 35)
    print("  GÉNÉRATION D'UN SOLVEUR AVEC LE LLM")
    print("🤖" * 35 + "\n")

    # ========================================================================
    # 1. Charger l'instance
    # ========================================================================

    print("📋 Étape 1 : Chargement de l'instance")
    print("   Fichier : dsl/examples/valid/atelier_trois_taches.json")

    chemin_instance = Path(__file__).parent.parent / "dsl/examples/valid/atelier_trois_taches.json"

    if not chemin_instance.exists():
        print(f"❌ Fichier introuvable : {chemin_instance}")
        sys.exit(1)

    instance = charger_instance_depuis_fichier(str(chemin_instance))

    print("   ✅ Instance chargée :")
    print(f"      - {len(instance.taches)} tâches")
    print(f"      - {len(instance.ressources)} ressources")
    print(f"      - {len(instance.contraintes)} contraintes")
    print()

    # ========================================================================
    # 2. Génération
    # ========================================================================

    print("🤖 Étape 2 : Génération du code par le LLM")
    print("   ⏱️  Cela peut prendre 30-60 secondes...")
    print("   💰 Coût estimé : ~$0.05-0.10")
    print()

    client_id = "test_generation_1"

    try:
        resultat = generer_et_valider(instance, client_id=client_id)
    except Exception as e:
        print(f"❌ Erreur lors de la génération : {e}")
        print("\nVérifiez :")
        print("  1. Clé API configurée (OPENROUTER_API_KEY)")
        print("  2. Extra [llm] installé : uv sync --extra llm")
        sys.exit(1)

    # ========================================================================
    # 3. Résultats
    # ========================================================================

    print("\n" + "=" * 70)
    print("  RÉSULTATS DE LA GÉNÉRATION")
    print("=" * 70 + "\n")

    if resultat.succes:
        print("✅ GÉNÉRATION RÉUSSIE !")
        print(f"\n📊 Verdict de la cascade : {resultat.verdict}")

        # Sauvegarder le code
        chemin_output = Path(__file__).parent.parent / "solveur_genere.py"
        with open(chemin_output, "w", encoding="utf-8") as f:
            f.write(resultat.code_genere)

        print(f"\n💾 Code sauvegardé : {chemin_output}")
        print(f"   {len(resultat.code_genere)} caractères")

        # Afficher un extrait
        lignes = resultat.code_genere.split("\n")
        print("\n📄 Extrait (10 premières lignes) :")
        print("   " + "-" * 66)
        for ligne in lignes[:10]:
            print(f"   {ligne}")
        print("   " + "-" * 66)
        print(f"   ... et {len(lignes) - 10} lignes supplémentaires")

        # Diagnostic cascade
        if resultat.verdict:
            print("\n🔍 Détails de la validation :")
            print(f"   - Faisabilité : {resultat.verdict.faisabilite}")
            print(f"   - Optimalité : {resultat.verdict.optimalite}")
            print(f"   - Fidélité : {resultat.verdict.fidelite}")

        print("\n🎯 Prochaines étapes :")
        print("   1. Examinez le code généré : cat solveur_genere.py")
        print("   2. Enregistrez-le : [à implémenter]")
        print("   3. Testez l'exécution dans le sandbox")

    else:
        print("❌ GÉNÉRATION ÉCHOUÉE")
        print(f"\nErreur : {resultat.erreur}")

        if resultat.verdict:
            print(f"\nVerdict : {resultat.verdict}")
            print("\n🔍 Diagnostics :")

            if not resultat.verdict.faisabilite.tous_valides():
                print("   ❌ Faisabilité : échec")
                for diag in resultat.verdict.faisabilite.diagnostics:
                    if not diag.valide:
                        print(f"      - {diag.instance_id} : {diag.violations}")

            if not resultat.verdict.optimalite.tous_optimaux():
                print("   ❌ Optimalité : échec")

            if not resultat.verdict.fidelite.tous_fideles():
                print("   ❌ Fidélité : échec")

        print("\n💡 Le solveur généré ne passe pas la validation cascade.")
        print("   Ceci peut arriver avec des modèles moins performants.")
        print("   Essayez avec Claude Opus ou GPT-4.")

    print()


if __name__ == "__main__":
    main()
