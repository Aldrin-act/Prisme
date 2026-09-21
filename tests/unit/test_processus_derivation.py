"""Couche 1 (§6.1) : éclatement du processus d'un atelier en tâches DSL
(`adapters/processus_derivation.py`) — fonction pure, aucun service externe."""

from __future__ import annotations

import pytest

from adapters.processus_derivation import ErreurProcessus, eclater_processus, valider_processus
from api.etat import EtapeProcessus
from dsl.schema import (
    CompatibiliteRessourceTache,
    CompetenceRequise,
    InstanceTRCO,
    Precedence,
)


def _atelier(**surcharges) -> InstanceTRCO:
    """Deux régleurs : l'un sait tourner et fraiser, l'autre seulement tourner. Une tâche
    d'origine, avec sa propre compétence requise et sa compatibilité explicite."""
    donnees = {
        "taches": [{"id": "EXISTANTE"}],
        "ressources": [
            {"id": "NADIA", "competences": ["TOUR", "FRAISE"]},
            {"id": "JULIEN", "competences": ["TOUR"]},
        ],
        "contraintes": [
            {"type": "competence_requise", "tache": "EXISTANTE", "competence": "TOUR"},
            {"type": "compatibilite_ressource_tache", "tache": "EXISTANTE", "ressource": "JULIEN", "duree": 4},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
        **surcharges,
    }
    return InstanceTRCO.model_validate(donnees)


TOURNAGE = EtapeProcessus(id="TOURNAGE", nom="Tournage", competences=("TOUR",), duree_par_piece=2)
FRAISAGE = EtapeProcessus(
    id="FRAISAGE", nom="Fraisage", competences=("FRAISE",), duree_par_piece=1, predecesseurs=("TOURNAGE",)
)


def _par_type(instance: InstanceTRCO, type_contrainte: type) -> list:
    return [c for c in instance.contraintes if isinstance(c, type_contrainte)]


# --- validation ---------------------------------------------------------------------------------


def test_processus_valide_accepte() -> None:
    valider_processus((TOURNAGE, FRAISAGE))


@pytest.mark.parametrize(
    ("etapes", "motif"),
    [
        ((), "au moins une étape"),
        ((TOURNAGE, TOURNAGE), "en double"),
        ((EtapeProcessus(id="a b", competences=("TOUR",), duree_par_piece=1),), "invalide"),
        ((EtapeProcessus(id="A", competences=(), duree_par_piece=1),), "au moins une compétence"),
        ((EtapeProcessus(id="A", competences=("TOUR",), duree_par_piece=0),), "durée par pièce"),
        ((EtapeProcessus(id="A", competences=("TOUR",), duree_par_piece=1, predecesseurs=("Z",)),), "inconnues"),
        ((EtapeProcessus(id="A", competences=("TOUR",), duree_par_piece=1, predecesseurs=("A",)),), "elle-même"),
        (
            (
                EtapeProcessus(id="A", competences=("TOUR",), duree_par_piece=1, predecesseurs=("B",)),
                EtapeProcessus(id="B", competences=("TOUR",), duree_par_piece=1, predecesseurs=("A",)),
            ),
            "cycle",
        ),
    ],
)
def test_processus_invalide_refuse(etapes: tuple[EtapeProcessus, ...], motif: str) -> None:
    with pytest.raises(ErreurProcessus, match=motif):
        valider_processus(etapes)


# --- éclatement ---------------------------------------------------------------------------------


def test_eclatement_cree_une_copie_des_etapes_pour_la_commande() -> None:
    resultat = eclater_processus(_atelier(), (TOURNAGE, FRAISAGE), "cmd-1", quantite=1)

    assert resultat.taches_creees == ("cmd-1_TOURNAGE", "cmd-1_FRAISAGE")
    nouvelles = {t.id: t for t in resultat.instance.taches if t.id.startswith("cmd-1_")}
    assert nouvelles["cmd-1_TOURNAGE"].nom == "Tournage"
    assert Precedence(avant="cmd-1_TOURNAGE", apres="cmd-1_FRAISAGE") in resultat.instance.contraintes
    assert CompetenceRequise(tache="cmd-1_FRAISAGE", competence="FRAISE") in resultat.instance.contraintes
    assert resultat.avertissements == ()


def test_duree_multipliee_par_la_quantite() -> None:
    """5 pièces à 2 unités de tournage par pièce : 10 unités planifiées, sur chaque ressource
    capable de tourner."""
    resultat = eclater_processus(_atelier(), (TOURNAGE, FRAISAGE), "cmd-1", quantite=5)

    durees = {
        (c.tache, c.ressource): c.duree
        for c in _par_type(resultat.instance, CompatibiliteRessourceTache)
        if c.tache.startswith("cmd-1_")
    }
    assert durees == {
        ("cmd-1_TOURNAGE", "NADIA"): 10,
        ("cmd-1_TOURNAGE", "JULIEN"): 10,
        ("cmd-1_FRAISAGE", "NADIA"): 5,
    }
    assert all(t.quantite == 5 for t in resultat.instance.taches if t.id.startswith("cmd-1_"))


def test_deux_commandes_ont_chacune_leurs_taches() -> None:
    premiere = eclater_processus(_atelier(), (TOURNAGE, FRAISAGE), "cmd-1", quantite=1)
    seconde = eclater_processus(premiere.instance, (TOURNAGE, FRAISAGE), "cmd-2", quantite=1)

    ids = {t.id for t in seconde.instance.taches}
    assert {"cmd-1_TOURNAGE", "cmd-1_FRAISAGE", "cmd-2_TOURNAGE", "cmd-2_FRAISAGE"} <= ids


def test_etape_irrealisable_ignoree_avec_avertissement_et_ordre_conserve() -> None:
    """A → B → C avec B que personne ne sait faire : B est ignorée, signalée, et C attend
    quand même A — sauter l'étape du milieu ne doit pas faire perdre l'ordre en amont."""
    etapes = (
        EtapeProcessus(id="A", competences=("TOUR",), duree_par_piece=1),
        EtapeProcessus(id="B", nom="Peinture", competences=("PEINTURE",), duree_par_piece=1, predecesseurs=("A",)),
        EtapeProcessus(id="C", competences=("FRAISE",), duree_par_piece=1, predecesseurs=("B",)),
    )

    resultat = eclater_processus(_atelier(), etapes, "cmd-1", quantite=1)

    assert resultat.taches_creees == ("cmd-1_A", "cmd-1_C")
    assert Precedence(avant="cmd-1_A", apres="cmd-1_C") in resultat.instance.contraintes
    assert len(resultat.avertissements) == 1
    assert "Peinture" in resultat.avertissements[0]


def test_aucune_etape_realisable_refuse() -> None:
    etapes = (EtapeProcessus(id="A", competences=("SOUDURE",), duree_par_piece=1),)

    with pytest.raises(ErreurProcessus, match="aucune étape"):
        eclater_processus(_atelier(), etapes, "cmd-1", quantite=1)


def test_taches_existantes_a_competence_requise_ne_bloquent_pas() -> None:
    """Régression : l'ancien éclatement (gammes) passait toutes les contraintes de l'atelier à la
    dérivation des compatibilités, qui exige une durée pour chaque tâche à compétence requise —
    un atelier dont les tâches d'origine déclarent des compétences faisait donc tout échouer."""
    resultat = eclater_processus(_atelier(), (TOURNAGE,), "cmd-1", quantite=1)

    existantes = [c for c in _par_type(resultat.instance, CompatibiliteRessourceTache) if c.tache == "EXISTANTE"]
    assert existantes == [CompatibiliteRessourceTache(tache="EXISTANTE", ressource="JULIEN", duree=4)]


def test_champs_de_l_atelier_preserves() -> None:
    """Régression : l'ancien éclatement reconstruisait l'instance sans `jours_fermes`, remis
    silencieusement au samedi-dimanche par défaut."""
    atelier = _atelier(unite_temps="heures", jours_fermes=[0])

    resultat = eclater_processus(atelier, (TOURNAGE,), "cmd-1", quantite=1)

    assert resultat.instance.unite_temps == "heures"
    assert resultat.instance.jours_fermes == [0]


def test_quantite_nulle_refusee() -> None:
    with pytest.raises(ErreurProcessus, match="quantité"):
        eclater_processus(_atelier(), (TOURNAGE,), "cmd-1", quantite=0)


def test_collision_avec_une_tache_existante_refusee() -> None:
    compatible = {"type": "compatibilite_ressource_tache", "ressource": "JULIEN", "duree": 4}
    atelier = _atelier(
        taches=[{"id": "EXISTANTE"}, {"id": "cmd-1_TOURNAGE"}],
        contraintes=[{**compatible, "tache": "EXISTANTE"}, {**compatible, "tache": "cmd-1_TOURNAGE"}],
    )

    with pytest.raises(ErreurProcessus, match="existe déjà"):
        eclater_processus(atelier, (TOURNAGE,), "cmd-1", quantite=1)


def test_instance_d_origine_jamais_mutee() -> None:
    atelier = _atelier()
    avant = atelier.model_dump()

    eclater_processus(atelier, (TOURNAGE, FRAISAGE), "cmd-1", quantite=3)

    assert atelier.model_dump() == avant
