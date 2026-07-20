"""Génération avec boucle de réparation (Étape 6 implémentée).

Ce script utilise le nouveau pipeline `pipeline_avec_boucle.py` qui permet
au Debugger de faire jusqu'à 3 tentatives de correction au lieu d'une seule.

Différence avec `generer_solveur.py` (sans boucle) :
- SANS boucle : 1 tentative Debugger → échec si validation échoue
- AVEC boucle : 3 tentatives max → feedback précis à chaque itération

Usage :
    python scripts/generer_avec_boucle.py

Output :
    - solveur_genere.py (code final)
    - test_solveur_genere.py (tests pytest)
    - solveur_genere_doc.md (documentation)
    - Affichage détaillé de chaque tentative de la boucle
"""

from __future__ import annotations

import sys
import os
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

from generation.agents.client_llm import construire_appel_llm
from generation.pipeline_avec_boucle import tenter_generation_avec_boucle


def afficher_tentative(tentative, numero: int):
    """Affiche les détails d'une tentative de réparation."""
    print(f"\n   ┌─ Tentative #{numero}")
    print(f"   │  Reviewer : {'✅ APPROUVÉ' if tentative.revue.approuve else '❌ REJETÉ'}")

    if not tentative.revue.approuve:
        print(f"   │  Bugs détectés : {tentative.revue.commentaires[:100]}...")
    else:
        # Validation effectuée
        if tentative.validation_statique is None:
            print(f"   │  Validation : ⏭️  Non effectuée")
        elif not tentative.validation_statique.valide:
            print(f"   │  Validation statique : ❌ {tentative.validation_statique.raison}")
        elif tentative.erreur_execution:
            print(f"   │  Exécution : ❌ {tentative.erreur_execution[:100]}...")
        elif tentative.verdict_cascade is None:
            print(f"   │  Cascade : ❌ Échec avant cascade")
        elif not tentative.verdict_cascade.reussi:
            print(f"   │  Cascade : ❌ {tentative.verdict_cascade.resumer()[:100]}...")
        else:
            print(f"   │  Validation : ✅ SUCCÈS COMPLET")

    print(f"   │  Résultat : {'🎉 SUCCÈS' if tentative.reussi else '🔄 RETRY'}")
    print(f"   └─")


def main():
    print("\n" + "="*70)
    print("  GÉNÉRATION AVEC BOUCLE DE RÉPARATION (max 3 tentatives)")
    print("="*70 + "\n")

    provider = os.getenv('PRISME_LLM_PROVIDER', 'mistral')
    print(f"📡 Provider : {provider}")
    print(f"🔑 API Key : {os.getenv(f'{provider.upper()}_API_KEY', 'NON DÉFINIE')[:20]}...")

    # Construction client LLM
    try:
        appel_llm = construire_appel_llm()
    except Exception as e:
        print(f"\n❌ Erreur construction client LLM : {e}")
        sys.exit(1)

    # Génération avec boucle
    print("\n🚀 Démarrage pipeline multi-agents AVEC boucle...\n")

    try:
        resultat = tenter_generation_avec_boucle(appel_llm)
    except Exception as e:
        print(f"\n❌ Erreur durant génération : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Affichage des résultats
    print("\n" + "─"*70)
    print("  RÉSULTATS BOUCLE DE RÉPARATION")
    print("─"*70)

    boucle = resultat.boucle_reparation
    print(f"\n📊 Nombre de tentatives : {boucle.nombre_tentatives} / 3")
    print(f"📋 Code initial : {len(boucle.code_initial)} caractères")
    print(f"📋 Code final : {len(boucle.code_final)} caractères")

    # Détails de chaque tentative
    for i, tentative in enumerate(boucle.tentatives, 1):
        afficher_tentative(tentative, i)

    # Résultat global
    print("\n" + "="*70)
    if resultat.reussi:
        print("  ✅ GÉNÉRATION RÉUSSIE")
    else:
        print("  ❌ GÉNÉRATION ÉCHOUÉE (après 3 tentatives)")
    print("="*70 + "\n")

    # Sauvegarde
    if resultat.reussi or boucle.nombre_tentatives > 0:
        chemin_code = projet_root / "solveur_genere.py"
        chemin_tests = projet_root / "test_solveur_genere.py"
        chemin_doc = projet_root / "solveur_genere_doc.md"

        with open(chemin_code, "w", encoding="utf-8") as f:
            f.write(resultat.code_final)

        with open(chemin_tests, "w", encoding="utf-8") as f:
            f.write(resultat.tests_generes)

        if resultat.documentation:
            with open(chemin_doc, "w", encoding="utf-8") as f:
                f.write(resultat.documentation)

        print("📁 Fichiers générés :")
        print(f"   • {chemin_code}")
        print(f"   • {chemin_tests}")
        if resultat.documentation:
            print(f"   • {chemin_doc}")

    # Statistiques finales
    print(f"\n📊 Statistiques :")
    print(f"   • Code généré : {len(resultat.code_genere)} caractères")
    print(f"   • Tests générés : {len(resultat.tests_generes)} caractères")
    print(f"   • Tentatives de réparation : {boucle.nombre_tentatives}")

    if resultat.optimisation and resultat.optimisation.proposee:
        print(f"   • Optimisation : {'✅ Adoptée' if resultat.code_optimise_adopte else '❌ Rejetée'}")

    # Diagnostic si échec
    if not resultat.reussi:
        print(f"\n❌ Raison de l'échec :")
        if resultat.validation_statique and not resultat.validation_statique.valide:
            print(f"   • Validation statique : {resultat.validation_statique.raison}")
        elif resultat.erreur_execution:
            print(f"   • Exécution : {resultat.erreur_execution}")
        elif resultat.verdict_cascade:
            print(f"   • Cascade : {resultat.verdict_cascade.resumer()}")
        else:
            print(f"   • Erreur inconnue")

        print(f"\n💡 Le code a été sauvegardé malgré l'échec pour inspection.")

    print()


if __name__ == "__main__":
    main()
