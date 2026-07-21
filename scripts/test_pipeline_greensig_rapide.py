"""Test rapide du pipeline sur une petite instance (pas GreenSig complet)."""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass


def main():
    print("\n" + "=" * 70)
    print("  TEST PIPELINE MULTI-AGENTS - CONFIGURATION OPTIMALE")
    print("=" * 70 + "\n")

    try:
        from generation.agents.config_fournisseurs import obtenir_fournisseur_pour_agent
        from generation.pipeline_multi_agents import tenter_generation_multi_agents
    except ImportError as e:
        print(f"ERREUR d'import : {e}")
        sys.exit(1)

    # Afficher configuration
    print("Configuration des fournisseurs:\n")
    agents = ['orchestrateur', 'analyste', 'architecte', 'benchmarker',
              'generateur', 'testeur', 'reviewer', 'debugger',
              'optimiseur', 'documentation']

    for agent in agents:
        fournisseur = obtenir_fournisseur_pour_agent(agent)
        print(f"  {agent:<16} -> {fournisseur}")

    print("\n" + "-" * 70)
    print("Test avec une petite instance (10 taches par defaut)")
    print("Duree estimee : 2-3 minutes")
    print("-" * 70 + "\n")

    timestamp_debut = datetime.now()

    try:
        print("Lancement du pipeline...\n")
        # Utilise l'instance par défaut (10 tâches)
        resultat = tenter_generation_multi_agents()

        timestamp_fin = datetime.now()
        duree = (timestamp_fin - timestamp_debut).total_seconds()

        print("\n" + "=" * 70)
        print("  RESULTATS")
        print("=" * 70 + "\n")

        print(f"Duree            : {duree:.1f}s ({duree/60:.1f} min)")
        print(f"Algorithme       : {resultat.algorithme_recommande.upper()}")
        print(f"Validation stat. : {'OK' if resultat.validation_statique.valide else 'ECHEC'}")
        print(f"Execution        : {'OK' if resultat.erreur_execution is None else 'ECHEC'}")

        if resultat.verdict_cascade:
            print(f"Cascade          : {'OK' if resultat.verdict_cascade.reussi else 'ECHEC'}")
        else:
            print("Cascade          : NON EVALUEE")

        print()
        print("=" * 70)

        if resultat.reussi:
            print("  SUCCES - Pipeline fonctionnel avec config optimale !")
        else:
            print("  ECHEC - Verifier erreurs ci-dessus")
            if not resultat.validation_statique.valide:
                print(f"\n  Erreur validation: {', '.join(resultat.validation_statique.violations)}")
            if resultat.erreur_execution:
                print(f"\n  Erreur execution: {resultat.erreur_execution[:200]}")

        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\nERREUR : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
