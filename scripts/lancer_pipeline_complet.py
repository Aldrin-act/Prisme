"""Lance le pipeline multi-agents complet avec l'instance GreenSig (2165 taches).

Ce script lance la generation complete d'un solveur adapte a l'instance GreenSig
en utilisant le Benchmarker pour choisir l'algorithme optimal.
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
    print("  PIPELINE MULTI-AGENTS COMPLET - GENERATION SOLVEUR GREENSIG")
    print("=" * 80 + "\n")

    # Verifier dependances
    try:
        from generation.agents.client_llm import construire_appel_llm
        from generation.pipeline_multi_agents import tenter_generation_multi_agents
    except ImportError as e:
        print(f"ERREUR d'import : {e}")
        print("Installez : uv sync --extra llm")
        sys.exit(1)

    # Charger instance GreenSig
    print("Chargement de l'instance GreenSig (2165 taches)...\n")
    chemin_instance = projet_root / "greensig_instance_trco_simulee.json"

    if not chemin_instance.exists():
        print(f"ERREUR: Instance introuvable : {chemin_instance}")
        print("Executez d'abord : uv run python -m scripts.generer_instance_simulee_2165")
        sys.exit(1)

    with open(chemin_instance, encoding="utf-8") as f:
        instance_exemple = json.load(f)

    print(f"Instance chargee :")
    print(f"  - Taches : {len(instance_exemple['taches'])}")
    print(f"  - Ressources : {len(instance_exemple['ressources'])}")
    print(f"  - Contraintes : {len(instance_exemple['contraintes'])}")
    print()

    # Lancer pipeline
    print("=" * 80)
    print("  LANCEMENT DU PIPELINE (10 AGENTS)")
    print("=" * 80 + "\n")

    print("Etapes du pipeline :")
    print("  1. Orchestrateur  - Planification generale")
    print("  2. Analyste       - Analyse de la mission")
    print("  3. Architecte     - Conception du modele")
    print("  4. Benchmarker    - Selection de l'algorithme optimal")
    print("  5. Developpeur    - Generation du code")
    print("  6. Testeur        - Generation des tests")
    print("  7. Reviewer       - Relecture du code")
    print("  8. Debugger       - Correction si necessaire")
    print("  9. Validation     - Cascade complete (faisabilite + optimalite + fidelite)")
    print(" 10. Optimiseur     - Proposition d'ameliorations")
    print(" 11. Documentation  - Generation de la documentation")
    print()

    print("ATTENTION : Ce processus peut prendre 3-5 minutes.")
    print("Le LLM sera appele plusieurs fois (un appel par agent).")
    print()
    print("Demarrage automatique dans 2 secondes...")
    print()

    timestamp_debut = datetime.now()

    try:
        appel_llm = construire_appel_llm()
        print(f"Provider LLM : {appel_llm.__class__.__name__}")
        print()

        print("Demarrage du pipeline...\n")
        resultat = tenter_generation_multi_agents(appel_llm, instance_exemple)

        timestamp_fin = datetime.now()
        duree = (timestamp_fin - timestamp_debut).total_seconds()

        print("\n" + "=" * 80)
        print("  PIPELINE TERMINE")
        print("=" * 80 + "\n")

        print(f"Duree totale : {duree:.1f} secondes ({duree/60:.1f} minutes)")
        print()

    except Exception as e:
        print(f"\nERREUR lors de la generation : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Afficher resultats
    print("=" * 80)
    print("  RESULTATS")
    print("=" * 80 + "\n")

    print("--- RECOMMANDATION BENCHMARKER ---\n")
    print(f"Algorithme recommande : {resultat.algorithme_recommande.upper()}")
    print()
    print("Justification :")
    import textwrap

    for ligne in textwrap.wrap(resultat.justification_algorithme, width=78):
        print(f"  {ligne}")
    print()

    if resultat.parametres_algorithme:
        print("Parametres suggeres :")
        for param, valeur in resultat.parametres_algorithme.items():
            print(f"  - {param}: {valeur}")
        print()

    print("\n--- GENERATION DU CODE ---\n")
    print(f"Code genere : {len(resultat.code_genere)} caracteres")
    print(f"Tests generes : {len(resultat.tests_generes)} caracteres")
    print(f"Revue approuvee : {'Oui' if resultat.revue.approuve else 'Non'}")

    if resultat.code_corrige:
        print("Code corrige par le Debugger : Oui")
    else:
        print("Code corrige par le Debugger : Non (pas necessaire)")
    print()

    print("\n--- VALIDATION ---\n")
    print(f"Validation statique : {'OK' if resultat.validation_statique.valide else 'ECHEC'}")

    if not resultat.validation_statique.valide:
        print(f"  Erreurs : {', '.join(resultat.validation_statique.violations)}")

    print(f"Execution : {'OK' if resultat.erreur_execution is None else 'ECHEC'}")

    if resultat.erreur_execution:
        print(f"  Erreur : {resultat.erreur_execution[:300]}...")

    if resultat.verdict_cascade:
        print(f"Cascade : {'REUSSI' if resultat.verdict_cascade.reussi else 'ECHEC'}")
        if resultat.verdict_cascade.reussi:
            instances_validees = len(
                [d for d in resultat.verdict_cascade.diagnostics if d.valide]
            )
            print(f"  Instances validees : {instances_validees}")
        else:
            print("  Certaines instances ont echoue")
    else:
        print("Cascade : NON EVALUEE (echec avant)")

    print()

    if resultat.optimisation and resultat.optimisation.proposee:
        print("\n--- OPTIMISATION ---\n")
        print(f"Code optimise propose : Oui")
        print(f"Code optimise adopte : {'Oui' if resultat.code_optimise_adopte else 'Non'}")
        print()

    print("\n--- DOCUMENTATION ---\n")
    if resultat.documentation:
        print(f"Documentation generee : {len(resultat.documentation)} caracteres")
    else:
        print("Documentation : Non generee")
    print()

    # Verdict final
    print("\n" + "=" * 80)
    print("  VERDICT FINAL")
    print("=" * 80 + "\n")

    if resultat.reussi:
        print("SUCCES : Le pipeline a genere un solveur valide et fonctionnel !")
        print()
        print(f"  Algorithme utilise : {resultat.algorithme_recommande.upper()}")
        print(f"  Validation complete : Oui")
        print(f"  Cascade reussie : Oui")
        print(f"  Documentation : Generee")
        print()
        print("Le solveur est pret a etre enregistre dans le solver_store.")
    else:
        print("ECHEC : Le pipeline n'a pas reussi a generer un solveur valide")
        print()
        if not resultat.validation_statique.valide:
            print("  Raison : Validation statique echouee")
            print("  Le code genere contient des erreurs de syntaxe ou utilise des imports interdits")
        elif resultat.erreur_execution:
            print("  Raison : Erreur d'execution")
            print("  Le code genere leve une exception a l'execution")
        elif not resultat.verdict_cascade or not resultat.verdict_cascade.reussi:
            print("  Raison : Cascade de validation echouee")
            print("  Le solveur ne repond pas aux criteres de qualite (faisabilite/optimalite/fidelite)")
        print()
        print("Analysez les erreurs ci-dessus pour diagnostiquer le probleme.")

    print()

    # Sauvegarder
    print("=" * 80)
    print("  SAUVEGARDE")
    print("=" * 80 + "\n")

    # Resultat JSON
    chemin_resultat = projet_root / f"resultat_pipeline_complet_{timestamp_debut.strftime('%Y%m%d_%H%M%S')}.json"

    with open(chemin_resultat, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": timestamp_debut.isoformat(),
                "duree_secondes": duree,
                "instance": {
                    "source": "greensig_instance_trco_simulee.json",
                    "nb_taches": len(instance_exemple["taches"]),
                    "nb_ressources": len(instance_exemple["ressources"]),
                    "nb_contraintes": len(instance_exemple["contraintes"]),
                },
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
                "code_optimise_adopte": resultat.code_optimise_adopte,
                "documentation_generee": resultat.documentation is not None,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Resultat JSON sauvegarde : {chemin_resultat.name}")

    # Code du solveur
    if resultat.reussi:
        chemin_code = (
            projet_root / f"solveur_genere_{timestamp_debut.strftime('%Y%m%d_%H%M%S')}.py"
        )
        with open(chemin_code, "w", encoding="utf-8") as f:
            f.write(resultat.code_final)
        print(f"Code du solveur sauvegarde : {chemin_code.name}")

        # Documentation
        if resultat.documentation:
            chemin_doc = (
                projet_root
                / f"documentation_solveur_{timestamp_debut.strftime('%Y%m%d_%H%M%S')}.md"
            )
            with open(chemin_doc, "w", encoding="utf-8") as f:
                f.write(resultat.documentation)
            print(f"Documentation sauvegardee : {chemin_doc.name}")

    print()

    # Prochaines etapes
    if resultat.reussi:
        print("=" * 80)
        print("  PROCHAINES ETAPES")
        print("=" * 80 + "\n")
        print("1. Enregistrer le solveur dans le solver_store :")
        print(f"   - Utilisez solver_store/registry.py")
        print()
        print("2. Tester le solveur sur une vraie instance GreenSig :")
        print(f"   - Chargez les donnees reelles depuis PostgreSQL")
        print(f"   - Executez le solveur genere")
        print()
        print("3. Mesurer les performances :")
        print(f"   - Temps d'execution")
        print(f"   - Qualite de la solution (makespan)")
        print()
    else:
        print("=" * 80)
        print("  DIAGNOSTIC")
        print("=" * 80 + "\n")
        print("Le pipeline a echoue. Analysez les erreurs ci-dessus.")
        print()
        print("Actions possibles :")
        print("1. Verifier que l'algorithme recommande est implemente")
        print(f"   - Algorithme recommande : {resultat.algorithme_recommande}")
        print(f"   - Fichier : generation/algorithms/{resultat.algorithme_recommande}.py")
        print()
        print("2. Verifier le prompt du Developpeur")
        print("   - generation/prompts/developpeur.md")
        print()
        print("3. Relancer le pipeline avec une instance plus petite")
        print("   - Tester avec 50 ou 100 taches d'abord")
        print()

    print()


if __name__ == "__main__":
    main()
