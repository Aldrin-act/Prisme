"""Génère/rafraîchit le catalogue versionné du banc synthétique (§6.4).

À relancer après toute modification de
`validation_engine/synthetic_bench/construction_inverse.py` ou du catalogue
(`catalogue.py`), pour que les fichiers sous `instances/` restent à jour.

Usage : python scripts/generer_banc_synthetique.py
"""

from __future__ import annotations

from validation_engine.synthetic_bench.catalogue import DOSSIER_INSTANCES, generer_catalogue
from validation_engine.synthetic_bench.stockage import sauvegarder


def main() -> None:
    DOSSIER_INSTANCES.mkdir(parents=True, exist_ok=True)
    for cas in generer_catalogue():
        chemin = sauvegarder(cas, DOSSIER_INSTANCES)
        print(f"écrit : {chemin}")


if __name__ == "__main__":
    main()
