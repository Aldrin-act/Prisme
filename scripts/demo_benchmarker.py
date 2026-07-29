"""Démonstration de l'agent Benchmarker.

Analyse une instance T-R-C-O et recommande le meilleur algorithme
d'ordonnancement au lieu de forcer CP-SAT systématiquement.

Exemples testés :
1. Petite instance (10 tâches) → CP-SAT optimal
2. Moyenne instance (100 tâches) → CP-SAT ou Tabu
3. Grande instance (500 tâches) → GA ou ACO
4. Très grande instance (2165 tâches GreenSig) → GA obligatoire
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
except ImportError:
    pass


def main():
    print("\n" + "🔬"*35)
    print("  DÉMONSTRATION AGENT BENCHMARKER")
    print("🔬"*35 + "\n")

    print("🎯 Objectif : Recommander le MEILLEUR algorithme pour une instance")
    print("   au lieu de forcer CP-SAT systématiquement.\n")

    # Choisir une instance
    print("="*70)
    print("  SÉLECTION DE L'INSTANCE")
    print("="*70 + "\n")

    print("Instances disponibles :\n")
    print("1. Petite (10 tâches, 5 ressources) - DSL exemple")
    print("2. Moyenne (100 tâches) - Subset GreenSig")
    print("3. Grande (500 tâches) - Subset GreenSig")
    print("4. Très grande (2165 tâches) - GreenSig complet")
    print("5. Personnalisée (charger un JSON)\n")

    choix = input("Votre choix [1-5, défaut=4] : ").strip() or "4"

    # Charger l'instance
    if choix == "1":
        # Créer une petite instance
        instance_json = creer_petite_instance()
        nom_instance = "Petite (10 tâches)"
    elif choix == "2":
        instance_json = charger_subset(100)
        nom_instance = "Moyenne (100 tâches subset)"
    elif choix == "3":
        instance_json = charger_subset(500)
        nom_instance = "Grande (500 tâches subset)"
    elif choix == "4":
        instance_json = charger_instance_greensig()
        nom_instance = "Très grande (2165 tâches GreenSig)"
    else:
        chemin = input("Chemin du fichier JSON : ").strip()
        with open(chemin, encoding="utf-8") as f:
            instance_json = json.load(f)
        nom_instance = Path(chemin).name

    print(f"\n✅ Instance chargée : {nom_instance}\n")

    # Analyser les caractéristiques
    print("="*70)
    print("  ANALYSE DES CARACTÉRISTIQUES")
    print("="*70 + "\n")

    from generation.agents.benchmarker import analyser_caracteristiques_instance

    carac = analyser_caracteristiques_instance(instance_json)

    print(f"📊 Caractéristiques :")
    print(f"   • Tâches : {carac.nb_taches}")
    print(f"   • Ressources : {carac.nb_ressources}")
    print(f"   • Contraintes : {carac.nb_contraintes}")
    print(f"   • Flexibilité moyenne : {carac.flexibilite_moyenne:.2f} équipes/tâche")
    print(f"   • Précédences : {'Oui' if carac.a_precedences else 'Non'}")
    print(f"   • Taille : {carac.taille_categorie}")
    print(f"   • Densité de contraintes : {carac.densite_contraintes:.3f}")
    print()

    # Appel de l'agent benchmarker
    print("="*70)
    print("  BENCHMARKING (APPEL LLM)")
    print("="*70 + "\n")

    print("🤖 Appel de l'agent Benchmarker...\n")

    try:
        from generation.agents.client_llm import construire_modele_pour_agent
        from generation.agents.benchmarker import benchmarker_algorithmes

        modele = construire_modele_pour_agent("benchmarker")
        resultat = benchmarker_algorithmes(modele, instance_json)

    except ImportError as e:
        print(f"❌ Erreur d'import : {e}")
        print("   Installez les dépendances LLM : uv sync --extra llm")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur lors du benchmark : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Afficher la recommandation
    print("="*70)
    print("  RECOMMANDATION")
    print("="*70 + "\n")

    reco = resultat.recommandation

    print(f"🎯 Algorithme recommandé : **{reco.algorithme.upper()}**\n")
    print(f"📝 Raison :")
    print(f"   {reco.raison}\n")

    print(f"⏱️  Temps d'exécution estimé : {reco.temps_execution_estime}")
    print(f"🎯 Qualité attendue : {reco.qualite_attendue}\n")

    if reco.parametres_suggeres:
        print(f"⚙️  Paramètres suggérés :")
        for param, valeur in reco.parametres_suggeres.items():
            print(f"   • {param}: {valeur}")
        print()

    if reco.alternatives:
        print(f"🔄 Alternatives :")
        for alt in reco.alternatives:
            print(f"   • {alt}")
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

    chemin_resultat = projet_root / f"benchmark_resultat_{carac.nb_taches}taches.json"

    with open(chemin_resultat, "w", encoding="utf-8") as f:
        json.dump({
            "instance": nom_instance,
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

    print(f"💾 Résultat sauvegardé : {chemin_resultat}")
    print()

    # Résumé
    print("="*70)
    print("  ✅ BENCHMARK TERMINÉ")
    print("="*70 + "\n")

    print(f"🎉 Recommandation : Utilisez **{reco.algorithme.upper()}** pour cette instance !")
    print(f"   • Instance : {nom_instance}")
    print(f"   • Taille : {carac.taille_categorie} ({carac.nb_taches} tâches)")
    print(f"   • Algorithme : {reco.algorithme}")
    print(f"   • Qualité : {reco.qualite_attendue}")
    print()


def creer_petite_instance():
    """Crée une petite instance d'exemple."""
    return {
        "taches": [{"id": f"T{i}"} for i in range(1, 11)],
        "ressources": [{"id": f"R{i}"} for i in range(1, 6)],
        "contraintes": [
            {
                "type": "compatibilite_ressource_tache",
                "tache": f"T{i}",
                "ressource": f"R{(i % 5) + 1}",
                "duree": 30
            }
            for i in range(1, 11)
        ] + [
            {
                "type": "precedence",
                "avant": f"T{i}",
                "apres": f"T{i+1}"
            }
            for i in range(1, 5)
        ],
        "objectifs": [{"type": "minimiser_makespan"}]
    }


def charger_subset(nb_taches: int):
    """Charge un subset de GreenSig."""
    chemin = projet_root / "greensig_instance_trco_reel.json"

    if not chemin.exists():
        print(f"❌ Fichier introuvable : {chemin}")
        print("   Exécutez d'abord : uv run python -m scripts.demo_greensig_vraies_donnees")
        sys.exit(1)

    with open(chemin, encoding="utf-8") as f:
        instance_complete = json.load(f)

    # Filtrer les N premières tâches
    taches = instance_complete["taches"][:nb_taches]
    ids_taches = {t["id"] for t in taches}

    contraintes = [
        c for c in instance_complete["contraintes"]
        if c.get("type") != "compatibilite_ressource_tache" or c["tache"] in ids_taches
    ]

    ressources_utilisees = {
        c["ressource"] for c in contraintes
        if c.get("type") == "compatibilite_ressource_tache"
    }

    ressources = [r for r in instance_complete["ressources"] if r["id"] in ressources_utilisees]

    return {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": instance_complete["objectifs"]
    }


def charger_instance_greensig():
    """Charge l'instance GreenSig complète."""
    chemin = projet_root / "greensig_instance_trco_reel.json"

    if not chemin.exists():
        print(f"❌ Fichier introuvable : {chemin}")
        print("   Exécutez d'abord : uv run python -m scripts.demo_greensig_vraies_donnees")
        sys.exit(1)

    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    main()
