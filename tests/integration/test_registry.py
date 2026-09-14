"""Couche 1 (§6.1) : le store est du code écrit à la main, déterministe —
Postgres + système de fichiers. Placé dans `integration/` (pas `unit/`)
depuis la migration §7.2 : contrairement à SQLite, ces tests ont besoin
d'un vrai serveur PostgreSQL accessible (`registre_test`, skip sinon —
même convention que `tests/integration/test_sandbox_*.py` pour Docker).
"""

from __future__ import annotations

import pytest

from solver_store.registry import ErreurIntegriteSolveur, Registre
from validation_engine.cascade import DiagnosticInstance, VerdictCascade

VERDICT_VERT = VerdictCascade(diagnostics=())
VERDICT_ROUGE = VerdictCascade(diagnostics=(DiagnosticInstance("un_cas", "faisabilite", ("planning illégal",)),))


def test_enregistrer_puis_recuperer_solveur(registre_test: Registre) -> None:
    id_solveur = registre_test.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence",
        verdict_cascade=VERDICT_VERT,
        instance_id="inst_a",
        client_id="client_a",
    )

    artefact = registre_test.recuperer_solveur(id_solveur)

    assert artefact.client_id == "client_a"
    assert artefact.instance_id == "inst_a"
    assert artefact.structure_contraintes == "precedence"
    assert artefact.code_source == "def resoudre(instance):\n    return None\n"
    assert artefact.chemin_code.exists()


def test_enregistrer_refuse_solveur_non_valide(registre_test: Registre) -> None:
    with pytest.raises(ValueError):
        registre_test.enregistrer_solveur(
            code_source="def resoudre(instance):\n    return None\n",
            structure_contraintes="precedence",
            verdict_cascade=VERDICT_ROUGE,
            instance_id="inst_x",
        )


def test_recuperer_solveur_inconnu_leve_keyerror(registre_test: Registre) -> None:
    with pytest.raises(KeyError):
        registre_test.recuperer_solveur("id-inexistant")


def test_alteration_du_fichier_fige_est_detectee(registre_test: Registre) -> None:
    id_solveur = registre_test.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence",
        verdict_cascade=VERDICT_VERT,
        instance_id="inst_x",
    )

    artefact = registre_test.recuperer_solveur(id_solveur)
    artefact.chemin_code.write_text("def resoudre(instance):\n    return 'altere'\n", encoding="utf-8")

    with pytest.raises(ErreurIntegriteSolveur):
        registre_test.recuperer_solveur(id_solveur)


def test_desactiver_solveur_le_retire_de_la_recherche(registre_test: Registre) -> None:
    id_solveur = registre_test.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence",
        verdict_cascade=VERDICT_VERT,
        instance_id="inst_c",
        client_id="client_c",
    )

    resultats = registre_test.rechercher_solveurs(client_id="client_c")
    assert [a.id for a in resultats] == [id_solveur]
    assert resultats[0].actif is True

    registre_test.desactiver_solveur(id_solveur)

    assert registre_test.rechercher_solveurs(client_id="client_c") == []

    resultats_avec_inactifs = registre_test.rechercher_solveurs(client_id="client_c", inclure_inactifs=True)
    assert [a.id for a in resultats_avec_inactifs] == [id_solveur]
    assert resultats_avec_inactifs[0].actif is False

    # La ligne/l'artefact restent consultables directement, juste hors circulation
    artefact = registre_test.recuperer_solveur(id_solveur)
    assert artefact.actif is False
    assert artefact.chemin_code.exists()


def test_desactiver_solveur_inconnu_leve_keyerror(registre_test: Registre) -> None:
    with pytest.raises(KeyError):
        registre_test.desactiver_solveur("id-inexistant")


def test_rechercher_par_client_et_structure(registre_test: Registre) -> None:
    id_a = registre_test.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence",
        verdict_cascade=VERDICT_VERT,
        instance_id="inst_a",
        client_id="client_a",
    )
    id_b = registre_test.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence,compatibilite_ressource_tache",
        verdict_cascade=VERDICT_VERT,
        instance_id="inst_b",
        client_id="client_b",
    )

    resultats_client_a = registre_test.rechercher_solveurs(client_id="client_a")
    assert [artefact.id for artefact in resultats_client_a] == [id_a]

    resultats_structure = registre_test.rechercher_solveurs(
        structure_contraintes="precedence,compatibilite_ressource_tache"
    )
    assert [artefact.id for artefact in resultats_structure] == [id_b]


def test_solveur_ne_sert_que_son_instance_meme_structure_partagee(registre_test: Registre) -> None:
    """Un solveur ne doit jamais être trouvé pour une AUTRE instance, même de structure et
    client identiques — fin du partage par signature entre instances d'un même client."""
    id_pour_inst_1 = registre_test.enregistrer_solveur(
        code_source="def resoudre(instance):\n    return None\n",
        structure_contraintes="precedence,compatibilite_ressource_tache",
        verdict_cascade=VERDICT_VERT,
        instance_id="inst_1",
        client_id="client_partage",
    )

    resultats_inst_1 = registre_test.rechercher_solveurs(client_id="client_partage", instance_id="inst_1")
    assert [artefact.id for artefact in resultats_inst_1] == [id_pour_inst_1]

    # Même client, même structure de contraintes, mais une AUTRE instance : aucun résultat.
    resultats_inst_2 = registre_test.rechercher_solveurs(client_id="client_partage", instance_id="inst_2")
    assert resultats_inst_2 == []

    # Le filtre structure seul (sans instance_id) continue de trouver le solveur — c'est le
    # filtre instance_id qui borne désormais la réutilisation, pas la disponibilité du filtre
    # structure lui-même (toujours utile comme vérification de compatibilité, voir
    # `api/routes/execution.py`).
    resultats_structure_seule = registre_test.rechercher_solveurs(
        client_id="client_partage", structure_contraintes="precedence,compatibilite_ressource_tache"
    )
    assert [artefact.id for artefact in resultats_structure_seule] == [id_pour_inst_1]
