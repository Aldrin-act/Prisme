"""Version allegee du pipeline multi-agents pour diagnostiquer un echec de
cascade sans repayer les ~9-10 appels LLM du pipeline complet.

N'appelle que la chaine qui produit le code (Analyste -> Benchmarker ->
Architecte -> Developpeur), saute les agents de securite/qualite (Testeur,
Reviewer, Debugger, Optimiseur, Documentation), puis valide le code produit
(statique -> execution -> cascade) et affiche le detail complet du verdict :
quelle brique echoue, sur quelle instance, pourquoi. But : comprendre POURQUOI
la cascade echoue sur l'instance GreenSig 2165 taches, pas produire un
solveur pret a enregistrer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

try:
    from dotenv import load_dotenv

    load_dotenv(projet_root / ".env")
    print("Fichier .env charge")
except ImportError:
    print("Warning: python-dotenv non installe")


def main() -> None:
    print("\n" + "=" * 70)
    print("  DIAGNOSTIC ALLEGE - ALGORITHME + CASCADE (2165 TACHES)")
    print("=" * 70 + "\n")

    chemin_instance = projet_root / "greensig_instance_trco_simulee.json"
    if not chemin_instance.exists():
        print(f"ERREUR: Instance introuvable : {chemin_instance}")
        print("Executez d'abord : python -m scripts.generer_instance_simulee_2165")
        sys.exit(1)

    with open(chemin_instance, encoding="utf-8") as f:
        instance_exemple = json.load(f)

    print(f"Instance chargee : {len(instance_exemple['taches'])} taches\n")

    from generation.agents import analyste, architecte, benchmarker
    from generation.agents.client_llm import construire_appel_llm_pour_agent
    from generation.agents.generateur import generer_code_depuis_plan
    from generation.executer import ErreurExecutionGeneree, executer_code_genere
    from generation.pipeline_multi_agents import _parametres_cascade_pour_algorithme
    from generation.validation_statique import valider_code_genere
    from validation_engine.cascade import evaluer_cascade

    print("=" * 70)
    print("  1/4 - ANALYSTE")
    print("=" * 70 + "\n")
    analyse = analyste.analyser_mission(construire_appel_llm_pour_agent("analyste"))
    print("OK\n")

    print("=" * 70)
    print("  2/4 - BENCHMARKER")
    print("=" * 70 + "\n")
    resultat_benchmark = benchmarker.benchmarker_algorithmes(
        construire_appel_llm_pour_agent("benchmarker"), instance_exemple
    )
    algo = resultat_benchmark.recommandation.algorithme
    parametres = resultat_benchmark.recommandation.parametres_suggeres
    print(f"Algorithme recommande : {algo}")
    print(f"Parametres : {parametres}\n")

    print("=" * 70)
    print("  3/4 - ARCHITECTE")
    print("=" * 70 + "\n")
    conception = architecte.concevoir_modele(
        construire_appel_llm_pour_agent("architecte"), analyse, algorithme=algo, parametres=parametres
    )
    print(conception.en_texte())
    print()

    print("=" * 70)
    print("  4/4 - DEVELOPPEUR")
    print("=" * 70 + "\n")
    brut = generer_code_depuis_plan(
        construire_appel_llm_pour_agent("generateur"), conception.en_texte(), algorithme=algo, parametres=parametres
    )
    print(f"Code genere : {len(brut.code_source)} caracteres\n")

    chemin_code = projet_root / "solveur_diagnostic_2165.py"
    chemin_code.write_text(brut.code_source, encoding="utf-8")
    print(f"Code sauvegarde (avant validation) : {chemin_code}\n")

    print("=" * 70)
    print("  VALIDATION")
    print("=" * 70 + "\n")

    validation = valider_code_genere(brut.code_source)
    print(f"Validation statique : {'OK' if validation.valide else 'ECHEC'}")
    if not validation.valide:
        print(f"  Violations : {', '.join(validation.violations)}")
        print("\nArret : le code ne passe meme pas l'allowlist AST, inutile d'aller plus loin.")
        return

    try:
        solveur = executer_code_genere(brut.code_source)
    except ErreurExecutionGeneree as erreur:
        print(f"Execution : ECHEC\n  {erreur}")
        print("\nArret : le module ne se charge/execute pas, inutile d'evaluer la cascade.")
        return
    print("Execution : OK")

    tolerance_relative, comparer_affectation = _parametres_cascade_pour_algorithme(algo)
    print(f"\nParametres cascade pour '{algo}' : tolerance={tolerance_relative:.0%}, "
          f"comparer_affectation={comparer_affectation}\n")

    try:
        verdict = evaluer_cascade(solveur, tolerance_relative, comparer_affectation)
    except Exception as erreur:  # le code genere peut lever n'importe quoi a l'execution
        print(f"Cascade : ECHEC (exception levee par resoudre() sur une instance du banc)")
        print(f"  {type(erreur).__name__}: {erreur}")
        import traceback

        traceback.print_exc()
        return

    print(f"Cascade : {'REUSSI' if verdict.reussi else 'ECHEC'}")
    print(f"Instances : {len(verdict.diagnostics) - len(verdict.echecs)}/{len(verdict.diagnostics)} reussies\n")

    if verdict.echecs:
        print("Echecs, par brique :")
        par_brique: dict[str, list] = {}
        for diagnostic in verdict.echecs:
            par_brique.setdefault(diagnostic.brique_en_echec or "?", []).append(diagnostic)

        for brique, diagnostics in par_brique.items():
            print(f"\n  [{brique}] {len(diagnostics)} instance(s) en echec :")
            for diagnostic in diagnostics[:5]:
                print(f"    - {diagnostic.nom} : {'; '.join(diagnostic.details)}")
            if len(diagnostics) > 5:
                print(f"    ... et {len(diagnostics) - 5} autres")

    chemin_resultat = projet_root / "diagnostic_cascade_2165.json"
    with open(chemin_resultat, "w", encoding="utf-8") as f:
        json.dump(
            {
                "algorithme": algo,
                "parametres": parametres,
                "tolerance_relative": tolerance_relative,
                "comparer_affectation": comparer_affectation,
                "validation_statique": validation.valide,
                "cascade_reussie": verdict.reussi,
                "nb_instances": len(verdict.diagnostics),
                "nb_echecs": len(verdict.echecs),
                "echecs": [
                    {"nom": d.nom, "brique": d.brique_en_echec, "details": list(d.details)}
                    for d in verdict.echecs
                ],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nDiagnostic complet sauvegarde : {chemin_resultat}")
    print(f"Code genere sauvegarde : {chemin_code}")
    print()


if __name__ == "__main__":
    main()
