"""Test du pipeline avec affichage VERBEUX de la progression en temps réel."""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass


def print_etape(message: str):
    """Affiche un message avec timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def main():
    print("\n" + "=" * 70)
    print("  TEST PIPELINE VERBEUX - PROGRESSION EN TEMPS RÉEL")
    print("=" * 70 + "\n")

    try:
        from generation.agents.client_llm import construire_appel_llm_pour_agent
        from generation.agents import (
            orchestrateur, analyste, architecte, benchmarker,
            testeur, reviewer, debugger, optimiseur, documentation
        )
        from generation.agents.generateur import generer_code_depuis_plan
        from generation.pipeline_multi_agents import _valider_completement, _creer_instance_exemple_defaut
    except ImportError as e:
        print(f"ERREUR d'import : {e}")
        sys.exit(1)

    instance_exemple = _creer_instance_exemple_defaut()

    print_etape("OK - Instance exemple creee (10 taches)")
    print()

    # Agent 1 : Orchestrateur
    print_etape(">> Agent 1/10 : Orchestrateur (nvidia) demarre...")
    plan = orchestrateur.planifier(construire_appel_llm_pour_agent("orchestrateur"))
    print_etape("OK - Orchestrateur termine")
    print()

    # Agent 2 : Analyste
    print_etape(">> Agent 2/10 : Analyste (deepseek) démarré...")
    analyse = analyste.analyser_mission(construire_appel_llm_pour_agent("analyste"))
    print_etape("OK - Analyste terminé")
    print()

    # Agent 3 : Architecte
    print_etape(">> Agent 3/10 : Architecte (deepseek) démarré...")
    conception = architecte.concevoir_modele(construire_appel_llm_pour_agent("architecte"), analyse)
    print_etape("OK - Architecte terminé")
    print()

    # Agent 4 : Benchmarker
    print_etape(">> Agent 4/10 : Benchmarker (minimax) démarré...")
    resultat_benchmark = benchmarker.benchmarker_algorithmes(
        construire_appel_llm_pour_agent("benchmarker"), instance_exemple
    )
    algo = resultat_benchmark.recommandation.algorithme
    print_etape(f"OK - Benchmarker terminé >> Algorithme recommandé: {algo}")
    print()

    # Agent 5 : Générateur
    print_etape(">> Agent 5/10 : Générateur (deepseek) démarré...")
    brut = generer_code_depuis_plan(
        construire_appel_llm_pour_agent("generateur"),
        conception.en_texte(),
        algorithme=algo,
        parametres=resultat_benchmark.recommandation.parametres_suggeres,
    )
    print_etape("OK - Générateur terminé")
    print()

    # Agent 6 : Testeur
    print_etape(">> Agent 6/10 : Testeur (deepseek) démarré...")
    tests = testeur.generer_tests(construire_appel_llm_pour_agent("testeur"), brut.code_source)
    print_etape("OK - Testeur terminé")
    print()

    # Agent 7 : Reviewer
    print_etape(">> Agent 7/10 : Reviewer (deepseek) démarré...")
    revue = reviewer.relire_code(construire_appel_llm_pour_agent("reviewer"), brut.code_source)
    print_etape(f"OK - Reviewer terminé >> Approuvé: {revue.approuve}")
    print()

    # Agent 8 : Debugger (si nécessaire)
    code_candidat = brut.code_source
    if not revue.approuve:
        print_etape(">> Agent 8/10 : Debugger (deepseek) - correction suite revue...")
        correction = debugger.corriger_code(
            construire_appel_llm_pour_agent("debugger"), code_candidat, revue.commentaires
        )
        code_candidat = correction.code_source
        print_etape("OK - Debugger terminé (correction revue)")
        print()

    # BOUCLE DE RÉPARATION (Étape 6)
    print_etape(">> Validation et boucle de réparation...")
    MAX_TENTATIVES = 3
    tentative = 0

    while tentative < MAX_TENTATIVES:
        print_etape(f"  Tentative de validation {tentative + 1}/{MAX_TENTATIVES + 1}...")
        resultat = _valider_completement(code_candidat)

        if resultat.reussi:
            print_etape("  OK - Validation réussie !")
            break

        if not resultat.validation_statique.valide:
            print_etape(
                f"  ERREUR - Erreur validation statique: {', '.join(resultat.validation_statique.violations)[:100]}"
            )
            break

        if resultat.erreur_execution is not None:
            tentative += 1
            if tentative >= MAX_TENTATIVES:
                print_etape(f"  ERREUR - Limite de réparation atteinte ({MAX_TENTATIVES} tentatives)")
                print_etape(f"  Erreur finale: {resultat.erreur_execution[:150]}")
                break

            print_etape(f"  ERREUR - Erreur d'exécution détectée: {resultat.erreur_execution[:100]}")
            print_etape(f"  >> Debugger rappelé (tentative {tentative}/{MAX_TENTATIVES})...")

            probleme = f"Erreur d'exécution:\n{resultat.erreur_execution}"
            correction = debugger.corriger_code(
                construire_appel_llm_pour_agent("debugger"), code_candidat, probleme
            )
            code_candidat = correction.code_source
            print_etape(f"  OK - Code corrigé par Debugger")
        else:
            print_etape("  ERREUR - Échec cascade (faisabilité/optimalité)")
            break

    print()

    if not resultat.reussi:
        print_etape("ERREUR - ÉCHEC - Pipeline n'a pas réussi")
        print()
        print("=" * 70)
        print(f"  Algorithme: {algo}")
        print(f"  Validation statique: {'OK' if resultat.validation_statique.valide else 'ÉCHEC'}")
        print(f"  Exécution: {'OK' if resultat.erreur_execution is None else 'ÉCHEC'}")
        print("=" * 70)
        return

    # Agent 9 : Optimiseur
    print_etape(">> Agent 9/10 : Optimiseur (minimax) démarré...")
    optimisation = optimiseur.optimiser_code(construire_appel_llm_pour_agent("optimiseur"), code_candidat)
    print_etape(f"OK - Optimiseur terminé >> Optimisation proposée: {optimisation.proposee}")
    print()

    # Agent 10 : Documentation
    print_etape(">> Agent 10/10 : Documentation (nvidia) démarré...")
    doc = documentation.documenter_code(construire_appel_llm_pour_agent("documentation"), code_candidat)
    print_etape("OK - Documentation terminée")
    print()

    # Résultat final
    print("\n" + "=" * 70)
    print("  OK - SUCCÈS - PIPELINE TERMINÉ")
    print("=" * 70)
    print(f"  Algorithme: {algo}")
    print(f"  Validation: Complète")
    print(f"  Cascade: Réussie")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    debut = datetime.now()
    try:
        main()
    except Exception as e:
        print(f"\nERREUR - ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        duree = (datetime.now() - debut).total_seconds()
        print(f"\nDurée totale: {duree:.1f}s ({duree/60:.1f} min)\n")
