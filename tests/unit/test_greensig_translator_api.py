"""Couche 1 (§6.1) : `translator_api.py` est du code écrit à la main, déterministe — pure
traduction, aucune dépendance externe (ni réseau ni Docker). Miroir de
`test_greensig_adapter.py` (chemin base directe) pour le chemin API HTTP publique
(`GREENSIG_MODE=api`)."""

from __future__ import annotations

from datetime import date

import pytest

from adapters.greensig import (
    AbsenceApiGreenSIG,
    EquipeApiGreenSIG,
    JourFerieApiGreenSIG,
    OperateurApiGreenSIG,
    PayloadGreenSIGApi,
    TacheApiGreenSIG,
    traduire_api,
)
from dsl.schema import CompatibiliteRessourceTache, ContrainteDisponibiliteRessource, InstanceTRCO

_DATE_REFERENCE = date(2026, 8, 10)


def test_traduction_produit_les_bonnes_taches_et_ressources() -> None:
    payload = PayloadGreenSIGApi(
        taches=[
            TacheApiGreenSIG(id=1, reference="PRI-SIT-ELA-12", type_tache="Élagage", equipes=["Équipe Nord"]),
            TacheApiGreenSIG(id=2, reference="PRI-SIT-TON-7", type_tache="Tonte", equipes=["Équipe Sud"]),
        ],
        equipes=[
            EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True),
            EquipeApiGreenSIG(id=200, nom_equipe="Équipe Sud", actif=True),
        ],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    assert isinstance(instance, InstanceTRCO)
    assert {t.id for t in instance.taches} == {"PRI-SIT-ELA-12", "PRI-SIT-TON-7"}
    assert {r.id for r in instance.ressources} == {"E100", "E200"}


def test_duree_toujours_un_jour() -> None:
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Élagage", equipes=["Équipe Nord"])],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert compatibilites == [CompatibiliteRessourceTache(tache="T1", ressource="E100", duree=1)]


def test_equipe_inactive_exclue_et_compatibilite_ignoree() -> None:
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Nord", "Équipe Sud"])],
        equipes=[
            EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True),
            EquipeApiGreenSIG(id=200, nom_equipe="Équipe Sud", actif=False),
        ],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    assert {r.id for r in instance.ressources} == {"E100"}
    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert {c.ressource for c in compatibilites} == {"E100"}


def test_equipe_inconnue_referencee_par_une_tache_ignoree_sans_erreur() -> None:
    """Une tâche qui référence un nom d'équipe absent de `equipes/` (donnée incohérente côté
    GreenSIG) ne fait jamais planter la traduction — juste ignorée, tant qu'au moins une autre
    équipe compatible existe (sinon `InstanceTRCO` rejette pour absence de compatibilité, comme
    n'importe quelle autre tâche non plannifiable)."""
    payload = PayloadGreenSIGApi(
        taches=[
            TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Fantôme", "Équipe Nord"])
        ],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert {c.ressource for c in compatibilites} == {"E100"}


def test_jour_ferie_applique_a_toutes_les_ressources_actives() -> None:
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Nord", "Équipe Sud"])],
        equipes=[
            EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True),
            EquipeApiGreenSIG(id=200, nom_equipe="Équipe Sud", actif=True),
        ],
        jours_feries=[JourFerieApiGreenSIG(date="2026-08-12")],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    disponibilites = {
        c.ressource: c.jours_indisponibles
        for c in instance.contraintes
        if isinstance(c, ContrainteDisponibiliteRessource)
    }
    assert disponibilites == {"E100": [2], "E200": [2]}


def test_absence_validee_rend_lequipe_entiere_indisponible() -> None:
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Nord"])],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
        operateurs=[OperateurApiGreenSIG(nom_complet="Jean Dupont", equipe="Équipe Nord")],
        absences=[
            AbsenceApiGreenSIG(
                operateur="Jean Dupont", date_debut="2026-08-11", date_fin="2026-08-13", statut="Validée"
            )
        ],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    disponibilites = {
        c.ressource: c.jours_indisponibles
        for c in instance.contraintes
        if isinstance(c, ContrainteDisponibiliteRessource)
    }
    assert disponibilites == {"E100": [1, 2, 3]}


def test_absence_non_validee_ignoree() -> None:
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Nord"])],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
        operateurs=[OperateurApiGreenSIG(nom_complet="Jean Dupont", equipe="Équipe Nord")],
        absences=[
            AbsenceApiGreenSIG(
                operateur="Jean Dupont", date_debut="2026-08-11", date_fin="2026-08-13", statut="En attente"
            )
        ],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    assert not [c for c in instance.contraintes if isinstance(c, ContrainteDisponibiliteRessource)]


def test_absence_dun_operateur_sans_equipe_connue_ignoree() -> None:
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Nord"])],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
        operateurs=[OperateurApiGreenSIG(nom_complet="Jean Dupont", equipe="Équipe Fantôme")],
        absences=[
            AbsenceApiGreenSIG(
                operateur="Jean Dupont", date_debut="2026-08-11", date_fin="2026-08-13", statut="Validée"
            )
        ],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    assert not [c for c in instance.contraintes if isinstance(c, ContrainteDisponibiliteRessource)]


def test_jours_anterieurs_a_la_reference_filtres() -> None:
    """Un jour férié déjà passé au moment de l'appel ne produit aucune contrainte — sans effet
    sur un horizon de planification qui démarre à `date_reference`."""
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Nord"])],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
        jours_feries=[JourFerieApiGreenSIG(date="2026-08-01")],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    assert not [c for c in instance.contraintes if isinstance(c, ContrainteDisponibiliteRessource)]


def test_instance_produite_est_valide_par_construction() -> None:
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Nord"])],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
    )

    instance = traduire_api(payload, date_reference=_DATE_REFERENCE)

    # Ne lève pas : model_validate revalide un InstanceTRCO déjà construit.
    InstanceTRCO.model_validate(instance.model_dump())


def test_tache_sans_aucune_equipe_compatible_rejetee() -> None:
    """Même garde-fou que le chemin DB (§6.7) : une tâche sans compatibilité ressource-tâche
    n'est jamais silencieusement ingérée."""
    payload = PayloadGreenSIGApi(
        taches=[TacheApiGreenSIG(id=1, reference="T1", type_tache="Tonte", equipes=["Équipe Fantôme"])],
        equipes=[EquipeApiGreenSIG(id=100, nom_equipe="Équipe Nord", actif=True)],
    )

    with pytest.raises(ValueError, match="sans aucune contrainte de compatibilité"):
        traduire_api(payload, date_reference=_DATE_REFERENCE)
