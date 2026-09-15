"""Couche 1 (§6.1) : `adapters/json_import/traducteur.py` — la version JSON
(un seul payload structuré) de la compatibilité dérivée par compétence,
miroir de `adapters/csv_import/` (voir `tests/unit/test_csv_import_adapter.py`).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adapters.json_import import ErreurPayloadInvalide
from adapters.json_import import traduire as _traduire_resultat
from dsl.schema import InstanceTRCO


def traduire(*args: object, **kwargs: object) -> InstanceTRCO:
    """`traduire()` renvoie désormais un `ResultatTraduction` (instance +
    avertissements, §FC4) — les tests ci-dessous ne portent que sur
    l'instance produite ; le comportement des avertissements/de
    `estimateur_duree` est couvert séparément plus bas."""
    return _traduire_resultat(*args, **kwargs).instance  # type: ignore[arg-type]


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


def test_traduire_derive_une_echeance_par_tache_depuis_une_commande() -> None:
    payload = _payload_de_base(
        commandes=[{"id": "CMD1", "taches": ["T1", "T2"], "client": "Client A", "date_limite": 20}]
    )

    instance = traduire(payload)

    echeances = [c for c in instance.contraintes if c.type == "echeance"]
    assert {(e.tache, e.echeance) for e in echeances} == {("T1", 20), ("T2", 20)}


def test_traduire_echeance_explicite_de_la_commande_prevaut_sur_la_derivation() -> None:
    payload = _payload_de_base(
        contraintes=[
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 15},
            {"type": "echeance", "tache": "T1", "echeance": 5},
        ],
        commandes=[{"id": "CMD1", "taches": ["T1", "T2"], "date_limite": 20}],
    )

    instance = traduire(payload)

    echeances = {c.tache: c.echeance for c in instance.contraintes if c.type == "echeance"}
    assert echeances == {"T1": 5, "T2": 20}  # T1 garde son échéance explicite, jamais 20


def test_traduire_sans_commandes_ne_derive_aucune_echeance() -> None:
    instance = traduire(_payload_de_base())

    assert not [c for c in instance.contraintes if c.type == "echeance"]


def test_traduire_commande_sans_taches_rejetee() -> None:
    payload = _payload_de_base(commandes=[{"id": "CMD1", "taches": []}])
    with pytest.raises(ErreurPayloadInvalide):
        traduire(payload)


# --- Matières (DeclarationMateriau/ConsommationMatiere, deux types de contraintes de plus) ---


def test_traduire_sans_declaration_materiau_ne_produit_aucune_contrainte_matiere() -> None:
    instance = traduire(_payload_de_base())
    assert not [c for c in instance.contraintes if c.type in ("declaration_materiau", "consommation_matiere")]


def test_traduire_ingere_declaration_materiau_et_consommation_matiere() -> None:
    payload = _payload_de_base(
        contraintes=[
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 15},
            {"type": "declaration_materiau", "materiau": "M1", "stock_initial": 100, "unite": "kg"},
            {"type": "consommation_matiere", "tache": "T1", "materiau": "M1", "quantite": 5},
        ],
    )

    instance = traduire(payload)

    declarations = [c for c in instance.contraintes if c.type == "declaration_materiau"]
    assert len(declarations) == 1
    assert declarations[0].stock_initial == 100
    consommations = [c for c in instance.contraintes if c.type == "consommation_matiere"]
    assert len(consommations) == 1
    assert consommations[0].materiau == "M1"
    assert consommations[0].quantite == 5


def test_traduire_consommation_matiere_vers_materiau_inconnu_rejetee() -> None:
    payload = _payload_de_base(
        contraintes=[
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 15},
            {"type": "consommation_matiere", "tache": "T1", "materiau": "M99", "quantite": 5},
        ],
    )
    with pytest.raises(ValidationError, match="consommation de matière référence un matériau inconnu"):
        traduire(payload)


# --- ResultatTraduction / estimateur_duree (§FC4, décision humaine préservée) ---
#
# Même faux estimateur duck-typé que `tests/unit/test_csv_import_adapter.py` —
# voir ce fichier pour la justification (ne pas exiger l'extra optionnel
# `estimation` dans cette suite).


class _EstimationFausse:
    def __init__(self, duree_estimee_jours: int, confiance: float) -> None:
        self.duree_estimee_jours = duree_estimee_jours
        self.confiance = confiance


class _EstimateurFaux:
    def __init__(self, duree: int, confiance: float = 0.9) -> None:
        self._duree = duree
        self._confiance = confiance

    def estimer(self, tache: object, ressource: object) -> _EstimationFausse:
        return _EstimationFausse(self._duree, self._confiance)


def test_traduire_par_defaut_renvoie_un_resultat_sans_avertissement() -> None:
    resultat = _traduire_resultat(_payload_de_base())
    assert resultat.avertissements == ()


def test_estimateur_duree_comble_une_duree_manquante_et_previent() -> None:
    payload = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1", "competences": ["decoupe"]}],
        "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
    }

    resultat = _traduire_resultat(payload, estimateur_duree=_EstimateurFaux(17))

    compatibilites = [c for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 17)]
    assert len(resultat.avertissements) == 1
    assert "T1" in resultat.avertissements[0]


def test_duree_declaree_l_emporte_toujours_sur_l_estimateur() -> None:
    payload = {
        "taches": [{"id": "T1", "duree_estimee_jours": 25}],
        "ressources": [{"id": "R1", "competences": ["decoupe"]}],
        "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
    }

    resultat = _traduire_resultat(payload, estimateur_duree=_EstimateurFaux(99))

    compatibilites = [c for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 25)]
    assert resultat.avertissements == ()


def test_sans_estimateur_duree_manquante_leve_toujours_erreur() -> None:
    payload = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1", "competences": ["decoupe"]}],
        "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
    }

    with pytest.raises(ErreurPayloadInvalide, match="durée estimée manquante"):
        _traduire_resultat(payload)
