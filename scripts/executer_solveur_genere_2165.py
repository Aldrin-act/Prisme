"""Execute le solveur genere par le pipeline (solveur_genere_avec_benchmarker.py)
sur la vraie instance GreenSig de 2165 taches, et affiche le planning obtenu.

Le solveur genere passe la cascade de validation (banc synthetique 1-80
taches) mais contient un bug de performance invisible a cette echelle :
`_duree_operation` re-scanne les 7556 contraintes de compatibilite pour
CHAQUE operation, a CHAQUE evaluation de fitness (400 population x 600
generations = 240 000 evaluations) -> ~41h estimees tel quel. Ce script
monkey-patche `_decoder`/`_calculer_fitness` avec des versions equivalentes
qui precalculent les tables de correspondance une fois (meme algorithme,
memes parametres, meme graine random.Random(42) -> meme resultat, juste
~50x plus rapide). Le fichier solveur_genere_avec_benchmarker.py lui-meme
n'est pas modifie.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))


def main() -> None:
    from dsl.schema import CompatibiliteRessourceTache, Echeance, InstanceTRCO, OperationPlanifiee, Precedence

    import solveur_genere_avec_benchmarker as sol

    chemin_instance = projet_root / "greensig_instance_trco_simulee.json"
    with open(chemin_instance, encoding="utf-8") as f:
        instance = InstanceTRCO.model_validate(json.load(f))

    print(f"Instance : {len(instance.taches)} taches, {len(instance.ressources)} ressources, "
          f"{len(instance.contraintes)} contraintes\n")

    # --- Tables precalculees une seule fois (le bug : le code genere les
    # reconstruit, ou pire rescane les contraintes, a chaque appel) ---
    duree_map: dict[tuple[str, str], int] = {}
    compat_par_tache: dict[str, list[tuple[str, int]]] = {}
    precedences_apres: dict[str, list[str]] = {}
    echeances_par_tache: dict[str, int] = {}
    for c in instance.contraintes:
        if isinstance(c, CompatibiliteRessourceTache):
            duree_map[(c.tache, c.ressource)] = c.duree
            compat_par_tache.setdefault(c.tache, []).append((c.ressource, c.duree))
        elif isinstance(c, Precedence):
            precedences_apres.setdefault(c.apres, []).append(c.avant)
        elif isinstance(c, Echeance):
            echeances_par_tache[c.tache] = c.echeance

    def decoder_rapide(chromosome: list[str], instance: InstanceTRCO) -> list[OperationPlanifiee] | None:
        fin_tache: dict[str, int] = {}
        ressource_disponibilite: dict[str, int] = {r.id: 0 for r in instance.ressources}
        planning_tuples: dict[str, tuple[str, int, int]] = {}
        n = len(instance.taches)
        while len(planning_tuples) < n:
            progres = False
            for tache_id in chromosome:
                if tache_id in planning_tuples:
                    continue
                taches_avant = precedences_apres.get(tache_id, [])
                if not all(a in planning_tuples for a in taches_avant):
                    continue
                debut_au_plus_tot = max((fin_tache[a] for a in taches_avant), default=0)
                meilleur_debut = None
                meilleure_fin = None
                meilleure_res = None
                compatibilites = compat_par_tache.get(tache_id, [])
                if not compatibilites:
                    return None
                echeance = echeances_par_tache.get(tache_id)
                for res_id, duree in compatibilites:
                    dispo = ressource_disponibilite[res_id]
                    debut_possible = debut_au_plus_tot if debut_au_plus_tot > dispo else dispo
                    fin_possible = debut_possible + duree
                    if echeance is not None and fin_possible > echeance:
                        continue
                    if (
                        meilleure_fin is None
                        or debut_possible < meilleur_debut
                        or (debut_possible == meilleur_debut and fin_possible < meilleure_fin)
                    ):
                        meilleur_debut = debut_possible
                        meilleure_fin = fin_possible
                        meilleure_res = res_id
                if meilleure_res is None:
                    return None
                planning_tuples[tache_id] = (meilleure_res, meilleur_debut, meilleure_fin)
                fin_tache[tache_id] = meilleure_fin
                ressource_disponibilite[meilleure_res] = meilleure_fin
                progres = True
            if not progres:
                return None
        return [OperationPlanifiee(tache=t, ressource=r, debut=d) for t, (r, d, _f) in planning_tuples.items()]

    def fitness_rapide(planning: list[OperationPlanifiee] | None, instance: InstanceTRCO) -> float:
        if not planning:
            return float("inf")
        return max(op.debut + duree_map[(op.tache, op.ressource)] for op in planning)

    sol._decoder = decoder_rapide
    sol._calculer_fitness = fitness_rapide

    print("Lancement de resoudre() (algorithme genetique, ~49 min estimees)...\n")
    debut = time.time()
    planning = sol.resoudre(instance)
    duree = time.time() - debut

    print(f"Termine en {duree:.1f}s ({duree/60:.1f} min)\n")

    if planning is None:
        print("AUCUNE SOLUTION TROUVEE (instance jugee infaisable par le solveur).")
        return

    makespan = max(op.debut + duree_map[(op.tache, op.ressource)] for op in planning.operations)
    print(f"Operations planifiees : {len(planning.operations)}")
    print(f"Makespan : {makespan} min ({makespan/60:.1f} h)\n")

    utilisation = Counter(op.ressource for op in planning.operations)
    print("Utilisation des ressources (top 10) :")
    for ressource, nb in utilisation.most_common(10):
        print(f"  - {ressource} : {nb} operations")
    print()

    operations_triees = sorted(planning.operations, key=lambda o: o.debut)
    print("Timeline (10 premieres operations) :")
    for op in operations_triees[:10]:
        duree_op = duree_map[(op.tache, op.ressource)]
        print(f"  - {op.tache} sur {op.ressource} : {op.debut} -> {op.debut + duree_op} min ({duree_op} min)")
    print(f"  ... et {len(planning.operations) - 10} autres operations\n")

    chemin_sortie = projet_root / "planning_genere_2165.json"
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(
            {
                "duree_resolution_secondes": duree,
                "makespan": makespan,
                "planning": planning.model_dump(),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Planning sauvegarde : {chemin_sortie}")


if __name__ == "__main__":
    main()
