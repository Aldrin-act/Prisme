"""Test de l'agent Orchestrateur seul.

Lance uniquement l'Orchestrateur pour voir le plan qu'il génère.
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

from generation.agents import orchestrateur
from generation.agents.client_llm import construire_appel_llm


def main():
    print("\n" + "="*70)
    print("  TEST AGENT ORCHESTRATEUR")
    print("="*70 + "\n")

    provider = os.getenv('PRISME_LLM_PROVIDER', 'mistral')
    print(f"📡 Provider : {provider}")

    api_key_var = f'{provider.upper()}_API_KEY'
    api_key = os.getenv(api_key_var)
    if not api_key:
        print(f"❌ {api_key_var} non définie dans .env")
        sys.exit(1)

    print(f"🔑 API Key : {api_key[:20]}...\n")

    # Construction client LLM
    try:
        appel_llm = construire_appel_llm()
    except Exception as e:
        print(f"❌ Erreur construction client LLM : {e}")
        sys.exit(1)

    # Appel Orchestrateur
    print("🤖 Appel de l'Orchestrateur...\n")

    import time
    debut = time.time()

    try:
        resultat = orchestrateur.planifier(appel_llm)
    except Exception as e:
        print(f"❌ Erreur durant l'appel : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    duree = time.time() - debut

    print(f"✅ Orchestrateur terminé en {duree:.1f}s\n")

    # Affichage du plan
    print("="*70)
    print("  PLAN GÉNÉRÉ PAR L'ORCHESTRATEUR")
    print("="*70 + "\n")

    for i, etape in enumerate(resultat.plan, 1):
        print(f"{i}️⃣  Agent : {etape.agent}")
        print(f"   Instruction :")

        # Afficher l'instruction avec indentation
        lignes = etape.instruction.split('. ')
        for ligne in lignes:
            if ligne.strip():
                print(f"   • {ligne.strip()}.")

        print()

    # Statistiques
    print("="*70)
    print("  STATISTIQUES")
    print("="*70 + "\n")

    print(f"⏱️  Durée : {duree:.1f}s")
    print(f"📊 Nombre d'étapes : {len(resultat.plan)}")
    print(f"📝 Réponse brute : {len(resultat.reponse_brute)} caractères")

    # Tokens estimés
    tokens_input = len(resultat.reponse_brute) // 4  # Estimation grossière
    print(f"🔢 Tokens output (estimé) : ~{tokens_input}")

    # Agents listés
    agents_mentionnes = [etape.agent for etape in resultat.plan]
    print(f"\n🤖 Agents dans le plan : {', '.join(agents_mentionnes)}")

    # Vérifier si les 8 agents sont là
    agents_attendus = {
        "Analyste", "Architecte", "Développeur", "Testeur",
        "Reviewer", "Debugger", "Optimiseur", "Documentation"
    }
    agents_manquants = agents_attendus - set(agents_mentionnes)

    if agents_manquants:
        print(f"\n⚠️  Agents manquants : {', '.join(agents_manquants)}")
    else:
        print(f"\n✅ Tous les 8 agents sont présents dans le plan")

    # Sauvegarder la réponse brute
    chemin_sortie = projet_root / "orchestrateur_resultat.txt"
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        f.write("RÉPONSE BRUTE DE L'ORCHESTRATEUR\n")
        f.write("="*70 + "\n\n")
        f.write(resultat.reponse_brute)
        f.write("\n\n")
        f.write("PLAN STRUCTURÉ\n")
        f.write("="*70 + "\n\n")
        for i, etape in enumerate(resultat.plan, 1):
            f.write(f"{i}. {etape.agent}\n")
            f.write(f"   {etape.instruction}\n\n")

    print(f"\n📁 Résultat sauvegardé : {chemin_sortie}")
    print()


if __name__ == "__main__":
    main()
