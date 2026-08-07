"""Couche 1 (§6.1) : le schéma T-R-C-O est du code écrit à la main,
déterministe — on teste ici le critère de validation de l'Étape 1 (§6.7) :
un payload bien formé est chargé tel quel, un payload mal formé est rejeté
par Pydantic avec un diagnostic exploitable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dsl.schema import InstanceTRCO
from dsl.validation import charger_instance

EXAMPLES = Path(__file__).resolve().parents[2] / "dsl" / "examples"
VALID_EXAMPLES = sorted((EXAMPLES / "valid").glob("*.json"))
INVALID_EXAMPLES = sorted((EXAMPLES / "invalid").glob("*.json"))


@pytest.mark.parametrize("chemin", VALID_EXAMPLES, ids=lambda p: p.stem)
def test_exemple_valide_est_accepte(chemin: Path) -> None:
    instance = charger_instance(chemin.read_text(encoding="utf-8"))
    assert isinstance(instance, InstanceTRCO)


@pytest.mark.parametrize("chemin", INVALID_EXAMPLES, ids=lambda p: p.stem)
def test_exemple_invalide_est_rejete(chemin: Path) -> None:
    with pytest.raises(ValidationError):
        charger_instance(chemin.read_text(encoding="utf-8"))


def _instance_minimale(**overrides: object) -> dict:
    base = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    base.update(overrides)
    return base


def test_duree_nulle_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 0}]
    )
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_identifiant_hors_alphabet_rejete() -> None:
    payload = _instance_minimale(taches=[{"id": "T 1"}])
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_precedence_autoreference_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "precedence", "avant": "T1", "apres": "T1"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
        ]
    )
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_tache_sans_compatibilite_est_rejetee() -> None:
    payload = _instance_minimale(contraintes=[])
    with pytest.raises(ValidationError, match="sans aucune contrainte de compatibilité"):
        charger_instance(payload)


def test_champ_inconnu_rejete() -> None:
    payload = _instance_minimale(champ_fantome="valeur")
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_sans_aucune_tache_rejete() -> None:
    payload = _instance_minimale(taches=[])
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_sans_aucune_ressource_rejete() -> None:
    payload = _instance_minimale(ressources=[])
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_sans_aucun_objectif_rejete() -> None:
    payload = _instance_minimale(objectifs=[])
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_identifiants_de_taches_dupliques_rejetes() -> None:
    payload = _instance_minimale(taches=[{"id": "T1"}, {"id": "T1"}])
    with pytest.raises(ValidationError, match="dupliqués"):
        charger_instance(payload)


def test_identifiants_de_ressources_dupliques_rejetes() -> None:
    payload = _instance_minimale(ressources=[{"id": "R1"}, {"id": "R1"}])
    with pytest.raises(ValidationError, match="dupliqués"):
        charger_instance(payload)


def test_compatibilite_vers_tache_inconnue_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[{"type": "compatibilite_ressource_tache", "tache": "T99", "ressource": "R1", "duree": 10}]
    )
    with pytest.raises(ValidationError, match="tâche inconnue"):
        charger_instance(payload)


def test_priorite_valide_acceptee() -> None:
    payload = _instance_minimale(taches=[{"id": "T1", "priorite": 3}])
    instance = charger_instance(payload)
    assert instance.taches[0].priorite == 3


def test_priorite_absente_par_defaut_none() -> None:
    instance = charger_instance(_instance_minimale())
    assert instance.taches[0].priorite is None


@pytest.mark.parametrize("priorite", [0, 6])
def test_priorite_hors_bornes_rejetee(priorite: int) -> None:
    payload = _instance_minimale(taches=[{"id": "T1", "priorite": priorite}])
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_competences_absentes_par_defaut_liste_vide() -> None:
    instance = charger_instance(_instance_minimale())
    assert instance.ressources[0].competences == []


def test_echeance_valide_acceptee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "echeance", "tache": "T1", "echeance": 100},
        ]
    )
    instance = charger_instance(payload)
    assert len(instance.contraintes) == 2


def test_echeance_vers_tache_inconnue_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "echeance", "tache": "T99", "echeance": 100},
        ]
    )
    with pytest.raises(ValidationError, match="échéance référence une tâche inconnue"):
        charger_instance(payload)


def test_competence_requise_valide_acceptee() -> None:
    payload = _instance_minimale(
        ressources=[{"id": "R1", "competences": ["soudure"]}],
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "competence_requise", "tache": "T1", "competence": "soudure"},
        ],
    )
    instance = charger_instance(payload)
    assert instance.ressources[0].competences == ["soudure"]


def test_competence_requise_vers_tache_inconnue_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "competence_requise", "tache": "T99", "competence": "soudure"},
        ]
    )
    with pytest.raises(ValidationError, match="compétence requise référence une tâche inconnue"):
        charger_instance(payload)


def test_compatibilite_sans_competence_requise_rejetee() -> None:
    """Une ressource sans la compétence exigée ne peut pas être déclarée compatible —
    même si elle est par ailleurs listée dans `ressources` (§ garde-fou structurel)."""
    payload = _instance_minimale(
        ressources=[{"id": "R1", "competences": []}],
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "competence_requise", "tache": "T1", "competence": "soudure"},
        ],
    )
    with pytest.raises(ValidationError, match="sans les compétences requises"):
        charger_instance(payload)


def test_statut_valide_accepte() -> None:
    payload = _instance_minimale(taches=[{"id": "T1", "statut": "en_cours"}])
    instance = charger_instance(payload)
    assert instance.taches[0].statut == "en_cours"


def test_statut_absent_par_defaut_none() -> None:
    instance = charger_instance(_instance_minimale())
    assert instance.taches[0].statut is None


def test_statut_hors_enum_rejete() -> None:
    payload = _instance_minimale(taches=[{"id": "T1", "statut": "annule"}])
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_type_ressource_valide_accepte() -> None:
    payload = _instance_minimale(ressources=[{"id": "R1", "type": "machine"}])
    instance = charger_instance(payload)
    assert instance.ressources[0].type == "machine"


def test_type_ressource_absent_par_defaut_none() -> None:
    instance = charger_instance(_instance_minimale())
    assert instance.ressources[0].type is None


def test_type_ressource_hors_enum_rejete() -> None:
    payload = _instance_minimale(ressources=[{"id": "R1", "type": "robot"}])
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_capacite_valide_acceptee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "capacite", "ressource": "R1", "capacite": 3},
        ]
    )
    instance = charger_instance(payload)
    assert len(instance.contraintes) == 2


def test_capacite_nulle_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "capacite", "ressource": "R1", "capacite": 0},
        ]
    )
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_capacite_vers_ressource_inconnue_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "capacite", "ressource": "R99", "capacite": 2},
        ]
    )
    with pytest.raises(ValidationError, match="capacité référence une ressource inconnue"):
        charger_instance(payload)


def test_incompatibilite_valide_acceptee() -> None:
    payload = _instance_minimale(
        taches=[{"id": "T1"}, {"id": "T2"}],
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 10},
            {"type": "incompatibilite", "tache": "T1", "tache_incompatible": "T2"},
        ],
    )
    instance = charger_instance(payload)
    assert len(instance.contraintes) == 3


def test_incompatibilite_autoreference_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "incompatibilite", "tache": "T1", "tache_incompatible": "T1"},
        ]
    )
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_incompatibilite_vers_tache_inconnue_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "incompatibilite", "tache": "T1", "tache_incompatible": "T99"},
        ]
    )
    with pytest.raises(ValidationError, match="incompatibilité référence une tâche inconnue"):
        charger_instance(payload)


def test_disponibilite_ressource_valide_acceptee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "disponibilite_ressource", "ressource": "R1", "jours_indisponibles": [2, 3]},
        ]
    )
    instance = charger_instance(payload)
    assert len(instance.contraintes) == 2


def test_disponibilite_ressource_liste_vide_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "disponibilite_ressource", "ressource": "R1", "jours_indisponibles": []},
        ]
    )
    with pytest.raises(ValidationError):
        charger_instance(payload)


def test_disponibilite_ressource_vers_ressource_inconnue_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "disponibilite_ressource", "ressource": "R99", "jours_indisponibles": [1]},
        ]
    )
    with pytest.raises(ValidationError, match="disponibilité référence une ressource inconnue"):
        charger_instance(payload)


def test_taille_lot_valide_acceptee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "taille_lot", "tache": "T1", "lot_min": 50, "lot_max": 1000},
        ]
    )
    instance = charger_instance(payload)
    assert len(instance.contraintes) == 2


def test_taille_lot_min_superieur_max_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "taille_lot", "tache": "T1", "lot_min": 1000, "lot_max": 50},
        ]
    )
    with pytest.raises(ValidationError, match="lot_min doit être inférieur ou égal à lot_max"):
        charger_instance(payload)


def test_taille_lot_vers_tache_inconnue_rejetee() -> None:
    payload = _instance_minimale(
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "taille_lot", "tache": "T99", "lot_min": 50, "lot_max": 1000},
        ]
    )
    with pytest.raises(ValidationError, match="taille de lot référence une tâche inconnue"):
        charger_instance(payload)
