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
