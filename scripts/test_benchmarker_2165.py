"""Test du benchmarker sur l'instance simulee de 2165 taches."""

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
    print("\n" + "="*70)
    print("  TEST BENCHMARKER - 2165 TACHES")
    print("="*70 + "\n")

    # Charger instance simulee
    chemin_instance = projet_root / "greensig_instance_trco_simulee.json"

    if not chemin_instance.exists():
        print(f"ERREUR: Instance introuvable : {chemin_instance}")
        print("Executez d'abord : python scripts/generer_instance_simulee_2165.py")
        sys.exit(1)

    print(f"Chargement de l'instance : {chemin_instance.name}")

    with open(chemin_instance, encoding="utf-8") as f:
        instance_json = json.load(f)

    print(f"Instance chargee : {len(instance_json['taches'])} taches")
    print()

    # Analyser caracteristiques
    print("="*70)
    print("  ANALYSE DES CARACTERISTIQUES")
    print("="*70 + "\n")

    from generation.agents.benchmarker import analyser_caracteristiques_instance

    carac = analyser_caracteristiques_instance(instance_json)

    print(f"Caracteristiques :")
    print(f"  - Taches : {carac.nb_taches}")
    print(f"  - Ressources : {carac.nb_ressources}")
    print(f"  - Contraintes : {carac.nb_contraintes}")
    print(f"  - Flexibilite moyenne : {carac.flexibilite_moyenne:.2f} equipes/tache")
    print(f"  - Precedences : {'Oui' if carac.a_precedences else 'Non'}")
    print(f"  - Taille : {carac.taille_categorie}")
    print(f"  - Densite contraintes : {carac.densite_contraintes:.3f}")
    print()

    # Appel benchmarker
    print("="*70)
    print("  BENCHMARKING (APPEL LLM)")
    print("="*70 + "\n")

    print("Appel de l'agent Benchmarker...")
    print("(Cela peut prendre 10-30 secondes selon le provider)\n")

    try:
        from generation.agents.client_llm import construire_appel_llm
        from generation.agents.benchmarker import benchmarker_algorithmes

        appel_llm = construire_appel_llm()
        resultat = benchmarker_algorithmes(appel_llm, instance_json)

    except ImportError as e:
        print(f"ERREUR d'import : {e}")
        print("Installez : uv sync --extra llm")
        sys.exit(1)
    except Exception as e:
        print(f"ERREUR lors du benchmark : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Afficher recommandation
    print("="*70)
    print("  RECOMMANDATION")
    print("="*70 + "\n")

    reco = resultat.recommandation

    print(f"Algorithme recommande : **{reco.algorithme.upper()}**\n")

    print(f"Raison :")
    # Couper la raison en lignes de max 70 caracteres
    raison = reco.raison
    import textwrap
    for ligne in textwrap.wrap(raison, width=68):
        print(f"  {ligne}")
    print()

    print(f"Temps d'execution estime : {reco.temps_execution_estime}")
    print(f"Qualite attendue : {reco.qualite_attendue}\n")

    if reco.parametres_suggeres:
        print(f"Parametres suggeres :")
        for param, valeur in reco.parametres_suggeres.items():
            print(f"  - {param}: {valeur}")
        print()

    if reco.alternatives:
        print(f"Alternatives :")
        for alt in reco.alternatives:
            print(f"  - {alt}")
        print()

    # Tableau comparatif
    print("="*70)
    print("  COMPARAISON")
    print("="*70 + "\n")

    print(resultat.comparaison)
    print()

    # Sauvegarder
    print("="*70)
    print("  SAUVEGARDE")
    print("="*70 + "\n")

    chemin_resultat = projet_root / "benchmark_resultat_2165taches.json"

    with open(chemin_resultat, "w", encoding="utf-8") as f:
        json.dump({
            "instance": "Instance simulee 2165 taches",
            "caracteristiques": {
                "nb_taches": carac.nb_taches,
                "nb_ressources": carac.nb_ressources,
                "nb_contraintes": carac.nb_contraintes,
                "flexibilite_moyenne": carac.flexibilite_moyenne,
                "a_precedences": carac.a_precedences,
                "taille_categorie": carac.taille_categorie,
                "densite_contraintes": carac.densite_contraintes
            },
            "recommandation": {
                "algorithme": reco.algorithme,
                "raison": reco.raison,
                "parametres": reco.parametres_suggeres,
                "temps_estime": reco.temps_execution_estime,
                "qualite_attendue": reco.qualite_attendue,
                "alternatives": reco.alternatives
            },
            "comparaison": resultat.comparaison
        }, f, indent=2, ensure_ascii=False)

    print(f"Resultat sauvegarde : {chemin_resultat}")
    print()

    # Resume
    print("="*70)
    print("  BENCHMARK TERMINE")
    print("="*70 + "\n")

    print(f"Recommandation finale : Utilisez **{reco.algorithme.upper()}** !")
    print(f"  - Instance : 2165 taches simulees")
    print(f"  - Categorie : {carac.taille_categorie}")
    print(f"  - Algorithme : {reco.algorithme}")
    print(f"  - Qualite : {reco.qualite_attendue}")
    print(f"  - Temps : {reco.temps_execution_estime}")
    print()

    print("Prochaine etape :")
    print("  Implémenter l'algorithme " + reco.algorithme + " dans generation/algorithms/")
    print()


if __name__ == "__main__":
    main()
