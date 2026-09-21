"""Couche 1 (§6.1) : `api.statistiques_generation` est calcul pur sur des listes de dicts déjà
en mémoire (pas de DB, pas de FastAPI) — les deux implémentations `EtatAPI`/`EtatPostgres` de
`lister_jobs_generation_persistes`/`lister_evenements_generation`/`lister_tentatives_generation`
sont censées produire exactement cette forme, voir leurs docstrings respectives."""

from __future__ import annotations

import pytest

from api.statistiques_generation import SEUIL_ECHECS_BOUCLE, agent_normalise, calculer_statistiques


def _job(
    job_id: str,
    *,
    termine: bool,
    reussi: bool | None,
    nombre_tentatives: int | None,
    cree_le: str | None = None,
    termine_le: str | None = None,
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "termine": termine,
        "reussi": reussi,
        "nombre_tentatives": nombre_tentatives,
        "cree_le": cree_le,
        "termine_le": termine_le,
    }


def test_agent_normalise_retire_le_suffixe_de_tentative() -> None:
    assert agent_normalise("debugger (tentative 3/10)") == "debugger"
    assert agent_normalise("analyste") == "analyste"


def test_calculer_statistiques_sur_liste_vide_ne_leve_pas() -> None:
    resultat = calculer_statistiques([], [], [], max_tentatives_reparation=10)
    assert resultat.generations_lancees == 0
    assert resultat.generations_terminees == 0
    assert resultat.taux_reussite is None
    assert resultat.tentatives_moyennes_convergence is None
    assert resultat.taux_epuisement_boucle is None
    assert resultat.taux_boucles_detectees is None
    assert resultat.diversite_actions_moyenne is None
    assert resultat.taux_stagnation is None


def test_taux_reussite_et_generations_comptees() -> None:
    jobs = [
        _job("j1", termine=True, reussi=True, nombre_tentatives=1),
        _job("j2", termine=True, reussi=False, nombre_tentatives=10),
        _job("j3", termine=False, reussi=None, nombre_tentatives=None),  # encore en cours
    ]
    resultat = calculer_statistiques(jobs, [], [], max_tentatives_reparation=10)
    assert resultat.generations_lancees == 3
    assert resultat.generations_terminees == 2  # j3 exclu (pas terminé)
    assert resultat.taux_reussite == 50.0


def test_tentatives_moyennes_convergence_ne_compte_que_les_reussis() -> None:
    jobs = [
        _job("j1", termine=True, reussi=True, nombre_tentatives=2),
        _job("j2", termine=True, reussi=True, nombre_tentatives=6),
        _job("j3", termine=True, reussi=False, nombre_tentatives=10),  # exclu : pas réussi
    ]
    resultat = calculer_statistiques(jobs, [], [], max_tentatives_reparation=10)
    assert resultat.tentatives_moyennes_convergence == 4.0


def test_taux_epuisement_boucle_distingue_echec_epuise_et_echec_precoce() -> None:
    jobs = [
        _job("j1", termine=True, reussi=False, nombre_tentatives=10),  # épuisé
        _job("j2", termine=True, reussi=False, nombre_tentatives=3),  # échec précoce, pas épuisé
        _job("j3", termine=True, reussi=True, nombre_tentatives=10),  # réussi, jamais "épuisé"
    ]
    resultat = calculer_statistiques(jobs, [], [], max_tentatives_reparation=10)
    assert resultat.taux_epuisement_boucle == pytest.approx(100 / 3)


def test_duree_moyenne_ignore_les_jobs_sans_horodatage_de_fin() -> None:
    jobs = [
        _job(
            "j1",
            termine=True,
            reussi=True,
            nombre_tentatives=1,
            cree_le="2026-08-15T10:00:00+00:00",
            termine_le="2026-08-15T10:01:40+00:00",
        ),
        _job("j2", termine=True, reussi=True, nombre_tentatives=1, cree_le="2026-08-15T10:00:00+00:00"),
    ]
    resultat = calculer_statistiques(jobs, [], [], max_tentatives_reparation=10)
    assert resultat.duree_moyenne_s == 100.0


def test_boucle_detectee_quand_un_agent_echoue_au_moins_le_seuil_de_fois() -> None:
    jobs = [_job("j1", termine=True, reussi=False, nombre_tentatives=SEUIL_ECHECS_BOUCLE)]
    evenements = [
        {"job_id": "j1", "ordre": i, "agent": f"test_sandbox (tentative {i + 1}/10)", "statut": "echec"}
        for i in range(SEUIL_ECHECS_BOUCLE)
    ]
    resultat = calculer_statistiques(jobs, evenements, [], max_tentatives_reparation=10)
    assert resultat.taux_boucles_detectees == 100.0


def test_pas_de_boucle_detectee_sous_le_seuil() -> None:
    jobs = [_job("j1", termine=True, reussi=False, nombre_tentatives=SEUIL_ECHECS_BOUCLE - 1)]
    evenements = [
        {"job_id": "j1", "ordre": i, "agent": f"test_sandbox (tentative {i + 1}/10)", "statut": "echec"}
        for i in range(SEUIL_ECHECS_BOUCLE - 1)
    ]
    resultat = calculer_statistiques(jobs, evenements, [], max_tentatives_reparation=10)
    assert resultat.taux_boucles_detectees == 0.0


def test_diversite_actions_basse_quand_un_seul_agent_repete() -> None:
    jobs = [_job("j1", termine=True, reussi=False, nombre_tentatives=4)]
    evenements = [
        {"job_id": "j1", "ordre": i, "agent": f"debugger (tentative {i + 1}/10)", "statut": "echec"}
        for i in range(4)
    ]
    resultat = calculer_statistiques(jobs, evenements, [], max_tentatives_reparation=10)
    # 1 agent unique ("debugger", une fois normalisé) sur 4 évènements.
    assert resultat.diversite_actions_moyenne == 0.25


def test_diversite_actions_haute_quand_chaque_evenement_est_un_agent_different() -> None:
    jobs = [_job("j1", termine=True, reussi=True, nombre_tentatives=1)]
    evenements = [
        {"job_id": "j1", "ordre": 0, "agent": "analyste", "statut": "termine"},
        {"job_id": "j1", "ordre": 1, "agent": "benchmarker", "statut": "termine"},
        {"job_id": "j1", "ordre": 2, "agent": "architecte", "statut": "termine"},
    ]
    resultat = calculer_statistiques(jobs, evenements, [], max_tentatives_reparation=10)
    assert resultat.diversite_actions_moyenne == 1.0


def test_stagnation_detectee_quand_le_code_candidat_ne_change_pas() -> None:
    jobs = [_job("j1", termine=True, reussi=False, nombre_tentatives=3)]
    tentatives = [
        {"job_id": "j1", "numero": 1, "code_candidat": "def resoudre(): pass"},
        {"job_id": "j1", "numero": 2, "code_candidat": "def resoudre(): pass"},  # identique -> stagnation
        {"job_id": "j1", "numero": 3, "code_candidat": "def resoudre(): return None"},  # changé
    ]
    resultat = calculer_statistiques(jobs, [], tentatives, max_tentatives_reparation=10)
    # 2 transitions (1->2, 2->3), 1 stagnante.
    assert resultat.taux_stagnation == 50.0


def test_stagnation_none_avec_une_seule_tentative_par_job() -> None:
    jobs = [_job("j1", termine=True, reussi=True, nombre_tentatives=1)]
    tentatives = [{"job_id": "j1", "numero": 1, "code_candidat": "def resoudre(): pass"}]
    resultat = calculer_statistiques(jobs, [], tentatives, max_tentatives_reparation=10)
    assert resultat.taux_stagnation is None


def test_filtre_agent_exclut_les_jobs_ou_il_najamais_tourne() -> None:
    jobs = [
        _job("j1", termine=True, reussi=True, nombre_tentatives=1),
        _job("j2", termine=True, reussi=False, nombre_tentatives=10),
    ]
    evenements = [
        {"job_id": "j1", "ordre": 0, "agent": "analyste", "statut": "termine"},
        {"job_id": "j2", "ordre": 0, "agent": "debugger (tentative 1/10)", "statut": "echec"},
    ]
    resultat = calculer_statistiques(jobs, evenements, [], max_tentatives_reparation=10, agent="debugger")
    assert resultat.generations_lancees == 1  # seul j2 a vu le debugger tourner
    assert resultat.taux_reussite == 0.0


def test_filtre_agent_rend_la_detection_de_boucle_specifique_a_cet_agent() -> None:
    jobs = [_job("j1", termine=True, reussi=False, nombre_tentatives=SEUIL_ECHECS_BOUCLE)]
    # test_sandbox échoue 3 fois (seuil atteint), validation échoue 1 fois seulement — les deux
    # sont dans AGENTS_CAPABLES_ECHEC, la comparaison reste valide.
    evenements = [
        {"job_id": "j1", "ordre": 0, "agent": "validation (tentative 1/10)", "statut": "echec"},
        *(
            {
                "job_id": "j1",
                "ordre": i + 1,
                "agent": f"test_sandbox (tentative {i + 1}/10)",
                "statut": "echec",
            }
            for i in range(SEUIL_ECHECS_BOUCLE)
        ),
    ]
    resultat_test_sandbox = calculer_statistiques(
        jobs, evenements, [], max_tentatives_reparation=10, agent="test_sandbox"
    )
    resultat_validation = calculer_statistiques(
        jobs, evenements, [], max_tentatives_reparation=10, agent="validation"
    )
    assert resultat_test_sandbox.taux_boucles_detectees == 100.0
    assert resultat_validation.taux_boucles_detectees == 0.0


def test_boucles_detectees_non_applicable_pour_un_agent_qui_ne_peut_pas_echouer() -> None:
    """Cohérence : filtrer « boucles détectées » sur le Debugger (jamais `statut="echec"` dans
    `generation/graph.py` — il produit toujours une correction) doit renvoyer `None`, jamais un
    0% qui se lirait à tort comme « le Debugger ne boucle jamais »."""
    jobs = [_job("j1", termine=True, reussi=False, nombre_tentatives=5)]
    evenements = [
        {"job_id": "j1", "ordre": i, "agent": f"debugger (tentative {i + 1}/10)", "statut": "termine"}
        for i in range(5)
    ]
    resultat = calculer_statistiques(jobs, evenements, [], max_tentatives_reparation=10, agent="debugger")
    assert resultat.taux_boucles_detectees is None
    # Le reste des KPI reste calculé normalement — seule la cohérence de ce KPI précis est en jeu.
    assert resultat.generations_lancees == 1


def test_filtre_agent_inconnu_donne_zero_generation_sans_lever() -> None:
    jobs = [_job("j1", termine=True, reussi=True, nombre_tentatives=1)]
    evenements = [{"job_id": "j1", "ordre": 0, "agent": "analyste", "statut": "termine"}]
    resultat = calculer_statistiques(
        jobs, evenements, [], max_tentatives_reparation=10, agent="agent_qui_nexiste_pas"
    )
    assert resultat.generations_lancees == 0
    assert resultat.taux_reussite is None


def test_les_mesures_d_appels_ne_comptent_pas_comme_des_actions_d_agent() -> None:
    """Une mesure (`statut="mesure"`) décrit un appel au modèle, pas une étape : trois agents
    distincts restent une diversité parfaite, quel que soit le nombre de mesures émises."""
    jobs = [_job("j1", termine=True, reussi=True, nombre_tentatives=1)]
    evenements = [
        {"job_id": "j1", "ordre": 0, "agent": "analyste", "statut": "termine"},
        {"job_id": "j1", "ordre": 1, "agent": "analyste", "statut": "mesure"},
        {"job_id": "j1", "ordre": 2, "agent": "benchmarker", "statut": "termine"},
        {"job_id": "j1", "ordre": 3, "agent": "benchmarker", "statut": "mesure"},
        {"job_id": "j1", "ordre": 4, "agent": "architecte", "statut": "termine"},
    ]
    resultat = calculer_statistiques(jobs, evenements, [], max_tentatives_reparation=10)
    assert resultat.diversite_actions_moyenne == 1.0
