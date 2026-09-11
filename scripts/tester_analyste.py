"""Test de l'agent Analyste seul.

Lance uniquement l'Analyste pour voir la spécification qu'il génère.
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

from generation.agents import analyste
from generation.agents.client_llm import construire_modele_pour_agent


def main():
    print("\n" + "="*70)
    print("  TEST AGENT ANALYSTE")
    print("="*70 + "\n")

    api_key = os.getenv("KIMI_API_KEY")
    if not api_key:
        print("❌ KIMI_API_KEY non définie dans .env")
        sys.exit(1)

    print(f"🔑 API Key : {api_key[:20]}...\n")

    # Construction client LLM
    try:
        modele = construire_modele_pour_agent("analyste")
    except Exception as e:
        print(f"❌ Erreur construction client LLM : {e}")
        sys.exit(1)

    # Appel Analyste
    print("🤖 Appel de l'Analyste...\n")

    import time
    debut = time.time()

    try:
        resultat = analyste.analyser_mission(modele)
    except Exception as e:
        print(f"❌ Erreur durant l'appel : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    duree = time.time() - debut

    print(f"✅ Analyste terminé en {duree:.1f}s\n")

    # Affichage de la spécification
    print("="*70)
    print("  SPÉCIFICATION GÉNÉRÉE PAR L'ANALYSTE")
    print("="*70 + "\n")

    print("📥 ENTRÉES")
    print("─"*70)
    print(resultat.entrees)
    print()

    print("📤 SORTIES")
    print("─"*70)
    print(resultat.sorties)
    print()

    print("🔒 CONTRAINTES À COUVRIR")
    print("─"*70)
    for i, contrainte in enumerate(resultat.contraintes_a_couvrir, 1):
        print(f"{i}. {contrainte}")
    print()

    # Rendu en texte (pour l'Architecte)
    print("="*70)
    print("  RENDU EN TEXTE (pour l'agent suivant)")
    print("="*70 + "\n")
    print(resultat.en_texte())
    print()

    # Statistiques
    print("="*70)
    print("  STATISTIQUES")
    print("="*70 + "\n")

    print(f"⏱️  Durée : {duree:.1f}s")
    print(f"📊 Nombre de contraintes : {len(resultat.contraintes_a_couvrir)}")
    print(f"📝 Réponse brute : {len(resultat.reponse_brute)} caractères")
    print(f"📏 Entrées : {len(resultat.entrees)} caractères")
    print(f"📏 Sorties : {len(resultat.sorties)} caractères")

    # Tokens estimés
    tokens_output = len(resultat.reponse_brute) // 4
    print(f"🔢 Tokens output (estimé) : ~{tokens_output}")

    # Sauvegarder
    chemin_sortie = projet_root / "analyste_resultat.txt"
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write("SPÉCIFICATION GÉNÉRÉE PAR L'ANALYSTE\n")
        f.write("="*70 + "\n\n")
        f.write("📥 ENTRÉES\n")
        f.write("─"*70 + "\n")
        f.write(resultat.entrees + "\n\n")
        f.write("📤 SORTIES\n")
        f.write("─"*70 + "\n")
        f.write(resultat.sorties + "\n\n")
        f.write("🔒 CONTRAINTES À COUVRIR\n")
        f.write("─"*70 + "\n")
        for i, contrainte in enumerate(resultat.contraintes_a_couvrir, 1):
            f.write(f"{i}. {contrainte}\n")
        f.write("\n")
        f.write("="*70 + "\n")
        f.write("RENDU EN TEXTE\n")
        f.write("="*70 + "\n\n")
        f.write(resultat.en_texte())
        f.write("\n\n")
        f.write("="*70 + "\n")
        f.write("RÉPONSE BRUTE (JSON)\n")
        f.write("="*70 + "\n\n")
        f.write(resultat.reponse_brute)

    print(f"\n📁 Résultat sauvegardé : {chemin_sortie}")
    print()


if __name__ == "__main__":
    main()
