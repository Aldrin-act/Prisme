"""Couche 1 (§6.1) : le store est du code écrit à la main, déterministe —
SQLite + système de fichiers, sans dépendance externe (pas de Docker requis
ici, contrairement à `tests/integration/test_sandbox_*.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from solver_store.registry import ErreurIntegriteSolveur, Registre
from validation_engine.cascade import DiagnosticInstance, VerdictCascade

VERDICT_VERT = VerdictCascade(diagnostics=())
VERDICT_ROUGE = VerdictCascade(diagnostics=(DiagnosticInstance("un_cas", "faisabilite", ("planning illégal",)),))


def _registre(tmp_path: Path) -> Registre:
    return Registre(chemin_base=tmp_path / "registre.sqlite3", dossier_artefacts=tmp_path / "artifacts")


def test_enregistrer_puis_recuperer_solveur(tmp_path: Path) -> None:
    registre = _registre(tmp_path)

    id_solveur = registre.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence",
        verdict_cascade=VERDICT_VERT,
        client_id="client_a",
    )

    artefact = registre.recuperer_solveur(id_solveur)

    assert artefact.client_id == "client_a"
    assert artefact.structure_contraintes == "precedence"
    assert artefact.code_source == "def resoudre(instance):\n    return None\n"
    assert artefact.chemin_code.exists()


def test_enregistrer_refuse_solveur_non_valide(tmp_path: Path) -> None:
    registre = _registre(tmp_path)

    with pytest.raises(ValueError):
        registre.enregistrer_solveur(
            code_source="def resoudre(instance):\n    return None\n",
            structure_contraintes="precedence",
            verdict_cascade=VERDICT_ROUGE,
        )


def test_recuperer_solveur_inconnu_leve_keyerror(tmp_path: Path) -> None:
    registre = _registre(tmp_path)

    with pytest.raises(KeyError):
        registre.recuperer_solveur("id-inexistant")


def test_alteration_du_fichier_fige_est_detectee(tmp_path: Path) -> None:
    registre = _registre(tmp_path)
    id_solveur = registre.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence",
        verdict_cascade=VERDICT_VERT,
    )

    artefact = registre.recuperer_solveur(id_solveur)
    artefact.chemin_code.write_text("def resoudre(instance):\n    return 'altere'\n", encoding="utf-8")

    with pytest.raises(ErreurIntegriteSolveur):
        registre.recuperer_solveur(id_solveur)


def test_rechercher_par_client_et_structure(tmp_path: Path) -> None:
    registre = _registre(tmp_path)
    id_a = registre.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence",
        verdict_cascade=VERDICT_VERT,
        client_id="client_a",
    )
    id_b = registre.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence,compatibilite_machine_tache",
        verdict_cascade=VERDICT_VERT,
        client_id="client_b",
    )

    resultats_client_a = registre.rechercher_solveurs(client_id="client_a")
    assert [artefact.id for artefact in resultats_client_a] == [id_a]

    resultats_structure = registre.rechercher_solveurs(
        structure_contraintes="precedence,compatibilite_machine_tache"
    )
    assert [artefact.id for artefact in resultats_structure] == [id_b]
