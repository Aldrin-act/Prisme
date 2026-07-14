"""Couche 1 (§6.1), Docker requis. Critère de validation de l'Étape 7 : un
solveur validé est stocké, réexécuté sur de nouvelles données dans un
conteneur qui meurt après, et le résultat est vérifié par le garde-fou de
faisabilité (§6.7) — les trois pièces (store, sandbox, garde-fou) bouclées
ensemble.
"""

from __future__ import annotations

from pathlib import Path

import solveur_reference.solveur as _module_solveur_reference
from sandbox.runner import executer_solveur_valide
from solver_store.registry import Registre
from validation_engine.cascade import VerdictCascade
from validation_engine.synthetic_bench import generer_catalogue


def test_solveur_valide_stocke_puis_execute_en_sandbox(tmp_path: Path, image_sandbox: str) -> None:
    registre = Registre(
        chemin_base=tmp_path / "registre.sqlite3",
        dossier_artefacts=tmp_path / "artifacts",
    )
    code_source = Path(_module_solveur_reference.__file__).read_text(encoding="utf-8")

    # Un verdict vert « à blanc » : ce test vérifie le câblage store → sandbox
    # → garde-fou, pas la cascade elle-même (déjà couverte ailleurs).
    id_solveur = registre.enregistrer_solveur(
        code_source=code_source,
        structure_contraintes="precedence,compatibilite_machine_tache",
        verdict_cascade=VerdictCascade(diagnostics=()),
    )

    cas = next(c for c in generer_catalogue() if c.nom == "taille_2_chaine_simple")

    resultat = executer_solveur_valide(registre, id_solveur, cas.instance)

    assert resultat.reussi, resultat.erreur
    assert resultat.planning is not None
    assert resultat.verdict_faisabilite is not None
    assert resultat.verdict_faisabilite.legal
