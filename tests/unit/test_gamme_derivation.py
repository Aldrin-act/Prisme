"""Couche 1 (§6.1) : `adapters.gamme_derivation` est calcul pur, aucune E/S — voir sa docstring
pour la séquence de dérivation réutilisée (competence_derivation.py). L'échéance n'est plus
dérivée ici (voir `traiter_nouvelle_commande` — une commande pouvant combiner plusieurs gammes et
des tâches choisies directement, l'échéance se dérive une seule fois côté appelant,
`api/routes/ingestion.py::ajouter_commande`), donc pas testée dans ce fichier."""

from __future__ import annotations

import pytest

from adapters.competence_derivation import CompetenceSansDureeEstimee
from adapters.gamme_derivation import (
    ErreurExplosionGamme,
    GammeAvecQuantite,
    exploser_gamme,
    traiter_nouvelle_commande,
)
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

    ressources = [Ressource(id="R1", competences=["soudure"])]
    taches, contraintes, avertissements = exploser_gamme(
        "CMD1", "0", quantite=5, gamme=gamme, ressources=ressources, ids_taches_existantes=set()
    )

    assert len(taches) == 1
    assert taches[0].id == "CMD1_0_soudure"
    assert taches[0].produit == "Vanne V12"
    assert taches[0].quantite == 5
    assert contraintes == [CompetenceRequise(tache="CMD1_0_soudure", competence="soudure")]
    assert avertissements == []


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

    ressources = [Ressource(id="R1", competences=["soudure", "emballage", "sciage"])]
    _, contraintes, _ = exploser_gamme(
        "CMD1", "0", quantite=None, gamme=gamme, ressources=ressources, ids_taches_existantes=set()
    )

    precedences = [c for c in contraintes if isinstance(c, Precedence)]
    assert {(p.avant, p.apres) for p in precedences} == {
        ("CMD1_0_soudure", "CMD1_0_sciage"),
        ("CMD1_0_emballage", "CMD1_0_sciage"),
    }


def test_exploser_gamme_id_deja_present_refuse() -> None:
    gamme = GammeProduit(
        id="G1", client_id="C1", produit="P", nom=None, etapes=(EtapeGamme(id="etape", competences=("x",)),)
    )

    ressources = [Ressource(id="R1", competences=["x"])]
    with pytest.raises(ErreurExplosionGamme, match="existe déjà"):
        exploser_gamme(
            "CMD1",
            "0",
            quantite=None,
            gamme=gamme,
            ressources=ressources,
            ids_taches_existantes={"CMD1_0_etape"},
        )


def test_exploser_gamme_predecesseur_inconnu_refuse() -> None:
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(EtapeGamme(id="etape", competences=("x",), predecesseurs=("fantome",)),),
    )

    ressources = [Ressource(id="R1", competences=["x"])]
    with pytest.raises(ErreurExplosionGamme, match="prédécesseur inconnu"):
        exploser_gamme("CMD1", "0", quantite=None, gamme=gamme, ressources=ressources, ids_taches_existantes=set())


def test_exploser_gamme_deux_gammes_meme_id_etape_ne_collisionnent_pas() -> None:
    """Le préfixe de gamme (index dans la liste de la requête) évite toute collision entre deux
    gammes différentes qui réutiliseraient le même id d'étape — nouveau comportement, la commande
    pouvant désormais référencer plusieurs gammes (voir `traiter_nouvelle_commande`)."""
    gamme = GammeProduit(
        id="G1", client_id="C1", produit="P", nom=None, etapes=(EtapeGamme(id="controle", competences=("x",)),)
    )

    ressources = [Ressource(id="R1", competences=["x"])]
    taches_0, _, _ = exploser_gamme(
        "CMD1", "0", quantite=None, gamme=gamme, ressources=ressources, ids_taches_existantes=set()
    )
    taches_1, _, _ = exploser_gamme(
        "CMD1", "1", quantite=None, gamme=gamme, ressources=ressources, ids_taches_existantes=set()
    )

    assert taches_0[0].id == "CMD1_0_controle"
    assert taches_1[0].id == "CMD1_1_controle"


def test_traiter_nouvelle_commande_derive_compatibilite_et_renvoie_les_ids_explodes() -> None:
    instance = _instance_vide()
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="Vanne V12",
        nom=None,
        etapes=(EtapeGamme(id="soudure", competences=("soudure",), duree_nominale=3),),
    )

    resultat = traiter_nouvelle_commande(instance, [GammeAvecQuantite(gamme, 2)], "CMD1")

    taches_ids = {t.id for t in resultat.instance.taches}
    assert taches_ids == {"EXISTANT", "CMD1_0_soudure"}
    assert resultat.taches_explodees == ("CMD1_0_soudure",)

    compat = [
        c
        for c in resultat.instance.contraintes
        if isinstance(c, CompatibiliteRessourceTache) and c.tache == "CMD1_0_soudure"
    ]
    assert compat == [CompatibiliteRessourceTache(tache="CMD1_0_soudure", ressource="R1", duree=3)]
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
        traiter_nouvelle_commande(instance, [GammeAvecQuantite(gamme, None)], "CMD1")


def test_traiter_nouvelle_commande_preserve_le_contenu_existant_de_l_instance() -> None:
    instance = _instance_vide()
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(EtapeGamme(id="soudure", competences=("soudure",), duree_nominale=1),),
    )

    resultat = traiter_nouvelle_commande(instance, [GammeAvecQuantite(gamme, None)], "CMD1")

    assert any(t.id == "EXISTANT" for t in resultat.instance.taches)
    assert resultat.instance.ressources == instance.ressources
    assert resultat.instance.objectifs == instance.objectifs


def test_traiter_nouvelle_commande_deux_gammes_fusionne_les_deux() -> None:
    """Une commande peut référencer plusieurs gammes (plusieurs produits) — les tâches et
    compatibilités des deux se retrouvent fusionnées dans l'instance résultante, sans collision
    même si les deux gammes partagent un id d'étape (ici "controle")."""
    instance = _instance_vide(ressources=[Ressource(id="R1", competences=["soudure", "peinture"])])
    gamme_a = GammeProduit(
        id="GA",
        client_id="C1",
        produit="Vanne V12",
        nom=None,
        etapes=(EtapeGamme(id="controle", competences=("soudure",), duree_nominale=2),),
    )
    gamme_b = GammeProduit(
        id="GB",
        client_id="C1",
        produit="Bride B7",
        nom=None,
        etapes=(EtapeGamme(id="controle", competences=("peinture",), duree_nominale=1),),
    )

    resultat = traiter_nouvelle_commande(
        instance, [GammeAvecQuantite(gamme_a, None), GammeAvecQuantite(gamme_b, None)], "CMD1"
    )

    assert resultat.taches_explodees == ("CMD1_0_controle", "CMD1_1_controle")
    taches_ids = {t.id for t in resultat.instance.taches}
    assert taches_ids == {"EXISTANT", "CMD1_0_controle", "CMD1_1_controle"}


def test_exploser_gamme_etape_non_couverte_par_les_ressources_est_ignoree() -> None:
    """Une étape dont aucune ressource de l'atelier ne couvre les compétences requises est
    ignorée (pas explosée), avec un avertissement — pas d'échec de toute l'explosion (§FC4)."""
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(
            EtapeGamme(id="soudure", competences=("soudure",)),
            EtapeGamme(id="peinture", competences=("peinture",)),
        ),
    )
    ressources = [Ressource(id="R1", competences=["soudure"])]

    taches, contraintes, avertissements = exploser_gamme(
        "CMD1", "0", quantite=None, gamme=gamme, ressources=ressources, ids_taches_existantes=set()
    )

    assert [t.id for t in taches] == ["CMD1_0_soudure"]
    assert contraintes == [CompetenceRequise(tache="CMD1_0_soudure", competence="soudure")]
    assert len(avertissements) == 1
    assert "peinture" in avertissements[0]


def test_exploser_gamme_precedence_vers_etape_ignoree_est_omise() -> None:
    """Une précédence référençant une étape non réalisable dans cet atelier est omise — l'étape
    suivante n'attend plus une étape qui n'aura jamais lieu ici."""
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(
            EtapeGamme(id="peinture", competences=("peinture",)),
            EtapeGamme(id="emballage", competences=("emballage",), predecesseurs=("peinture",)),
        ),
    )
    ressources = [Ressource(id="R1", competences=["emballage"])]

    taches, contraintes, avertissements = exploser_gamme(
        "CMD1", "0", quantite=None, gamme=gamme, ressources=ressources, ids_taches_existantes=set()
    )

    assert [t.id for t in taches] == ["CMD1_0_emballage"]
    assert not any(isinstance(c, Precedence) for c in contraintes)
    assert len(avertissements) == 1


def test_exploser_gamme_aucune_etape_realisable_leve_erreur() -> None:
    """Si aucune étape de la gamme n'est réalisable dans cet atelier, l'explosion échoue
    explicitement plutôt que de produire silencieusement une commande sans aucune tâche."""
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="P",
        nom=None,
        etapes=(EtapeGamme(id="peinture", competences=("peinture",)),),
    )
    ressources = [Ressource(id="R1", competences=["soudure"])]

    with pytest.raises(ErreurExplosionGamme, match="aucune étape"):
        exploser_gamme("CMD1", "0", quantite=None, gamme=gamme, ressources=ressources, ids_taches_existantes=set())


def test_traiter_nouvelle_commande_etape_non_couverte_ignoree_avec_avertissement() -> None:
    """Intégration bout en bout : une gamme avec une étape non couverte par les ressources de
    l'instance cible explose quand même (l'étape couverte), avec un avertissement signalant
    l'étape ignorée — la commande n'échoue pas."""
    instance = _instance_vide()
    gamme = GammeProduit(
        id="G1",
        client_id="C1",
        produit="Vanne V12",
        nom=None,
        etapes=(
            EtapeGamme(id="soudure", competences=("soudure",), duree_nominale=3),
            EtapeGamme(id="peinture", competences=("peinture",), duree_nominale=1),
        ),
    )

    resultat = traiter_nouvelle_commande(instance, [GammeAvecQuantite(gamme, None)], "CMD1")

    assert resultat.taches_explodees == ("CMD1_0_soudure",)
    assert len(resultat.avertissements) == 1
    assert "peinture" in resultat.avertissements[0]
