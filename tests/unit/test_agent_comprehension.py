"""Couche 1 (§6.1) : `comprendre_donnees_erp` ne fait qu'appeler un LLM et
parser sa sortie structurée — aucune dépendance externe (pas d'OR-Tools, pas
de BDD), donc `tests/unit/` plutôt que `integration/`. La validation réelle
du JSON produit contre `InstanceTRCO` est testée côté route API
(`tests/integration/test_api_adapters.py`), pas ici.
"""

from __future__ import annotations

import pytest

from adapters.agent_comprehension.agent import (
    _SchemaComprehension,
    comprendre_donnees_erp,
    construire_prompt_comprehension,
)
from generation.agents.base import ErreurReponseAgentInvalide
from tests.unit.aides_test_agents import ModeleFactice


def test_comprehension_parse_une_reponse_valide() -> None:
    schema = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
        avertissements=["durée estimée, absente des données source"],
    )
    modele = ModeleFactice(raw_content="{}", parsed=schema)

    resultat = comprendre_donnees_erp(modele, "T1;M1;10min")

    assert resultat.instance_brute["taches"] == [{"id": "T1"}]
    assert resultat.description_metier == "Une tâche T1 exécutée sur la ressource R1."
    assert resultat.avertissements == ("durée estimée, absente des données source",)


def test_comprehension_tolere_labsence_davertissements() -> None:
    schema = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
    )
    modele = ModeleFactice(raw_content="{}", parsed=schema)

    resultat = comprendre_donnees_erp(modele, "T1;M1;10min")

    assert resultat.avertissements == ()


def test_construire_prompt_comprehension_injecte_les_instructions_complementaires() -> None:
    _, prompt_utilisateur = construire_prompt_comprehension(
        "T1;R1;10min", instructions_complementaires="Le poste CTRL est ouvert 24/7"
    )

    assert "Instructions complémentaires" in prompt_utilisateur
    assert "Le poste CTRL est ouvert 24/7" in prompt_utilisateur


def test_construire_prompt_comprehension_sans_instructions_affiche_aucune() -> None:
    _, prompt_utilisateur = construire_prompt_comprehension("T1;R1;10min")

    assert "(aucune)" in prompt_utilisateur


def test_comprendre_donnees_erp_accepte_des_instructions_complementaires() -> None:
    """Le contenu exact du prompt envoyé au modèle est déjà couvert par
    `test_construire_prompt_comprehension_injecte_les_instructions_complementaires` ci-dessus —
    ici, seulement que le paramètre traverse `comprendre_donnees_erp` sans casser le flux."""
    schema = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
    )
    modele = ModeleFactice(raw_content="{}", parsed=schema)

    resultat = comprendre_donnees_erp(modele, "T1;M1;10min", instructions_complementaires="Contexte additionnel")

    assert resultat.instance_brute["taches"] == [{"id": "T1"}]


def test_comprehension_corrige_une_faute_sur_le_type_dun_objectif() -> None:
    """Régression : un modèle a produit "minimizer_makespan" (anglicisme/faute) au lieu de
    "minimiser_makespan", provoquant un rejet 422 en aval malgré une donnée par ailleurs correcte
    — voir `_corriger_types_dsl` (agent.py)."""
    schema = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimizer_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
    )
    modele = ModeleFactice(raw_content="{}", parsed=schema)

    resultat = comprendre_donnees_erp(modele, "T1;M1;10min")

    assert resultat.instance_brute["objectifs"] == [{"type": "minimiser_makespan"}]
    assert resultat.avertissements == ("objectif : type 'minimizer_makespan' corrigé en 'minimiser_makespan'",)


def test_comprehension_ne_corrige_pas_un_type_sans_correspondance_proche() -> None:
    """Un type manifestement différent (pas une faute de frappe) n'est jamais réinterprété — la
    validation `InstanceTRCO` en aval reste l'arbitre honnête de ce cas."""
    schema = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [{"type": "un_type_totalement_invente", "tache": "T1"}],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
    )
    modele = ModeleFactice(raw_content="{}", parsed=schema)

    resultat = comprendre_donnees_erp(modele, "T1;M1;10min")

    assert resultat.instance_brute["contraintes"][0]["type"] == "un_type_totalement_invente"
    assert resultat.avertissements == ()


def test_comprehension_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(ErreurReponseAgentInvalide, match="pas du JSON valide"):
        comprendre_donnees_erp(modele, "T1;M1;10min")
