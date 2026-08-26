"""Couche 1 (§6.1) : `testeur.generer_tests` construit correctement son
`ResultatTests` depuis une sortie structurée — aucun appel LLM réel (voir
`tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import testeur
from tests.unit.aides_test_agents import ModeleFactice


def test_generer_tests_construit_le_resultat_depuis_le_schema() -> None:
    schema = testeur._SchemaTests(code_tests="def test_x():\n    assert True\n")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = testeur.generer_tests(modele, "def resoudre(instance): ...")

    assert resultat.code_tests == "def test_x():\n    assert True\n"


def test_generer_tests_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(testeur.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        testeur.generer_tests(modele, "def resoudre(instance): ...")


def test_generer_tests_sans_appel_d_outil_a_une_trace_vide() -> None:
    """Le faux modèle (`bind_tools` simulé, voir `aides_test_agents.py`) ne
    demande jamais d'outil — `appels_outils` doit refléter cette absence."""
    schema = testeur._SchemaTests(code_tests="def test_x():\n    assert True\n")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = testeur.generer_tests(modele, "def resoudre(instance): ...")

    assert resultat.appels_outils == ()


def test_generer_tests_sans_outils_fonctionne_toujours() -> None:
    schema = testeur._SchemaTests(code_tests="def test_x():\n    assert True\n")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = testeur.generer_tests(modele, "def resoudre(instance): ...", avec_outils=False)

    assert resultat.appels_outils == ()
    assert resultat.code_tests == "def test_x():\n    assert True\n"


class TestDecrireCasLimitesBancSynthetique:
    """`decrire_cas_limites_banc_synthetique` — fonction pure derrière
    l'outil LLM, testable sans modèle ni outil LangChain."""

    def test_renvoie_tous_les_cas_du_catalogue(self) -> None:
        from validation_engine.synthetic_bench.catalogue import generer_catalogue

        resultat = testeur.decrire_cas_limites_banc_synthetique()

        for cas in generer_catalogue():
            assert cas.nom in resultat
            assert str(cas.optimum) in resultat


def test_outil_cas_limites_banc_synthetique_delegue_a_la_fonction_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(testeur, "decrire_cas_limites_banc_synthetique", lambda: "profils factices")

    outil = testeur._construire_outil_cas_limites_banc_synthetique()

    assert outil.invoke({}) == "profils factices"
