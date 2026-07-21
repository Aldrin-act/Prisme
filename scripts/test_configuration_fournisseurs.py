"""Test de la configuration optimale des fournisseurs LLM par agent.

Ce script vérifie que chaque agent utilise bien son fournisseur optimal et
lance un test complet du pipeline sur l'instance GreenSig.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger .env
try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass


def main():
    print("\n" + "=" * 80)
    print("  TEST DE LA CONFIGURATION OPTIMALE DES FOURNISSEURS LLM")
    print("=" * 80 + "\n")

    # Importer config
    try:
        from generation.agents.config_fournisseurs import FOURNISSEURS_PAR_AGENT, obtenir_fournisseur_pour_agent
        from generation.agents.client_llm import construire_appel_llm_pour_agent
        from generation.pipeline_multi_agents import tenter_generation_multi_agents
    except ImportError as e:
        print(f"ERREUR d'import : {e}")
        print("Installez : uv sync --extra llm")
        sys.exit(1)

    # Afficher configuration
    print("Configuration des fournisseurs par agent :\n")
    print(f"{'Agent':<20} {'Fournisseur':<15} {'Modèle'}")
    print("-" * 80)

    from generation.agents.client_llm import _MODELES_PAR_DEFAUT

    agents_par_fournisseur = {}
    for agent, fournisseur in sorted(FOURNISSEURS_PAR_AGENT.items()):
        modele = _MODELES_PAR_DEFAUT.get(fournisseur, "N/A")
        print(f"{agent:<20} {fournisseur:<15} {modele}")

        if fournisseur not in agents_par_fournisseur:
            agents_par_fournisseur[fournisseur] = []
        agents_par_fournisseur[fournisseur].append(agent)

    print("\n" + "=" * 80)
    print("  RÉPARTITION PAR FOURNISSEUR")
    print("=" * 80 + "\n")

    for fournisseur, agents in sorted(agents_par_fournisseur.items()):
        print(f"{fournisseur.upper()} ({len(agents)} agents) :")
        for agent in sorted(agents):
            print(f"  - {agent}")
        print()

    # Charger instance GreenSig
    print("=" * 80)
    print("  CHARGEMENT DE L'INSTANCE GREENSIG")
    print("=" * 80 + "\n")

    chemin_instance = projet_root / "greensig_instance_trco_simulee.json"

    if not chemin_instance.exists():
        print(f"ERREUR : Instance introuvable : {chemin_instance}")
        print("Exécutez d'abord : uv run python -m scripts.generer_instance_simulee_2165")
        sys.exit(1)

    with open(chemin_instance, encoding="utf-8") as f:
        instance_exemple = json.load(f)

    print(f"Instance chargée :")
    print(f"  - Tâches      : {len(instance_exemple['taches'])}")
    print(f"  - Ressources  : {len(instance_exemple['ressources'])}")
    print(f"  - Contraintes : {len(instance_exemple['contraintes'])}")
    print()

    # Confirmation
    print("=" * 80)
    print("  LANCEMENT DU TEST")
    print("=" * 80 + "\n")

    print("Ce test va lancer le pipeline multi-agents complet avec :")
    print("  - Chaque agent utilise son fournisseur optimal")
    print("  - Instance GreenSig (2165 tâches)")
    print("  - Durée estimée : 3-5 minutes")
    print()

    reponse = input("Continuer ? (o/N) : ")
    if reponse.lower() != 'o':
        print("Test annulé.")
        sys.exit(0)

    print()
    print("=" * 80)
    print("  PIPELINE EN COURS...")
    print("=" * 80 + "\n")

    timestamp_debut = datetime.now()

    try:
        # Lancer pipeline avec configuration optimale (ignore le paramètre appel_llm)
        print("Démarrage du pipeline (chaque agent utilise son fournisseur optimal)...\n")
        resultat = tenter_generation_multi_agents(instance_exemple=instance_exemple)

        timestamp_fin = datetime.now()
        duree = (timestamp_fin - timestamp_debut).total_seconds()

        print("\n" + "=" * 80)
        print("  PIPELINE TERMINÉ")
        print("=" * 80 + "\n")

        print(f"Durée totale : {duree:.1f} secondes ({duree/60:.1f} minutes)")
        print()

    except Exception as e:
        print(f"\nERREUR lors de la génération : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Afficher résultats
    print("=" * 80)
    print("  RÉSULTATS")
    print("=" * 80 + "\n")

    print("--- RECOMMANDATION BENCHMARKER ---\n")
    print(f"Algorithme recommandé : {resultat.algorithme_recommande.upper()}")
    print(f"Justification : {resultat.justification_algorithme[:200]}...")
    print()

    print("--- VALIDATION ---\n")
    print(f"Validation statique : {'✓ OK' if resultat.validation_statique.valide else '✗ ÉCHEC'}")
    print(f"Exécution           : {'✓ OK' if resultat.erreur_execution is None else '✗ ÉCHEC'}")

    if resultat.verdict_cascade:
        print(f"Cascade             : {'✓ RÉUSSI' if resultat.verdict_cascade.reussi else '✗ ÉCHEC'}")
    else:
        print("Cascade             : ✗ NON ÉVALUÉE")

    print()

    # Verdict final
    print("=" * 80)
    print("  VERDICT FINAL")
    print("=" * 80 + "\n")

    if resultat.reussi:
        print("✓ SUCCÈS : Le pipeline a généré un solveur valide et fonctionnel !")
        print()
        print(f"  Algorithme       : {resultat.algorithme_recommande.upper()}")
        print(f"  Validation       : Complète")
        print(f"  Cascade          : Réussie")
        print(f"  Code optimisé    : {'Oui' if resultat.code_optimise_adopte else 'Non'}")
        print(f"  Documentation    : {'Générée' if resultat.documentation else 'Non'}")
        print()
        print("✓ La configuration optimale des fournisseurs fonctionne correctement !")
    else:
        print("✗ ÉCHEC : Le pipeline n'a pas réussi à générer un solveur valide")
        print()
        if not resultat.validation_statique.valide:
            print("  Raison : Validation statique échouée")
            print(f"  Détails : {', '.join(resultat.validation_statique.violations)}")
        elif resultat.erreur_execution:
            print("  Raison : Erreur d'exécution")
            print(f"  Détails : {resultat.erreur_execution[:200]}...")
        elif not resultat.verdict_cascade or not resultat.verdict_cascade.reussi:
            print("  Raison : Cascade de validation échouée")

    print()

    # Sauvegarder résultat
    chemin_resultat = projet_root / f"test_fournisseurs_{timestamp_debut.strftime('%Y%m%d_%H%M%S')}.json"

    with open(chemin_resultat, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp_debut.isoformat(),
            "duree_secondes": duree,
            "configuration_fournisseurs": FOURNISSEURS_PAR_AGENT,
            "instance": {
                "source": "greensig_instance_trco_simulee.json",
                "nb_taches": len(instance_exemple["taches"]),
                "nb_ressources": len(instance_exemple["ressources"]),
                "nb_contraintes": len(instance_exemple["contraintes"]),
            },
            "succes": resultat.reussi,
            "algorithme_recommande": resultat.algorithme_recommande,
            "validation_statique_ok": resultat.validation_statique.valide,
            "execution_ok": resultat.erreur_execution is None,
            "cascade_ok": resultat.verdict_cascade.reussi if resultat.verdict_cascade else False,
        }, f, indent=2, ensure_ascii=False)

    print(f"Résultat sauvegardé : {chemin_resultat.name}")
    print()


if __name__ == "__main__":
    main()
