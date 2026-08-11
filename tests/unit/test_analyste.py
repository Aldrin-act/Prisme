"""Couche 1 (§6.1) : `analyste.analyser_mission` construit correctement son
`ResultatAnalyse` depuis une sortie structurée — aucun appel LLM réel (voir
`tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import analyste
from tests.unit.aides_test_agents import ModeleFactice


def test_analyser_mission_construit_le_resultat_depuis_le_schema() -> None:
    schema = analyste._SchemaAnalyse(
        entrees="Instance T-R-C-O", sorties="Planning", contraintes_a_couvrir=["c1", "c2"]
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = analyste.analyser_mission(modele)

    assert resultat.entrees == "Instance T-R-C-O"
    assert resultat.sorties == "Planning"
    assert resultat.contraintes_a_couvrir == ("c1", "c2")
    assert "### Entrées" in resultat.en_texte()


def test_analyser_mission_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(analyste.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        analyste.analyser_mission(modele)


def test_extraire_structure_instance_isole_les_types_distincts_et_tries() -> None:
    instance_json = {
        "taches": [{"id": "T1"}, {"id": "T2"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 5},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    structure = analyste.extraire_structure_instance(instance_json)

    assert structure.types_contraintes == ("compatibilite_ressource_tache", "precedence")
    assert structure.types_objectifs == ("minimiser_makespan",)
    assert structure.nb_taches == 2
    assert structure.nb_ressources == 1


def test_extraire_structure_instance_gere_une_instance_sans_contraintes_ni_objectifs() -> None:
    structure = analyste.extraire_structure_instance({})

    assert structure.types_contraintes == ()
    assert structure.types_objectifs == ()
    assert structure.nb_taches == 0
    assert structure.nb_ressources == 0


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


def test_analyser_mission_injecte_la_structure_de_linstance_dans_le_prompt() -> None:
    schema = analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=["c"])
    modele = _ModeleFacticeCapturant(raw_content=json.dumps(schema.model_dump()), parsed=schema)
    instance_json = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "precedence", "avant": "T1", "apres": "T1"}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    analyste.analyser_mission(modele, instance_json)

    assert "precedence" in modele.dernier_prompt
    assert "minimiser_makespan" in modele.dernier_prompt
    assert "1 tâche" in modele.dernier_prompt or "1 ressource" in modele.dernier_prompt


def test_analyser_mission_sans_instance_ne_leve_pas() -> None:
    """Appelants historiques sans instance sous la main (scripts, tests) — `instance_json`
    optionnel, ne doit jamais faire planter la construction du prompt."""
    schema = analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=[])
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = analyste.analyser_mission(modele)

    assert resultat.entrees == "e"
