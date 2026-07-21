"""Génère une instance simulée de 2165 tâches pour tester le benchmarker.

Simule la structure d'une instance GreenSig réelle :
- 2165 tâches
- ~30 ressources
- Flexibilité moyenne ~3-4 équipes/tâche
- Pas de précédences (comme GreenSig)
- Durées variées
"""

from __future__ import annotations

import json
import random
from pathlib import Path

projet_root = Path(__file__).parent.parent


def generer_instance_simulee():
    """Génère une instance simulée de 2165 tâches."""

    NB_TACHES = 2165
    NB_RESSOURCES = 30
    FLEXIBILITE_MIN = 1
    FLEXIBILITE_MAX = 6
    DUREE_MIN = 15
    DUREE_MAX = 180

    random.seed(42)  # Pour reproductibilité

    print(f"Génération d'une instance simulée de {NB_TACHES} tâches...")

    # Tâches
    taches = [{"id": f"T{i}"} for i in range(1, NB_TACHES + 1)]

    # Ressources
    ressources = [{"id": f"E{i}"} for i in range(1, NB_RESSOURCES + 1)]

    # Compatibilités ressource-tâche
    contraintes = []

    for tache in taches:
        # Flexibilité aléatoire (1 à 6 ressources par tâche)
        nb_ressources_compatibles = random.randint(FLEXIBILITE_MIN, FLEXIBILITE_MAX)
        ressources_compatibles = random.sample(
            [r["id"] for r in ressources],
            nb_ressources_compatibles
        )

        for ressource in ressources_compatibles:
            duree = random.randint(DUREE_MIN, DUREE_MAX)
            contraintes.append({
                "type": "compatibilite_ressource_tache",
                "tache": tache["id"],
                "ressource": ressource,
                "duree": duree
            })

    # Objectifs
    objectifs = [{"type": "minimiser_makespan"}]

    instance = {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": objectifs
    }

    # Statistiques
    from collections import Counter
    comp_par_tache = Counter(c["tache"] for c in contraintes)
    flexibilite_moyenne = sum(comp_par_tache.values()) / len(comp_par_tache)

    print(f"\nInstance generee :")
    print(f"   - Taches : {len(taches)}")
    print(f"   - Ressources : {len(ressources)}")
    print(f"   - Contraintes : {len(contraintes)}")
    print(f"   - Flexibilite moyenne : {flexibilite_moyenne:.2f} ressources/tache")
    print(f"   - Precedences : Non")

    return instance


def main():
    print("\n" + "="*70)
    print("  GENERATION INSTANCE SIMULEE 2165 TACHES")
    print("="*70 + "\n")

    instance = generer_instance_simulee()

    # Sauvegarder
    chemin = projet_root / "greensig_instance_trco_simulee.json"

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(instance, f, indent=2, ensure_ascii=False)

    print(f"\nInstance sauvegardee : {chemin}")
    print(f"   Taille : {chemin.stat().st_size / 1024:.1f} KB")

    print("\n" + "="*70)
    print("  INSTANCE PRETE")
    print("="*70 + "\n")

    print("Prochaine etape : Tester avec le benchmarker")
    print("   uv run python -m scripts.test_benchmarker_2165")
    print()


if __name__ == "__main__":
    main()
