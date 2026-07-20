"""Script de génération de solveur - MODE PAR DÉFAUT : Multi-Agents.

Ce script utilise le pipeline multi-agents (9 agents) comme mode par défaut
pour bénéficier de :
- Plan technique structuré (Architecte)
- Revue de code automatique (Reviewer)
- Correction automatique des bugs (Debugger)
- Tests unitaires générés (Testeur)
- Optimisation du code (Optimiseur)
- Documentation complète (Documentation)

Mode simple (1 seul agent) : Utilisez scripts/generer_solveur_simple.py
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Ajouter le projet au PYTHONPATH
projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger le fichier .env
try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass

# Imports
try:
    from generation.pipeline_multi_agents import tenter_generation_multi_agents
    from generation.agents.client_llm import construire_appel_llm
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    sys.exit(1)


def main():
    """Génère un solveur avec le pipeline multi-agents (mode par défaut)."""

    print("\n" + "🤖" * 35)
    print("  GÉNÉRATION DE SOLVEUR")
    print("  Mode : Pipeline Multi-Agents (9 agents)")
    print("🤖" * 35 + "\n")

    # Configuration
    provider = os.getenv('PRISME_LLM_PROVIDER', 'mistral')
    print(f"🔧 Configuration :")
    print(f"   Provider : {provider}")
    print(f"   Mode : Multi-Agents (recommandé)")
    print()

    # Client LLM
    try:
        appel_llm = construire_appel_llm()
    except Exception as e:
        print(f"❌ Erreur : {e}")
        print("\nVérifiez votre configuration dans .env :")
        print("  - PRISME_LLM_PROVIDER")
        print("  - MISTRAL_API_KEY (ou ANTHROPIC_API_KEY, OPENAI_API_KEY)")
        sys.exit(1)

    # Lancement
    print("🚀 Lancement du pipeline...")
    print("   ⏱️  Durée estimée : 2-5 minutes")
    print("   💰 Coût estimé : ~$0.50-1.00")
    print()
    print("📋 Agents qui vont travailler :")
    print("   1. Orchestrateur  → Planifie")
    print("   2. Analyste       → Analyse")
    print("   3. Architecte     → Conçoit")
    print("   4. Développeur    → Code")
    print("   5. Testeur        → Tests")
    print("   6. Reviewer       → Revoit")
    print("   7. Debugger       → Corrige (si besoin)")
    print("   8. Optimiseur     → Optimise")
    print("   9. Documentation  → Documente")
    print()

    try:
        resultat = tenter_generation_multi_agents(appel_llm)
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Résultats
    print("\n" + "=" * 70)
    print("  RÉSULTATS")
    print("=" * 70 + "\n")

    # Code final
    chemin_code = projet_root / "solveur_genere.py"
    with open(chemin_code, "w", encoding="utf-8") as f:
        f.write(resultat.code_final)
    print(f"✅ Code généré : {chemin_code}")
    print(f"   {len(resultat.code_final)} caractères")

    # Tests
    if resultat.tests_generes:
        chemin_tests = projet_root / "test_solveur_genere.py"
        with open(chemin_tests, "w", encoding="utf-8") as f:
            f.write(resultat.tests_generes)
        print(f"✅ Tests générés : {chemin_tests}")
        print(f"   {len(resultat.tests_generes)} caractères")

    # Documentation
    if resultat.documentation:
        chemin_doc = projet_root / "solveur_genere_doc.md"
        with open(chemin_doc, "w", encoding="utf-8") as f:
            f.write(resultat.documentation)
        print(f"✅ Documentation : {chemin_doc}")

    # Revue
    print(f"\n📊 Revue de code : {'✅ Approuvé' if resultat.revue.approuve else '❌ Rejeté'}")
    if not resultat.revue.approuve:
        print(f"   Commentaires : {resultat.revue.commentaires[:200]}...")

    # Corrections
    if resultat.code_corrige:
        print(f"🐛 Debugger : Code corrigé automatiquement")

    # Validation
    print(f"\n🔍 Validation :")
    print(f"   Statique : {'✅' if resultat.validation_statique.valide else '❌'}")
    print(f"   Exécution : {'✅' if not resultat.erreur_execution else '❌'}")
    if resultat.erreur_execution:
        print(f"      Erreur : {resultat.erreur_execution[:150]}...")

    if resultat.verdict_cascade:
        print(f"   Cascade : {resultat.verdict_cascade}")

    # Statut final
    print(f"\n{'='*70}")
    if resultat.reussi:
        print("✅ SUCCÈS - Solveur prêt pour enregistrement")
    else:
        print("❌ ÉCHEC - Corrections nécessaires")
    print(f"{'='*70}\n")

    # Prochaines étapes
    print("🎯 Prochaines étapes :")
    if resultat.reussi:
        print("   1. Examinez le code : cat solveur_genere.py")
        print("   2. Lancez les tests : pytest test_solveur_genere.py")
        print("   3. Enregistrez : registre.enregistrer(...)")
    else:
        print("   1. Examinez l'erreur ci-dessus")
        print("   2. Corrigez le code manuellement")
        print("   3. Relancez la génération")
    print()


if __name__ == "__main__":
    main()
