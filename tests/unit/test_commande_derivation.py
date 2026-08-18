"""Couche 1 (§6.1) : `adapters.commande_derivation` est calcul pur, aucune E/S — voir sa
docstring pour les règles de préséance (explicite > dérivé, échéance la plus proche)."""

from __future__ import annotations

from adapters.commande_derivation import Commande, deriver_echeances_par_commande
from dsl.schema import Echeance


def test_commande_avec_date_limite_derive_une_echeance_par_tache() -> None:
    commandes = [Commande(id="CMD1", taches=("T1", "T2"), client="Client A", date_limite=10)]

    derivees = deriver_echeances_par_commande(commandes, contraintes=[])

    assert len(derivees) == 2
    assert {(e.tache, e.echeance) for e in derivees} == {("T1", 10), ("T2", 10)}


def test_commande_sans_date_limite_ne_derive_rien() -> None:
    commandes = [Commande(id="CMD1", taches=("T1",), client="Client A", date_limite=None)]

    derivees = deriver_echeances_par_commande(commandes, contraintes=[])

    assert derivees == []


def test_echeance_explicite_l_emporte_sur_la_derivation() -> None:
    commandes = [Commande(id="CMD1", taches=("T1",), date_limite=10)]
    contraintes = [Echeance(tache="T1", echeance=3)]

    derivees = deriver_echeances_par_commande(commandes, contraintes)

    assert derivees == []  # T1 a déjà une échéance explicite, jamais écrasée


def test_echeance_explicite_n_empeche_pas_la_derivation_pour_une_autre_tache() -> None:
    commandes = [Commande(id="CMD1", taches=("T1", "T2"), date_limite=10)]
    contraintes = [Echeance(tache="T1", echeance=3)]

    derivees = deriver_echeances_par_commande(commandes, contraintes)

    assert len(derivees) == 1
    assert derivees[0].tache == "T2"
    assert derivees[0].echeance == 10


def test_tache_dans_plusieurs_commandes_retient_l_echeance_la_plus_proche() -> None:
    commandes = [
        Commande(id="CMD1", taches=("T1",), date_limite=20),
        Commande(id="CMD2", taches=("T1",), date_limite=5),
        Commande(id="CMD3", taches=("T1",), date_limite=15),
    ]

    derivees = deriver_echeances_par_commande(commandes, contraintes=[])

    assert len(derivees) == 1
    assert derivees[0].echeance == 5  # la plus contraignante, pas la dernière rencontrée


def test_liste_de_commandes_vide_ne_derive_rien() -> None:
    assert deriver_echeances_par_commande([], contraintes=[]) == []
