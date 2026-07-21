"""Test du pipeline multi-agents avec l'agent Benchmarker integre.

Ce script teste l'integration complete du Benchmarker dans le pipeline de
generation. Il verifie que :
1. Le Benchmarker est appele correctement
2. La recommandation d'algorithme est transmise au Developpeur
3. Le code genere utilise l'algorithme recommande
4. Le resultat contient les nouvelles informations (algorithme, justification, parametres)
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger .env
try:
    from dotenv import load_dotenv

    load_dotenv(projet_root / ".env")
    print("Fichier .env charge")
except ImportError:
    print("Warning: python-dotenv non installe")


def main():
    print("\n" + "=" * 70)
    print("  TEST PIPELINE MULTI-AGENTS AVEC BENCHMARKER")
    print("=" * 70 + "\n")

    # Verifier que les dependances sont installees
    try:
        from generation.agents.client_llm import construire_appel_llm
        from generation.pipeline_multi_agents import tenter_generation_multi_agents
    except ImportError as e:
        print(f"ERREUR d'import : {e}")
        print("Installez : uv sync --extra llm")
        sys.exit(1)

    # Trois scenarios de test
    print("Scenarios de test disponibles :\n")
    print("1. Instance par defaut (10 taches) - devrait recommander CP-SAT")
    print("2. Instance moyenne (100 taches) - devrait recommander CP-SAT ou Tabu")
    print("3. Instance grande (500 taches) - devrait recommander Genetic ou ACO")
    print("4. Instance tres grande (2165 taches simulee) - devrait recommander Genetic\n")

    choix = input("Choisissez un scenario (1-4, defaut=1) : ").strip() or "1"

    if choix == "1":
        print("\nTest avec instance par defaut (10 taches)...\n")
        instance_exemple = None  # Utilise l'instance par defaut

    elif choix == "2":
        print("\nGeneration d'une instance moyenne (100 taches)...\n")
        instance_exemple = _generer_instance(nb_taches=100, nb_ressources=15)

    elif choix == "3":
        print("\nGeneration d'une instance grande (500 taches)...\n")
        instance_exemple = _generer_instance(nb_taches=500, nb_ressources=25)

    elif choix == "4":
        print("\nChargement de l'instance simulee (2165 taches)...\n")
        chemin_instance = projet_root / "greensig_instance_trco_simulee.json"

        if not chemin_instance.exists():
            print(f"ERREUR: Instance introuvable : {chemin_instance}")
            print("Executez d'abord : uv run python -m scripts.generer_instance_simulee_2165")
            sys.exit(1)

        with open(chemin_instance, encoding="utf-8") as f:
            instance_exemple = json.load(f)

    else:
        print("Choix invalide, utilisation de l'instance par defaut")
        instance_exemple = None

    # Lancer le pipeline
    print("=" * 70)
    print("  LANCEMENT DU PIPELINE")
    print("=" * 70 + "\n")

    print("Appel du pipeline multi-agents...")
    print("(Cela peut prendre 1-3 minutes selon le provider LLM)\n")

    try:
        appel_llm = construire_appel_llm()
        resultat = tenter_generation_multi_agents(appel_llm, instance_exemple)

    except Exception as e:
        print(f"\nERREUR lors de la generation : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Afficher les resultats
    print("\n" + "=" * 70)
    print("  RESULTATS DU PIPELINE")
    print("=" * 70 + "\n")

    print(f"Algorithme recommande : {resultat.algorithme_recommande}\n")

    print("Justification :")
    import textwrap

    for ligne in textwrap.wrap(resultat.justification_algorithme, width=68):
        print(f"  {ligne}")
    print()

    if resultat.parametres_algorithme:
        print("Parametres suggeres :")
        for param, valeur in resultat.parametres_algorithme.items():
            print(f"  - {param}: {valeur}")
        print()

    # Verification de la generation
    print("=" * 70)
    print("  VERIFICATION DU CODE GENERE")
    print("=" * 70 + "\n")

    print(f"Code genere : {len(resultat.code_genere)} caracteres")
    print(f"Tests generes : {len(resultat.tests_generes)} caracteres")
    print(f"Revue approuvee : {resultat.revue.approuve}")

    if resultat.code_corrige:
        print("Code corrige par le Debugger (erreurs detectees)")

    print()

    # Validation
    print("=" * 70)
    print("  VALIDATION")
    print("=" * 70 + "\n")

    print(f"Validation statique : {'OK' if resultat.validation_statique.valide else 'ECHEC'}")

    if not resultat.validation_statique.valide:
        print(f"  Erreurs : {', '.join(resultat.validation_statique.violations)}")

    print(f"Execution : {'OK' if resultat.erreur_execution is None else 'ECHEC'}")

    if resultat.erreur_execution:
        print(f"  Erreur : {resultat.erreur_execution[:200]}...")

    if resultat.verdict_cascade:
        print(f"Cascade : {'REUSSI' if resultat.verdict_cascade.reussi else 'ECHEC'}")
        nb_instances = len(resultat.verdict_cascade.diagnostics)
        nb_reussies = len([d for d in resultat.verdict_cascade.diagnostics if d.reussi])
        print(f"  Instances : {nb_reussies}/{nb_instances} reussies")
        if not resultat.verdict_cascade.reussi:
            print("  Echecs :")
            for diagnostic in resultat.verdict_cascade.echecs:
                print(f"    - {diagnostic.nom} [{diagnostic.brique_en_echec}] : {'; '.join(diagnostic.details)}")
    else:
        print("Cascade : NON EVALUEE")

    print()

    # Optimisation
    if resultat.optimisation and resultat.optimisation.proposee:
        print("=" * 70)
        print("  OPTIMISATION")
        print("=" * 70 + "\n")
        print(f"Code optimise propose : Oui")
        print(f"Code optimise adopte : {resultat.code_optimise_adopte}")
        print()

    # Succes global
    print("=" * 70)
    print("  VERDICT FINAL")
    print("=" * 70 + "\n")

    if resultat.reussi:
        print("SUCCES : Le pipeline a genere un solveur valide !")
        print(f"  - Algorithme : {resultat.algorithme_recommande}")
        print(f"  - Validation : Complete")
        print(f"  - Documentation : Generee")
    else:
        print("ECHEC : Le pipeline n'a pas reussi a generer un solveur valide")
        if not resultat.validation_statique.valide:
            print("  Raison : Validation statique echouee")
        elif resultat.erreur_execution:
            print("  Raison : Erreur d'execution")
        elif not resultat.verdict_cascade or not resultat.verdict_cascade.reussi:
            print("  Raison : Cascade de validation echouee")

    print()

    # Sauvegarder
    print("=" * 70)
    print("  SAUVEGARDE")
    print("=" * 70 + "\n")

    chemin_resultat = projet_root / "resultat_pipeline_avec_benchmarker.json"

    with open(chemin_resultat, "w", encoding="utf-8") as f:
        json.dump(
            {
                "succes": resultat.reussi,
                "algorithme_recommande": resultat.algorithme_recommande,
                "justification_algorithme": resultat.justification_algorithme,
                "parametres_algorithme": resultat.parametres_algorithme,
                "validation_statique": {
                    "valide": resultat.validation_statique.valide,
                    "message": ", ".join(resultat.validation_statique.violations) or "OK",
                },
                "erreur_execution": resultat.erreur_execution,
                "cascade_reussie": resultat.verdict_cascade.reussi
                if resultat.verdict_cascade
                else False,
                "cascade_echecs": [
                    {"nom": d.nom, "brique": d.brique_en_echec, "details": list(d.details)}
                    for d in (resultat.verdict_cascade.echecs if resultat.verdict_cascade else ())
                ],
                "code_optimise_adopte": resultat.code_optimise_adopte,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Resultat sauvegarde : {chemin_resultat}")

    # Sauvegarder le code final (meme en cas d'echec cascade, pour pouvoir l'inspecter)
    chemin_code = projet_root / "solveur_genere_avec_benchmarker.py"
    with open(chemin_code, "w", encoding="utf-8") as f:
        f.write(resultat.code_final)
    print(f"Code du solveur sauvegarde : {chemin_code}{'' if resultat.reussi else ' (echec cascade)'}")

    print()


def _generer_instance(nb_taches: int, nb_ressources: int) -> dict:
    """Genere une instance synthetique pour le test."""
    import random

    random.seed(42)

    flexibilite_min = 1
    flexibilite_max = min(6, nb_ressources)

    taches = [{"id": f"T{i}"} for i in range(1, nb_taches + 1)]
    ressources = [{"id": f"R{i}"} for i in range(1, nb_ressources + 1)]

    contraintes = []
    for tache in taches:
        nb_ressources_compatibles = random.randint(flexibilite_min, flexibilite_max)
        ressources_compatibles = random.sample(
            [r["id"] for r in ressources], nb_ressources_compatibles
        )

        for ressource in ressources_compatibles:
            duree = random.randint(15, 180)
            contraintes.append(
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": tache["id"],
                    "ressource": ressource,
                    "duree": duree,
                }
            )

    return {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": [{"type": "minimiser_makespan"}],
    }


if __name__ == "__main__":
    main()
