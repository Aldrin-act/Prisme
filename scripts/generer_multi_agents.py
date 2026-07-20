"""Génère un solveur avec le pipeline multi-agents (9 agents)."""

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
    print("✅ Fichier .env chargé")
    print(f"   Provider: {os.getenv('PRISME_LLM_PROVIDER')}")
except ImportError:
    print("⚠️  python-dotenv non installé")

# Imports du projet
try:
    from generation.pipeline_multi_agents import tenter_generation_multi_agents
    from generation.agents.client_llm import construire_appel_llm
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    sys.exit(1)


def main():
    """Génère un solveur avec le pipeline multi-agents complet."""

    print("\n" + "🤖" * 35)
    print("  GÉNÉRATION AVEC PIPELINE MULTI-AGENTS (9 AGENTS)")
    print("🤖" * 35 + "\n")

    print("📋 Pipeline complet :")
    print("   1. Orchestrateur → Planifie les étapes")
    print("   2. Analyste      → Analyse l'instance")
    print("   3. Architecte    → Conçoit le plan technique")
    print("   4. Développeur   → Génère le code")
    print("   5. Testeur       → Génère les tests")
    print("   6. Reviewer      → Revoit le code")
    print("   7. Debugger      → Corrige les bugs (si besoin)")
    print("   8. Optimiseur    → Optimise le code")
    print("   9. Documentation → Génère la doc")
    print()

    # Configuration LLM
    print("🔧 Configuration du client LLM...")
    try:
        appel_llm = construire_appel_llm()
        print(f"   ✅ Client {os.getenv('PRISME_LLM_PROVIDER', 'mistral')} créé")
        print()
    except Exception as e:
        print(f"❌ Erreur : {e}")
        sys.exit(1)

    # Lancement du pipeline
    print("🚀 Lancement du pipeline multi-agents...")
    print("   ⏱️  Durée estimée : 2-5 minutes")
    print("   💰 Coût estimé : ~$0.50-1.00")
    print("   📊 9 appels LLM séquentiels")
    print()

    try:
        resultat = tenter_generation_multi_agents(appel_llm)
    except Exception as e:
        print(f"❌ Erreur lors du pipeline : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Affichage des résultats
    print("\n" + "=" * 70)
    print("  RÉSULTATS DU PIPELINE MULTI-AGENTS")
    print("=" * 70 + "\n")

    # 1. Plan Orchestrateur
    print("📋 1. PLAN ORCHESTRATEUR")
    print(f"   {len(resultat.plan_orchestrateur)} étapes planifiées")
    for i, etape in enumerate(resultat.plan_orchestrateur, 1):
        print(f"   {i}. {etape}")
    print()

    # 2. Analyse
    print("🔍 2. ANALYSE")
    print(f"   Spécification : {len(resultat.specification)} caractères")
    lignes_spec = resultat.specification.split("\n")[:5]
    for ligne in lignes_spec:
        print(f"   {ligne}")
    if len(resultat.specification.split("\n")) > 5:
        print(f"   ... ({len(resultat.specification.split('\n')) - 5} lignes supplémentaires)")
    print()

    # 3. Plan Technique
    print("🏗️  3. PLAN TECHNIQUE (Architecte)")
    print(f"   Plan : {len(resultat.plan_technique)} caractères")
    lignes_plan = resultat.plan_technique.split("\n")[:5]
    for ligne in lignes_plan:
        print(f"   {ligne}")
    if len(resultat.plan_technique.split("\n")) > 5:
        print(f"   ... ({len(resultat.plan_technique.split('\n')) - 5} lignes supplémentaires)")
    print()

    # 4. Code Généré
    print("💻 4. CODE GÉNÉRÉ (Développeur)")
    print(f"   {len(resultat.code_genere)} caractères")

    # Sauvegarder le code initial
    chemin_code_initial = projet_root / "solveur_multi_agents_initial.py"
    with open(chemin_code_initial, "w", encoding="utf-8") as f:
        f.write(resultat.code_genere)
    print(f"   💾 Sauvegardé : {chemin_code_initial}")
    print()

    # 5. Tests
    print("🧪 5. TESTS GÉNÉRÉS (Testeur)")
    print(f"   {len(resultat.tests_generes)} caractères")
    chemin_tests = projet_root / "test_solveur_multi_agents.py"
    with open(chemin_tests, "w", encoding="utf-8") as f:
        f.write(resultat.tests_generes)
    print(f"   💾 Sauvegardé : {chemin_tests}")
    print()

    # 6. Revue
    print("👀 6. REVUE DE CODE (Reviewer)")
    print(f"   Approuvé : {'✅ OUI' if resultat.revue.approuve else '❌ NON'}")
    if not resultat.revue.approuve:
        print(f"   Commentaires : {resultat.revue.commentaires}")
    print()

    # 7. Débogage
    print("🐛 7. DÉBOGAGE (Debugger)")
    if resultat.code_corrige:
        print("   ✅ Code corrigé généré")
        chemin_code_corrige = projet_root / "solveur_multi_agents_corrige.py"
        with open(chemin_code_corrige, "w", encoding="utf-8") as f:
            f.write(resultat.code_corrige)
        print(f"   💾 Sauvegardé : {chemin_code_corrige}")
    else:
        print("   ⏭️  Pas de correction nécessaire (code déjà correct)")
    print()

    # 8. Code Final
    print("✅ 8. CODE FINAL")
    print(f"   {len(resultat.code_final)} caractères")
    chemin_code_final = projet_root / "solveur_multi_agents_final.py"
    with open(chemin_code_final, "w", encoding="utf-8") as f:
        f.write(resultat.code_final)
    print(f"   💾 Sauvegardé : {chemin_code_final}")

    # Extrait
    lignes_final = resultat.code_final.split("\n")
    print(f"\n   Extrait (15 premières lignes) :")
    print("   " + "-" * 66)
    for ligne in lignes_final[:15]:
        print(f"   {ligne}")
    print("   " + "-" * 66)
    if len(lignes_final) > 15:
        print(f"   ... et {len(lignes_final) - 15} lignes supplémentaires")
    print()

    # 9. Validation
    print("🔍 9. VALIDATION")
    print(f"   Validation statique : {resultat.validation_statique}")
    if resultat.erreur_execution:
        print(f"   ❌ Exécution : ÉCHEC")
        print(f"      Erreur : {resultat.erreur_execution}")
    else:
        print(f"   ✅ Exécution : SUCCÈS")

    if resultat.verdict_cascade:
        print(f"   📊 Verdict cascade : {resultat.verdict_cascade}")
    else:
        print(f"   ⚠️  Verdict cascade : Non disponible")
    print()

    # 10. Optimisation
    print("⚡ 10. OPTIMISATION")
    if resultat.optimisation:
        print(f"   ✅ Code optimisé généré")
        print(f"   Adopté : {'✅ OUI' if resultat.code_optimise_adopte else '❌ NON'}")
    else:
        print(f"   ⏭️  Pas d'optimisation (code déjà optimal ou cascade échouée)")
    print()

    # 11. Documentation
    print("📚 11. DOCUMENTATION")
    if resultat.documentation:
        print(f"   ✅ Documentation générée : {len(resultat.documentation)} caractères")
        chemin_doc = projet_root / "solveur_multi_agents_doc.md"
        with open(chemin_doc, "w", encoding="utf-8") as f:
            f.write(resultat.documentation)
        print(f"   💾 Sauvegardé : {chemin_doc}")
    else:
        print(f"   ⏭️  Pas de documentation (cascade échouée)")
    print()

    # Résumé final
    print("=" * 70)
    print("  RÉSUMÉ")
    print("=" * 70)
    if resultat.reussi:
        print("✅ PIPELINE RÉUSSI !")
        print(f"   - Code fonctionnel et validé")
        print(f"   - Tests générés")
        print(f"   - Documentation complète")
        print(f"   - Prêt pour enregistrement dans solver_store/")
    else:
        print("❌ PIPELINE ÉCHOUÉ")
        if not resultat.validation_statique.valide:
            print(f"   Raison : Validation statique échouée")
        elif resultat.erreur_execution:
            print(f"   Raison : Erreur d'exécution")
        else:
            print(f"   Raison : Cascade de validation échouée")

    print()


if __name__ == "__main__":
    main()
