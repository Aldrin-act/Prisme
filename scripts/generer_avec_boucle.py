"""Génération avec boucle de réparation (Étape 6, `generation/graph.py`).

Ce script utilise le pipeline `generation/graph.py` (StateGraph LangGraph)
qui permet au Debugger de faire jusqu'à `MAX_TENTATIVES_REPARATION`
tentatives de correction au lieu d'une seule.

Usage :
    python scripts/generer_avec_boucle.py

Output :
    - solveur_genere.py (code final)
    - test_solveur_genere.py (tests pytest)
    - solveur_genere_doc.md (documentation, si produite)
    - Affichage détaillé de chaque tentative de la boucle
"""

from __future__ import annotations

import os
import sys
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

from generation.graph import MAX_TENTATIVES_REPARATION, TentativeReparation, tenter_generation_avec_boucle


def _resumer_echecs_cascade(verdict) -> str:
    """`VerdictCascade` n'a pas de `.resumer()` — construit un résumé court
    à partir de `.echecs` (une entrée par instance/cas en échec)."""
    if verdict is None:
        return "cascade non atteinte"
    if verdict.reussi:
        return "cascade au vert"
    return "; ".join(f"[{d.brique_en_echec}] {d.nom}" for d in verdict.echecs)


def afficher_tentative(tentative: TentativeReparation, numero: int) -> None:
    """Affiche les détails d'une tentative de réparation."""
    print(f"\n   ┌─ Tentative #{numero}")
    print(f"   │  Reviewer : {'✅ APPROUVÉ' if tentative.revue.approuve else '❌ REJETÉ'}")

    if not tentative.revue.approuve:
        print(f"   │  Bugs détectés : {tentative.revue.commentaires[:100]}...")
    else:
        # Validation effectuée
        if tentative.validation_statique is None:
            print("   │  Validation : ⏭️  Non effectuée")
        elif not tentative.validation_statique.valide:
            print(f"   │  Validation statique : ❌ {'; '.join(tentative.validation_statique.violations)}")
        elif tentative.erreur_execution:
            print(f"   │  Exécution : ❌ {tentative.erreur_execution[:100]}...")
        elif tentative.verdict_cascade is None:
            print("   │  Cascade : ❌ Échec avant cascade")
        elif not tentative.verdict_cascade.reussi:
            print(f"   │  Cascade : ❌ {_resumer_echecs_cascade(tentative.verdict_cascade)[:100]}...")
        else:
            print("   │  Validation : ✅ SUCCÈS COMPLET")

    print(f"   │  Résultat : {'🎉 SUCCÈS' if tentative.reussi else '🔄 RETRY'}")
    print("   └─")


def main():
    print("\n" + "="*70)
    print(f"  GÉNÉRATION AVEC BOUCLE DE RÉPARATION (max {MAX_TENTATIVES_REPARATION} tentatives)")
    print("="*70 + "\n")

    provider = os.getenv('PRISME_LLM_PROVIDER', 'mistral')
    print(f"📡 Provider : {provider}")
    print(f"🔑 API Key : {os.getenv(f'{provider.upper()}_API_KEY', 'NON DÉFINIE')[:20]}...")

    # Génération avec boucle
    print("\n🚀 Démarrage pipeline multi-agents AVEC boucle...\n")

    try:
        resultat = tenter_generation_avec_boucle()
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
    print(f"\n📊 Nombre de tentatives : {boucle.nombre_tentatives} / {MAX_TENTATIVES_REPARATION}")
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
        print(f"  ❌ GÉNÉRATION ÉCHOUÉE (après {boucle.nombre_tentatives} tentatives)")
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
    print("\n📊 Statistiques :")
    print(f"   • Code généré : {len(resultat.code_genere)} caractères")
    print(f"   • Tests générés : {len(resultat.tests_generes)} caractères")
    print(f"   • Tentatives de réparation : {boucle.nombre_tentatives}")
    print(f"   • Algorithme recommandé : {resultat.algorithme_recommande} ({resultat.justification_algorithme})")

    # Diagnostic si échec
    if not resultat.reussi:
        print("\n❌ Raison de l'échec :")
        if resultat.validation_statique and not resultat.validation_statique.valide:
            print(f"   • Validation statique : {'; '.join(resultat.validation_statique.violations)}")
        elif resultat.erreur_execution:
            print(f"   • Exécution : {resultat.erreur_execution}")
        elif resultat.verdict_cascade:
            print(f"   • Cascade : {_resumer_echecs_cascade(resultat.verdict_cascade)}")
        else:
            print("   • Erreur inconnue")

        print("\n💡 Le code a été sauvegardé malgré l'échec pour inspection.")

    print()


if __name__ == "__main__":
    main()
