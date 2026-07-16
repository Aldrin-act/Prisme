"""Couche 1 (§6.1) : l'adaptateur GreenSIG est du code écrit à la main,
déterministe — pure traduction, aucune dépendance externe (ni OR-Tools ni
Docker)."""

from __future__ import annotations

from adapters.greensig import EquipeGreenSIG, PayloadGreenSIG, TacheGreenSIG, TypeTacheGreenSIG, traduire
from dsl.schema import CompatibiliteMachineTache, InstanceTRCO, Precedence


def test_traduction_produit_les_bonnes_taches_et_ressources() -> None:
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=2.5, equipes_ids=[100]),
            TacheGreenSIG(id=2, id_type_tache_id=11, charge_estimee_heures=1.0, equipes_ids=[100, 200]),
        ],
        equipes=[
            EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True),
            EquipeGreenSIG(id=200, nom_equipe="Equipe Sud", actif=True),
        ],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte"), TypeTacheGreenSIG(id=11, nom_tache="Taille")],
    )

    instance = traduire(payload)

    assert isinstance(instance, InstanceTRCO)
    assert {t.id for t in instance.taches} == {"T1", "T2"}
    assert {r.id for r in instance.ressources} == {"E100", "E200"}


def test_duree_convertie_en_minutes_depuis_la_charge_estimee() -> None:
    payload = PayloadGreenSIG(
        taches=[TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=2.5, equipes_ids=[100])],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteMachineTache)]
    assert len(compatibilites) == 1
    assert compatibilites[0] == CompatibiliteMachineTache(tache="T1", ressource="E100", duree=150)


def test_duree_par_defaut_si_charge_estimee_absente() -> None:
    payload = PayloadGreenSIG(
        taches=[TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=None, equipes_ids=[100])],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteMachineTache)]
    assert compatibilites[0].duree == 30


def test_meme_duree_appliquee_a_chaque_equipe_compatible() -> None:
    payload = PayloadGreenSIG(
        taches=[TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=1.0, equipes_ids=[100, 200])],
        equipes=[
            EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True),
            EquipeGreenSIG(id=200, nom_equipe="Equipe Sud", actif=True),
        ],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    durees = {c.ressource: c.duree for c in instance.contraintes if isinstance(c, CompatibiliteMachineTache)}
    assert durees == {"E100": 60, "E200": 60}


def test_taches_supprimees_exclues() -> None:
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=1.0, equipes_ids=[100]),
            TacheGreenSIG(
                id=2, id_type_tache_id=10, charge_estimee_heures=1.0, equipes_ids=[100], deleted_at="2026-01-01"
            ),
        ],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    assert {t.id for t in instance.taches} == {"T1"}


def test_equipe_inactive_exclue_et_compatibilite_ignoree() -> None:
    payload = PayloadGreenSIG(
        taches=[TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=1.0, equipes_ids=[100, 200])],
        equipes=[
            EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True),
            EquipeGreenSIG(id=200, nom_equipe="Equipe Sud", actif=False),
        ],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    assert {r.id for r in instance.ressources} == {"E100"}
    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteMachineTache)]
    assert {c.ressource for c in compatibilites} == {"E100"}


def test_traduction_ne_produit_jamais_de_precedence() -> None:
    """GreenSIG n'a pas de colonne de précédence entre tâches (voir
    adapters/greensig/mapping/regles.md, limite 1) — l'adaptateur ne doit
    jamais en inventer une."""
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=1.0, equipes_ids=[100]),
            TacheGreenSIG(id=2, id_type_tache_id=10, charge_estimee_heures=1.0, equipes_ids=[100]),
        ],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    assert not [c for c in instance.contraintes if isinstance(c, Precedence)]


def test_instance_produite_est_valide_par_construction() -> None:
    """La traduction doit toujours produire un InstanceTRCO qui passe ses
    propres garde-fous (§6.7) — sinon l'adaptateur laisserait passer des
    données incohérentes vers le solveur."""
    payload = PayloadGreenSIG(
        taches=[TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=1.0, equipes_ids=[100])],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    # Ne lève pas : model_validate revalide un InstanceTRCO déjà construit.
    InstanceTRCO.model_validate(instance.model_dump())
