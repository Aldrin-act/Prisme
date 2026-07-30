"""Couche 1 (§6.1) : `adapters/json_import/traducteur.py` — la version JSON
(un seul payload structuré) de la compatibilité dérivée par compétence,
miroir de `adapters/csv_import/` (voir `tests/unit/test_csv_import_adapter.py`).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adapters.json_import import ErreurPayloadInvalide, traduire


def _payload_de_base(**surcharges: object) -> dict:
    payload = {
        "taches": [{"id": "T1", "nom": "Decoupe"}, {"id": "T2", "nom": "Assemblage"}],
        "ressources": [{"id": "R1", "nom": "Decoupeuse"}],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 15},
        ],
    }
    payload.update(surcharges)
    return payload


def test_traduire_ingere_une_instance_canonique_sans_transformation() -> None:
    """Sur-ensemble strict du format canonique : un payload sans compétence ni
    durée estimée est ingéré tel quel, comme POST /ingestion/{client_id}."""
    instance = traduire(_payload_de_base())

    assert [t.id for t in instance.taches] == ["T1", "T2"]
    assert len(instance.contraintes) == 3
    assert instance.objectifs[0].type == "minimiser_makespan"


def test_traduire_derive_la_compatibilite_par_competence() -> None:
    payload = {
        "taches": [{"id": "T1", "duree_estimee_jours": 25}],
        "ressources": [
            {"id": "R1", "competences": ["decoupe", "affutage"]},
            {"id": "R2", "competences": ["assemblage"]},
        ],
        "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
    }

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 25)]


def test_traduire_sans_duree_estimee_leve_erreur_payload_invalide() -> None:
    payload = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1", "competences": ["decoupe"]}],
        "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
    }

    with pytest.raises(ErreurPayloadInvalide, match="durée estimée manquante"):
        traduire(payload)


def test_traduire_payload_structurellement_invalide_leve_erreur_payload_invalide() -> None:
    with pytest.raises(ErreurPayloadInvalide):
        traduire({"taches": "pas une liste", "ressources": [], "contraintes": []})


def test_traduire_tache_sans_compatibilite_rejetee_par_le_garde_fou_dsl() -> None:
    payload = _payload_de_base(
        contraintes=[{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}]
    )
    with pytest.raises(ValidationError):
        traduire(payload)
