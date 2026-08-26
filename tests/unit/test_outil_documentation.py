"""Couche 1 (§6.1) : `generation/agents/outil_documentation.py` — l'outil de consultation
documentaire pour Architecte/Développeur. Aucun appel LLM réel (voir
`tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

from generation.agents import outil_documentation as outil
from tests.unit.aides_test_agents import ModeleFactice


def test_lister_sujets_disponibles_correspond_aux_fichiers_reellement_presents() -> None:
    """Un sujet catalogué sans fichier (ou l'inverse) casserait silencieusement l'outil — ce
    test échoue explicitement plutôt que de laisser passer une incohérence."""
    sujets = outil.lister_sujets_disponibles()
    assert sujets  # au moins un sujet catalogué

    fichiers_presents = {chemin.stem for chemin in outil._DOSSIER_REFERENCE.glob("*.md")}
    assert set(sujets) == fichiers_presents


def test_lister_sujets_disponibles_renvoie_une_copie() -> None:
    sujets = outil.lister_sujets_disponibles()
    sujets["nouveau"] = "ne doit pas affecter le catalogue interne"
    assert "nouveau" not in outil.lister_sujets_disponibles()


def test_rechercher_documentation_sujet_connu_renvoie_le_contenu() -> None:
    contenu = outil.rechercher_documentation("genetic")
    assert contenu is not None
    assert "croisement" in contenu.lower() or "crossover" in contenu.lower()


def test_rechercher_documentation_sujet_inconnu_renvoie_none() -> None:
    assert outil.rechercher_documentation("sujet_qui_n_existe_pas") is None


def test_rechercher_documentation_sujet_absent_renvoie_none() -> None:
    assert outil.rechercher_documentation(None) is None
    assert outil.rechercher_documentation("") is None


def test_consulter_si_utile_sujet_valide_renvoie_le_contenu_formate() -> None:
    modele = ModeleFactice(raw_content='{"sujet": "aco"}', parsed=outil._SchemaBesoinDocumentation(sujet="aco"))

    resultat = outil.consulter_si_utile(modele, "concevoir le plan technique du solveur", "aco")

    assert resultat.startswith("### aco")
    assert "phéromone" in resultat.lower()


def test_consulter_si_utile_sans_besoin_renvoie_chaine_vide() -> None:
    modele = ModeleFactice(raw_content="{}", parsed=outil._SchemaBesoinDocumentation(sujet=None))

    resultat = outil.consulter_si_utile(modele, "écrire le code du solveur", "cp_sat")

    assert resultat == ""


def test_consulter_si_utile_sujet_inconnu_renvoie_chaine_vide() -> None:
    modele = ModeleFactice(
        raw_content='{"sujet": "quantique"}', parsed=outil._SchemaBesoinDocumentation(sujet="quantique")
    )

    resultat = outil.consulter_si_utile(modele, "écrire le code du solveur", "cp_sat")

    assert resultat == ""


def test_consulter_si_utile_echec_de_l_appel_ne_propage_jamais() -> None:
    """Outil auxiliaire, jamais bloquant — même après épuisement des tentatives de
    `invoquer_agent_structure`."""
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    resultat = outil.consulter_si_utile(modele, "concevoir le plan technique du solveur", "cp_sat")

    assert resultat == ""


def test_consulter_si_utile_forme_inattendue_ne_leve_pas() -> None:
    """Reproduit la situation réelle de `tests/integration/test_graph_pipeline.py::_fabrique` :
    le modèle factice renvoie un objet d'un tout autre schéma (celui de l'appel principal, pas
    `_SchemaBesoinDocumentation`) — `getattr` doit absorber ça proprement."""

    class _AutreSchema:
        pass

    modele = ModeleFactice(raw_content="{}", parsed=_AutreSchema())

    resultat = outil.consulter_si_utile(modele, "concevoir le plan technique du solveur", "cp_sat")

    assert resultat == ""
