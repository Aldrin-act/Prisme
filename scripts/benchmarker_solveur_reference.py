"""Benchmark du solveur de référence sur le catalogue du banc synthétique.

Pour chaque instance de `validation_engine/synthetic_bench/`, résout avec
`solveur_reference.resoudre` et compare le makespan obtenu à l'optimum connu
par construction (§6.4), en rapportant aussi le temps de résolution — la
calibration de performance visée par l'étape « solveur de référence ».

Usage : python scripts/benchmarker_solveur_reference.py
"""

from __future__ import annotations

from validation_engine.synthetic_bench import generer_catalogue
from solveur_reference import resoudre


def main() -> None:
    entetes = ("cas", "n_taches", "optimum", "statut", "makespan", "ecart", "temps_s")
    ligne_format = "{:<28} {:>8} {:>8} {:>10} {:>9} {:>7} {:>9}"
    print(ligne_format.format(*entetes))

    for cas in generer_catalogue():
        resultat = resoudre(cas.instance)
        ecart = "-" if resultat.makespan is None else resultat.makespan - cas.optimum
        print(
            ligne_format.format(
                cas.nom,
                len(cas.instance.taches),
                cas.optimum,
                resultat.statut,
                resultat.makespan if resultat.makespan is not None else "-",
                ecart,
                f"{resultat.temps_resolution_s:.3f}",
            )
        )


if __name__ == "__main__":
    main()
