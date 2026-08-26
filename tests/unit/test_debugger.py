"""Couche 1 (§6.1) : `debugger.corriger_code` construit correctement son
`ResultatCorrection` depuis une sortie structurée — aucun appel LLM réel
(voir `tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import debugger
from tests.unit.aides_test_agents import ModeleFactice


def test_corriger_code_construit_le_resultat_depuis_le_schema() -> None:
    schema = debugger._SchemaCorrection(code="def resoudre(instance):\n    return None\n", cause="import interdit")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = debugger.corriger_code(modele, "code cassé", "import os interdit")

    assert resultat.code_source == "def resoudre(instance):\n    return None\n"
    assert resultat.cause == "import interdit"


def test_corriger_code_defaut_prudent_si_cause_absente() -> None:
    schema = debugger._SchemaCorrection(code="def resoudre(instance):\n    return None\n", cause=None)
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = debugger.corriger_code(modele, "code cassé", "problème")

    assert resultat.cause == "non précisée"


def test_corriger_code_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(debugger.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        debugger.corriger_code(modele, "code cassé", "problème")


def test_corriger_solveur_ou_tests_designe_le_solveur_comme_cible() -> None:
    schema = debugger._SchemaCorrectionTestsSandbox(
        cible="solveur",
        code="def resoudre(instance):\n    return None\n",
        tests="def test_x(): assert True",
        cause="mauvaise contrainte de précédence",
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = debugger.corriger_solveur_ou_tests(modele, "code cassé", "def test_x(): assert True", "test échoué")

    assert resultat.cible == "solveur"
    assert resultat.code_source == "def resoudre(instance):\n    return None\n"
    assert resultat.tests_source == "def test_x(): assert True"
    assert resultat.cause == "mauvaise contrainte de précédence"


def test_corriger_solveur_ou_tests_designe_les_tests_comme_cible() -> None:
    schema = debugger._SchemaCorrectionTestsSandbox(
        cible="tests",
        code="code inchangé",
        tests="def test_x_corrige(): assert True",
        cause="attente erronée dans le test généré",
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = debugger.corriger_solveur_ou_tests(
        modele, "code inchangé", "def test_x(): assert False", "problème"
    )

    assert resultat.cible == "tests"
    assert resultat.tests_source == "def test_x_corrige(): assert True"


def test_corriger_solveur_ou_tests_defaut_prudent_si_cause_absente() -> None:
    schema = debugger._SchemaCorrectionTestsSandbox(cible="solveur", code="c", tests="t", cause=None)
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = debugger.corriger_solveur_ou_tests(modele, "c", "t", "problème")

    assert resultat.cause == "non précisée"


def test_corriger_solveur_ou_tests_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(debugger.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        debugger.corriger_solveur_ou_tests(modele, "code", "tests", "problème")


class _ModeleFacticeCapturant(ModeleFactice):
    """Capture le dernier prompt envoyé, pour vérifier son contenu sans dépendre d'un vrai appel LLM."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.dernier_prompt: str | None = None

    def with_structured_output(self, schema: type, include_raw: bool = True, method: str | None = None):
        runnable = super().with_structured_output(schema, include_raw, method)
        invoke_original = runnable.invoke

        def invoke_capturant(messages):
            self.dernier_prompt = messages[-1].content
            return invoke_original(messages)

        runnable.invoke = invoke_capturant
        return runnable


def test_corriger_code_sans_historique_indique_aucune_tentative_precedente() -> None:
    schema = debugger._SchemaCorrection(code="c", cause="cause")
    modele = _ModeleFacticeCapturant(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    debugger.corriger_code(modele, "code cassé", "problème")

    assert "Aucune tentative précédente dans cette génération." in modele.dernier_prompt


def test_corriger_code_avec_historique_l_injecte_dans_le_prompt() -> None:
    schema = debugger._SchemaCorrection(code="c", cause="cause")
    modele = _ModeleFacticeCapturant(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    debugger.corriger_code(
        modele, "code cassé", "problème", historique="Tentative 1 : problème = X → cause identifiée = Y"
    )

    assert "Tentative 1 : problème = X → cause identifiée = Y" in modele.dernier_prompt


def test_corriger_solveur_ou_tests_avec_historique_l_injecte_dans_le_prompt() -> None:
    schema = debugger._SchemaCorrectionTestsSandbox(cible="solveur", code="c", tests="t", cause="cause")
    modele = _ModeleFacticeCapturant(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    debugger.corriger_solveur_ou_tests(
        modele, "code", "tests", "problème", historique="Tentative 1 : déjà tenté et échoué"
    )

    assert "Tentative 1 : déjà tenté et échoué" in modele.dernier_prompt
