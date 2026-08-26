"""Couche 1 (§6.1) : `generateur.generer_code_depuis_plan` construit
correctement son `ResultatGenerationBrute` depuis une sortie structurée —
aucun appel LLM réel (voir `tests/unit/aides_test_agents.py`).
`generer_code_solveur` (mode simple, Étape 4) reste sur un simple `.invoke()`/
`extraire_bloc_code`, sans sortie structurée — non retesté ici."""

from __future__ import annotations

import json

import pytest

from generation.agents import generateur
from tests.unit.aides_test_agents import ModeleFactice


def test_generer_code_depuis_plan_construit_le_resultat_depuis_le_schema() -> None:
    schema = generateur._SchemaGenerationCode(code="def resoudre(instance):\n    return None\n")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = generateur.generer_code_depuis_plan(modele, "plan technique", algorithme="cp_sat")

    assert resultat.code_source == "def resoudre(instance):\n    return None\n"


def test_generer_code_depuis_plan_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(generateur.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        generateur.generer_code_depuis_plan(modele, "plan technique")


class _RunnableStructureSequence:
    def __init__(self, sequence: list[dict]) -> None:
        self._sequence = iter(sequence)

    def invoke(self, messages: object) -> dict:
        return next(self._sequence)


class _ModeleSequence:
    """Contrairement à `ModeleFactice` (stateless), renvoie une sortie différente à chaque
    appel — nécessaire ici puisque `autoriser_documentation=True` déclenche deux appels
    distincts (décision, puis génération de code). Un seul itérateur partagé entre tous les
    appels à `with_structured_output` : le recréer à chaque appel le ferait repartir du début."""

    def __init__(self, sequence: list[dict]) -> None:
        self._iterateur = iter(sequence)

    def with_structured_output(self, schema: type, include_raw: bool = True, method: str | None = None):
        return _RunnableStructureSequence(self._iterateur)


def _sortie(contenu: str, parsed: object, parsing_error: Exception | None = None) -> dict:
    from langchain_core.messages import AIMessage

    return {"raw": AIMessage(content=contenu), "parsed": parsed, "parsing_error": parsing_error}


def test_generer_code_depuis_plan_avec_documentation_autorisee_consulte_puis_genere() -> None:
    from generation.agents.outil_documentation import _SchemaBesoinDocumentation

    schema_final = generateur._SchemaGenerationCode(code="def resoudre(instance):\n    return None\n")
    modele = _ModeleSequence(
        [
            _sortie("{}", _SchemaBesoinDocumentation(sujet="tabu_search")),
            _sortie("{}", schema_final),
        ]
    )

    resultat = generateur.generer_code_depuis_plan(
        modele, "plan technique", algorithme="tabu_search", autoriser_documentation=True
    )

    assert resultat.code_source == "def resoudre(instance):\n    return None\n"


def test_generer_code_depuis_plan_sans_documentation_autorisee_ne_fait_qu_un_appel() -> None:
    schema_final = generateur._SchemaGenerationCode(code="def resoudre(instance):\n    return None\n")
    modele = _ModeleSequence([_sortie("{}", schema_final)])

    resultat = generateur.generer_code_depuis_plan(modele, "plan technique")

    assert resultat.code_source == "def resoudre(instance):\n    return None\n"
