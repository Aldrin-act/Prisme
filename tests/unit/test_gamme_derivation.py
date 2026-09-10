"""Couche 1 (§6.1) : `adapters.gamme_derivation` est calcul pur, aucune E/S — voir sa docstring
pour la séquence de dérivation réutilisée (competence_derivation.py, commande_derivation.py)."""

from __future__ import annotations

import pytest

from adapters.competence_derivation import CompetenceSansDureeEstimee
from adapters.gamme_derivation import ErreurExplosionGamme, exploser_gamme, traiter_nouvelle_commande
from api.etat import EtapeGamme, GammeProduit
from dsl.schema import (
    CompatibiliteRessourceTache,
    CompetenceRequise,
    InstanceTRCO,
    MinimiserMakespan,
    Precedence,
    Ressource,
    Tache,
)


def _instance_vide(ressources: list[Ressource] | None = None) -> InstanceTRCO:
    return InstanceTRCO(
        taches=[Tache(id="EXISTANT")],
        ressources=ressources or [Ressource(id="R1", competences=["soudure"])],
        contraintes=[CompatibiliteRessourceTache(tache="EXISTANT", ressource="R1", duree=1)],
        objectifs=[MinimiserMakespan()],
    )


def test_exploser_gamme_une_tache_par_etape_avec_produit_et_competence() -> None:
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="Vanne V12",
        nom=None,
        etapes=(EtapeGamme(id="soudure", competences=("soudure",)),),
    )

    taches, contraintes = exploser_gamme("CMD1", quantite=5, gamme=gamme, ids_taches_existantes=set())

    assert len(taches) == 1
    assert taches[0].id == "CMD1_soudure"
    assert taches[0].produit == "Vanne V12"
    assert taches[0].quantite == 5
    assert contraintes == [CompetenceRequise(tache="CMD1_soudure", competence="soudure")]


def test_exploser_gamme_plusieurs_predecesseurs_exprime_une_fusion() -> None:
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(
            EtapeGamme(id="soudure", competences=("soudure",)),
            EtapeGamme(id="emballage", competences=("emballage",)),
            EtapeGamme(id="sciage", competences=("sciage",), predecesseurs=("soudure", "emballage")),
        ),
    )

    _, contraintes = exploser_gamme("CMD1", quantite=None, gamme=gamme, ids_taches_existantes=set())

    precedences = [c for c in contraintes if isinstance(c, Precedence)]
    assert {(p.avant, p.apres) for p in precedences} == {
        ("CMD1_soudure", "CMD1_sciage"),
        ("CMD1_emballage", "CMD1_sciage"),
    }


def test_exploser_gamme_id_deja_present_refuse() -> None:
    gamme = GammeProduit(
        id="G1", client_id="C1", produit="P", nom=None, etapes=(EtapeGamme(id="etape", competences=("x",)),)
    )

    with pytest.raises(ErreurExplosionGamme, match="existe déjà"):
        exploser_gamme("CMD1", quantite=None, gamme=gamme, ids_taches_existantes={"CMD1_etape"})


def test_exploser_gamme_predecesseur_inconnu_refuse() -> None:
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(EtapeGamme(id="etape", competences=("x",), predecesseurs=("fantome",)),),
    )

    with pytest.raises(ErreurExplosionGamme, match="prédécesseur inconnu"):
        exploser_gamme("CMD1", quantite=None, gamme=gamme, ids_taches_existantes=set())


def test_traiter_nouvelle_commande_derive_compatibilite_et_echeance() -> None:
    instance = _instance_vide()
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="Vanne V12",
        nom=None,
        etapes=(EtapeGamme(id="soudure", competences=("soudure",), duree_nominale=3),),
    )

    resultat = traiter_nouvelle_commande(instance, gamme, "CMD1", quantite=2, date_limite=10)

    taches_ids = {t.id for t in resultat.instance.taches}
    assert taches_ids == {"EXISTANT", "CMD1_soudure"}

    compat = [
        c
        for c in resultat.instance.contraintes
        if isinstance(c, CompatibiliteRessourceTache) and c.tache == "CMD1_soudure"
    ]
    assert compat == [CompatibiliteRessourceTache(tache="CMD1_soudure", ressource="R1", duree=3)]

    echeances = [c for c in resultat.instance.contraintes if c.type == "echeance" and c.tache == "CMD1_soudure"]
    assert len(echeances) == 1
    assert echeances[0].echeance == 10
    assert resultat.avertissements == ()


def test_traiter_nouvelle_commande_sans_duree_ni_estimateur_leve_erreur_explicite() -> None:
    instance = _instance_vide()
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(EtapeGamme(id="soudure", competences=("soudure",)),),
    )

    with pytest.raises(CompetenceSansDureeEstimee):
        traiter_nouvelle_commande(instance, gamme, "CMD1", quantite=None, date_limite=None)


def test_traiter_nouvelle_commande_preserve_le_contenu_existant_de_l_instance() -> None:
    instance = _instance_vide()
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(EtapeGamme(id="soudure", competences=("soudure",), duree_nominale=1),),
    )

    resultat = traiter_nouvelle_commande(instance, gamme, "CMD1", quantite=None, date_limite=None)

    assert any(t.id == "EXISTANT" for t in resultat.instance.taches)
    assert resultat.instance.ressources == instance.ressources
    assert resultat.instance.objectifs == instance.objectifs
