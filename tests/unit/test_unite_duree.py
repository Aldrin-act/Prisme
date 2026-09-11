from __future__ import annotations

from api.unite_duree import detecter_unite_duree
from dsl.schema import InstanceTRCO


def _instance(contraintes: list[dict]) -> InstanceTRCO:
    return InstanceTRCO.model_validate(
        {
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": contraintes,
            "objectifs": [{"type": "minimiser_makespan"}],
        }
    )


def test_sans_contrainte_de_duree_retombe_sur_jours() -> None:
    # `model_construct` contourne délibérément la validation d'`InstanceTRCO`
    # (qui impose ≥1 CompatibiliteRessourceTache par tâche, donc au moins une
    # valeur de durée en pratique) — seul moyen d'exercer ce repli défensif,
    # pour un appelant hypothétique qui construirait l'instance autrement.
    instance = InstanceTRCO.model_construct(taches=[], ressources=[], contraintes=[], objectifs=[])
    assert detecter_unite_duree(instance) == "jours"


def test_petites_durees_restent_en_jours() -> None:
    instance = _instance([{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 3}])
    assert detecter_unite_duree(instance) == "jours"


def test_duree_a_deux_semaines_bascule_en_semaines() -> None:
    instance = _instance(
        [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 14}]
    )
    assert detecter_unite_duree(instance) == "semaines"


def test_echeance_de_plusieurs_mois_bascule_en_mois() -> None:
    instance = _instance(
        [
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 5},
            {"type": "echeance", "tache": "T1", "echeance": 90},
        ]
    )
    assert detecter_unite_duree(instance) == "mois"


def test_retient_la_plus_grande_valeur_toutes_contraintes_confondues() -> None:
    """Une petite durée tâche-ressource à côté d'une échéance lointaine ne doit
    pas faire retomber le choix sur "jours" — c'est la plus grande valeur qui
    détermine la lisibilité de l'affichage, pas la première rencontrée."""
    instance = _instance(
        [
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 2},
            {"type": "echeance", "tache": "T1", "echeance": 21},
        ]
    )
    assert detecter_unite_duree(instance) == "semaines"
