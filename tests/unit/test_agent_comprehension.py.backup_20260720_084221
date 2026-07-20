"""Couche 1 (§6.1) : `comprendre_donnees_erp` ne fait qu'appeler un LLM et
parser sa réponse JSON — aucune dépendance externe (pas d'OR-Tools, pas de
BDD), donc `tests/unit/` plutôt que `integration/`. La validation réelle du
JSON produit contre `InstanceTRCO` est testée côté route API
(`tests/integration/test_api_adapters.py`), pas ici.
"""

from __future__ import annotations

import json

import pytest

from adapters.agent_comprehension import comprendre_donnees_erp
from generation.agents.base import ErreurReponseAgentInvalide


def _appel_factice(reponse: str):
    def appel(_prompt_systeme: str, _prompt_utilisateur: str) -> str:
        return reponse

    return appel


def test_comprehension_parse_une_reponse_json_valide() -> None:
    reponse = json.dumps(
        {
            "instance": {
                "taches": [{"id": "T1"}],
                "ressources": [{"id": "M1"}],
                "contraintes": [
                    {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "M1", "duree": 10}
                ],
                "objectifs": [{"type": "minimiser_makespan"}],
            },
            "avertissements": ["durée estimée, absente des données source"],
        }
    )

    resultat = comprendre_donnees_erp(_appel_factice(reponse), "T1;M1;10min")

    assert resultat.instance_brute["taches"] == [{"id": "T1"}]
    assert resultat.avertissements == ("durée estimée, absente des données source",)


def test_comprehension_tolere_labsence_davertissements() -> None:
    reponse = json.dumps(
        {
            "instance": {
                "taches": [{"id": "T1"}],
                "ressources": [{"id": "M1"}],
                "contraintes": [
                    {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "M1", "duree": 10}
                ],
                "objectifs": [{"type": "minimiser_makespan"}],
            }
        }
    )

    resultat = comprendre_donnees_erp(_appel_factice(reponse), "T1;M1;10min")

    assert resultat.avertissements == ()


def test_comprehension_leve_si_le_llm_ne_repond_pas_en_json() -> None:
    with pytest.raises(ErreurReponseAgentInvalide):
        comprendre_donnees_erp(_appel_factice("désolé, je ne peux pas faire ça."), "T1;M1;10min")
