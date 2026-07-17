"""Couche 1 (§6.1) : l'adaptateur GreenSIG est du code écrit à la main,
déterministe — pure traduction, aucune dépendance externe (ni OR-Tools ni
Docker)."""

from __future__ import annotations

import pytest

from adapters.greensig import (
    EquipeGreenSIG,
    OperateurGreenSIG,
    PayloadGreenSIG,
    TacheGreenSIG,
    TypeTacheGreenSIG,
    traduire,
)
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, Precedence

# 2 = Binage dans `api_planification_typetache` (base GreenSIG réelle), mappé dans
# `adapters/greensig/mapping/competences_types_tache.py` vers les compétences 21/5.
_ID_TYPE_TACHE_MAPPE = 2
_ID_COMPETENCE_BINAGE = 21
_ID_COMPETENCE_BINAGE_VARIANTE = 5  # "Binage des sols" — doublon traité comme synonyme


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

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert len(compatibilites) == 1
    assert compatibilites[0] == CompatibiliteRessourceTache(tache="T1", ressource="E100", duree=150)


def test_duree_par_defaut_si_charge_estimee_absente() -> None:
    payload = PayloadGreenSIG(
        taches=[TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=None, equipes_ids=[100])],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert compatibilites[0].duree == 30


def test_duree_plancher_a_une_minute_si_charge_arrondit_a_zero() -> None:
    """Observé sur données réelles (`backup_20260503.sql`) : une
    charge_estimee_heures non nulle mais minuscule (quelques secondes)
    arrondit à 0 minute — `CompatibiliteRessourceTache.duree` exige `> 0`,
    donc jamais 0, mais pas non plus le défaut de 30 min (qui ne vaut que
    pour une charge réellement absente)."""
    payload = PayloadGreenSIG(
        taches=[TacheGreenSIG(id=1, id_type_tache_id=10, charge_estimee_heures=0.00064453125, equipes_ids=[100])],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=10, nom_tache="Tonte")],
    )

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert compatibilites[0].duree == 1


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

    durees = {c.ressource: c.duree for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)}
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
    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
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


def test_competence_debloque_compatibilite_absente_de_laffectation() -> None:
    """Type de tâche mappé (voir mapping/competences_types_tache.py) : une
    équipe compétente est compatible même sans avoir jamais été affectée à
    cette tâche par le passé — c'est tout le point de la compétence plutôt
    que l'historique (adapters/greensig/mapping/regles.md)."""
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(id=1, id_type_tache_id=_ID_TYPE_TACHE_MAPPE, charge_estimee_heures=1.0, equipes_ids=[])
        ],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=_ID_TYPE_TACHE_MAPPE, nom_tache="Binage")],
        operateurs=[OperateurGreenSIG(id=1, equipe_id=100, competences_ids=[_ID_COMPETENCE_BINAGE])],
    )

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert {c.ressource for c in compatibilites} == {"E100"}


def test_competence_manquante_exclut_malgre_affectation_historique() -> None:
    """Type mappé : une équipe historiquement affectée mais sans opérateur
    qualifié n'est PAS compatible — la compétence remplace l'affectation
    pour ce type, elle ne s'y ajoute pas."""
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(
                id=1, id_type_tache_id=_ID_TYPE_TACHE_MAPPE, charge_estimee_heures=1.0, equipes_ids=[100]
            )
        ],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=_ID_TYPE_TACHE_MAPPE, nom_tache="Binage")],
        operateurs=[OperateurGreenSIG(id=1, equipe_id=100, competences_ids=[])],
    )

    with pytest.raises(ValueError, match="sans aucune contrainte de compatibilité"):
        traduire(payload)


def test_variantes_doublon_dune_competence_comptent_comme_equivalentes() -> None:
    """21 ('Binage') et 5 ('Binage des sols') sont traités comme des
    synonymes d'une même compétence réelle (mapping/competences_types_tache.py) —
    posséder l'une ou l'autre suffit."""
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(id=1, id_type_tache_id=_ID_TYPE_TACHE_MAPPE, charge_estimee_heures=1.0, equipes_ids=[])
        ],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=_ID_TYPE_TACHE_MAPPE, nom_tache="Binage")],
        operateurs=[OperateurGreenSIG(id=1, equipe_id=100, competences_ids=[_ID_COMPETENCE_BINAGE_VARIANTE])],
    )

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert {c.ressource for c in compatibilites} == {"E100"}


def test_competence_ignoree_si_equipe_inactive() -> None:
    """Un opérateur qualifié dans une équipe désactivée ne rend pas cette
    équipe compatible — le filtre `actif` prime, comme pour l'affectation
    historique classique. Une seconde équipe active mais non qualifiée
    isole ce comportement (sinon `InstanceTRCO` rejetterait pour absence de
    toute ressource, pas spécifiquement pour la compétence ignorée)."""
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(id=1, id_type_tache_id=_ID_TYPE_TACHE_MAPPE, charge_estimee_heures=1.0, equipes_ids=[])
        ],
        equipes=[
            EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=False),
            EquipeGreenSIG(id=200, nom_equipe="Equipe Sud", actif=True),
        ],
        types_tache=[TypeTacheGreenSIG(id=_ID_TYPE_TACHE_MAPPE, nom_tache="Binage")],
        operateurs=[OperateurGreenSIG(id=1, equipe_id=100, competences_ids=[_ID_COMPETENCE_BINAGE])],
    )

    with pytest.raises(ValueError, match="sans aucune contrainte de compatibilité"):
        traduire(payload)


def test_operateur_sans_equipe_ignore_dans_le_calcul_de_competence() -> None:
    """Un opérateur qualifié mais sans équipe (`equipe_id=None`) ne peut
    rendre aucune équipe compatible — garde-fou basique contre une
    compétence orpheline."""
    payload = PayloadGreenSIG(
        taches=[
            TacheGreenSIG(id=1, id_type_tache_id=_ID_TYPE_TACHE_MAPPE, charge_estimee_heures=1.0, equipes_ids=[])
        ],
        equipes=[EquipeGreenSIG(id=100, nom_equipe="Equipe Nord", actif=True)],
        types_tache=[TypeTacheGreenSIG(id=_ID_TYPE_TACHE_MAPPE, nom_tache="Binage")],
        operateurs=[OperateurGreenSIG(id=1, equipe_id=None, competences_ids=[_ID_COMPETENCE_BINAGE])],
    )

    with pytest.raises(ValueError, match="sans aucune contrainte de compatibilité"):
        traduire(payload)
