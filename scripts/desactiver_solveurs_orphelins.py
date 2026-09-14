"""Nettoyage ponctuel (§7, migration instance_id) : désactive tout solveur actif enregistré
avant qu'un solveur ne soit rattaché à une instance précise (`instance_id IS NULL` —
`solver_store/registry.py::enregistrer_solveur`, `instance_id` obligatoire depuis ce
changement). Ces solveurs ne peuvent plus jamais être trouvés par `/execution` ni par la
supervision (les deux filtrent désormais sur `instance_id`) : les laisser actifs ne fait que
les garder visibles, inertes, dans la liste des solveurs générés.

Désactive plutôt que supprime — même principe que `Registre.desactiver_solveur` partout
ailleurs : la ligne et l'artefact restent consultables pour l'audit/historique
(`rechercher_solveurs(inclure_inactifs=True)`), seule leur visibilité par défaut change.

Usage, depuis la racine du dépôt : python -m scripts.desactiver_solveurs_orphelins [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from solver_store.registry import Registre


def desactiver_orphelins(registre: Registre, dry_run: bool = False) -> list[str]:
    """Renvoie les ids désactivés (ou qui le seraient, en `dry_run`)."""
    solveurs_actifs = registre.rechercher_solveurs()
    orphelins = [s for s in solveurs_actifs if s.instance_id is None]

    for solveur in orphelins:
        print(
            f"  - {solveur.id} (client={solveur.client_id!r}, "
            f"structure={solveur.structure_contraintes!r}, généré le {solveur.date_validation})"
        )
        if not dry_run:
            registre.desactiver_solveur(solveur.id)

    return [s.id for s in orphelins]


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    registre = Registre()

    print("\n" + "=" * 70)
    print("  NETTOYAGE DES SOLVEURS ORPHELINS (sans instance_id)")
    print("=" * 70 + "\n")

    if dry_run:
        print("Mode --dry-run : aucune modification, juste la liste ci-dessous.\n")

    ids = desactiver_orphelins(registre, dry_run=dry_run)

    if not ids:
        print("Aucun solveur orphelin actif trouvé — rien à faire.\n")
        return

    verbe = "seraient désactivés" if dry_run else "désactivés"
    print(f"\n{len(ids)} solveur(s) {verbe}.")
    if not dry_run:
        print("Toujours consultables via rechercher_solveurs(inclure_inactifs=True).\n")


if __name__ == "__main__":
    main()
