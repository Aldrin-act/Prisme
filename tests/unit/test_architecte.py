"""Couche 1 (§6.1) : `architecte.concevoir_modele` construit correctement son
`ResultatConception` depuis une sortie structurée — aucun appel LLM réel
(voir `tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import architecte
from generation.agents.analyste import ResultatAnalyse
from tests.unit.aides_test_agents import ModeleFactice

_ANALYSE = ResultatAnalyse(
    reponse_brute="", entrees="Instance T-R-C-O", sorties="Planning", contraintes_a_couvrir=()
)


def test_concevoir_modele_construit_le_resultat_depuis_le_schema() -> None:
    schema = architecte._SchemaConception(
        variables="Une IntVar debut/fin par tâche.",
        contraintes_modele="AddNoOverlap par ressource.",
        objectif="Minimiser le makespan.",
        fonctions_internes=None,
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = architecte.concevoir_modele(modele, _ANALYSE)

    assert resultat.variables == "Une IntVar debut/fin par tâche."
    assert resultat.fonctions_internes is None
    assert "aucune — une seule fonction resoudre()" in resultat.en_texte()


def test_concevoir_modele_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(architecte.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        architecte.concevoir_modele(modele, _ANALYSE)


class _RunnableStructureSequence:
    def __init__(self, sequence: list[dict]) -> None:
        self._sequence = iter(sequence)

    def invoke(self, messages: object) -> dict:
        return next(self._sequence)


class _ModeleSequence:
    """Contrairement à `ModeleFactice` (stateless), renvoie une sortie différente à chaque
    `with_structured_output(...).invoke(...)` — nécessaire ici puisque
    `autoriser_documentation=True` déclenche deux appels distincts (décision, puis conception).
    Un seul itérateur partagé entre tous les appels à `with_structured_output` : le recréer à
    chaque appel (`iter(sequence)`) le ferait repartir du début à chaque fois, au lieu
    d'avancer d'un appel à l'autre."""

    def __init__(self, sequence: list[dict]) -> None:
        self._iterateur = iter(sequence)

    def with_structured_output(self, schema: type, include_raw: bool = True, method: str | None = None):
        return _RunnableStructureSequence(self._iterateur)


def _sortie(contenu: str, parsed: object, parsing_error: Exception | None = None) -> dict:
    from langchain_core.messages import AIMessage

    return {"raw": AIMessage(content=contenu), "parsed": parsed, "parsing_error": parsing_error}


def test_concevoir_modele_avec_documentation_autorisee_consulte_puis_concoit() -> None:
    from generation.agents.outil_documentation import _SchemaBesoinDocumentation

    schema_final = architecte._SchemaConception(
        variables="v", contraintes_modele="c", objectif="o", fonctions_internes=None
    )
    modele = _ModeleSequence(
        [
            _sortie("{}", _SchemaBesoinDocumentation(sujet="aco")),
            _sortie("{}", schema_final),
        ]
    )

    resultat = architecte.concevoir_modele(modele, _ANALYSE, algorithme="aco", autoriser_documentation=True)

    assert resultat.variables == "v"


def test_concevoir_modele_sans_documentation_autorisee_ne_fait_qu_un_appel() -> None:
    """Comportement par défaut inchangé : `autoriser_documentation=False` (défaut) ne consomme
    qu'une seule sortie de la séquence — la deuxième ne serait jamais atteinte si un appel de
    décision était fait à tort."""
    schema_final = architecte._SchemaConception(
        variables="v", contraintes_modele="c", objectif="o", fonctions_internes=None
    )
    modele = _ModeleSequence([_sortie("{}", schema_final)])

    resultat = architecte.concevoir_modele(modele, _ANALYSE)

    assert resultat.variables == "v"
