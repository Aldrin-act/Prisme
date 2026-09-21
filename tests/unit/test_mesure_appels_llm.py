"""Couche 1 (§6.1) : mesure de chaque appel au modèle (`client_llm.MesureAppelLLM`) et sa
remontée dans le flux d'une génération (`generation.graph._emettre_mesure_appel`).

Motif : une génération pouvait durer des dizaines de minutes sans que rien dans PRISME ne dise
pourquoi — réflexion du modèle, attente d'une place sur un compte limité à une requête
simultanée, ou refus 429 rattrapés. L'information n'existait que dans LangSmith. Aucun appel
réseau ici : les « appels au modèle » sont des fonctions locales qui renvoient un `AIMessage`.
"""

from __future__ import annotations

import threading

import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from generation import graph
from generation.agents import client_llm
from generation.agents.client_llm import MesureAppelLLM


def _message(sortie: int = 1_200, reflexion: int | None = None, modele: str = "kimi-k2.6") -> AIMessage:
    usage: dict[str, object] = {"input_tokens": 6_694, "output_tokens": sortie, "total_tokens": 6_694 + sortie}
    if reflexion is not None:
        usage["output_token_details"] = {"reasoning": reflexion}
    return AIMessage(content="ok", usage_metadata=usage, response_metadata={"model_name": modele})


@pytest.fixture
def mesures(monkeypatch: pytest.MonkeyPatch) -> list[MesureAppelLLM]:
    """Remplace l'observateur global par un collecteur, et neutralise limite et attentes."""
    collectees: list[MesureAppelLLM] = []
    monkeypatch.setattr(client_llm, "_observateur_appels", collectees.append)
    monkeypatch.delenv("PRISME_LLM_CONCURRENCE_MAX", raising=False)
    monkeypatch.setattr(client_llm.time, "sleep", lambda _: None)
    return collectees


class _Erreur429(Exception):
    status_code = 429


# --- Mesure elle-même ----------------------------------------------------------------------------


def test_un_appel_reussi_rapporte_modele_tokens_et_reflexion(mesures: list[MesureAppelLLM]) -> None:
    client_llm._avec_retry(lambda: _message(sortie=19_229, reflexion=17_388))()

    (mesure,) = mesures
    assert mesure.reussi
    assert mesure.modele == "kimi-k2.6"
    assert (mesure.tokens_entree, mesure.tokens_sortie, mesure.tokens_reflexion) == (6_694, 19_229, 17_388)
    assert (mesure.tentatives, mesure.refus_429) == (1, 0)
    assert mesure.reponse_conforme is None  # appel brut, pas de sortie structurée


def test_la_sortie_structuree_signale_une_reponse_hors_format(mesures: list[MesureAppelLLM]) -> None:
    reponse = {"raw": _message(), "parsed": None, "parsing_error": ValueError("champ manquant")}

    client_llm._avec_retry(lambda: reponse)()

    assert mesures[0].reponse_conforme is False
    assert mesures[0].tokens_sortie == 1_200  # l'usage est lu sur le message brut


def test_les_refus_429_rattrapes_sont_comptes(mesures: list[MesureAppelLLM]) -> None:
    essais = iter([_Erreur429(), _Erreur429(), _message()])

    def appel() -> AIMessage:
        resultat = next(essais)
        if isinstance(resultat, Exception):
            raise resultat
        return resultat

    client_llm._avec_retry(appel)()

    (mesure,) = mesures
    assert mesure.reussi
    assert (mesure.tentatives, mesure.refus_429) == (3, 2)


def test_un_appel_qui_echoue_est_mesure_quand_meme(mesures: list[MesureAppelLLM]) -> None:
    def toujours_refuse() -> AIMessage:
        raise _Erreur429("max organization concurrency: 1")

    with pytest.raises(_Erreur429):
        client_llm._avec_retry(toujours_refuse)()

    (mesure,) = mesures
    assert not mesure.reussi
    assert mesure.refus_429 == client_llm._TENTATIVES_MAX
    assert "max organization concurrency" in (mesure.erreur or "")
    assert mesure.tokens_sortie is None
    assert mesure.cause_dominante() == "refus"


def test_l_attente_d_une_place_est_mesuree(monkeypatch: pytest.MonkeyPatch, mesures: list[MesureAppelLLM]) -> None:
    monkeypatch.setenv("PRISME_LLM_CONCURRENCE_MAX", "1")
    limiteur = client_llm._limiteur_concurrence()
    limiteur.acquire()  # un autre appel occupe l'unique place
    liberateur = threading.Timer(0.3, limiteur.release)
    liberateur.start()

    client_llm._avec_retry(lambda: _message())()
    liberateur.join()

    assert mesures[0].attente_file_s >= 0.25
    assert mesures[0].duree_s >= mesures[0].attente_file_s


def test_un_observateur_en_echec_ne_fait_jamais_echouer_l_appel(monkeypatch: pytest.MonkeyPatch) -> None:
    def observateur_casse(_: MesureAppelLLM) -> None:
        raise RuntimeError("panne de l'observateur")

    monkeypatch.setattr(client_llm, "_observateur_appels", observateur_casse)

    assert client_llm._avec_retry(lambda: "réponse")() == "réponse"


# --- Cause dominante -----------------------------------------------------------------------------


def _mesure(**champs: object) -> MesureAppelLLM:
    base: dict[str, object] = {
        "reussi": True,
        "duree_s": 600.0,
        "attente_file_s": 0.0,
        "tentatives": 1,
        "refus_429": 0,
    }
    return MesureAppelLLM(**(base | champs))


def test_cause_reflexion_quand_elle_domine_un_appel_long() -> None:
    assert _mesure(tokens_sortie=19_229, tokens_reflexion=17_388).cause_dominante() == "reflexion"


def test_cause_attente_quand_la_place_a_ete_attendue_plus_de_la_moitie_du_temps() -> None:
    mesure = _mesure(duree_s=100.0, attente_file_s=70.0, tokens_sortie=19_229, tokens_reflexion=17_388)

    assert mesure.cause_dominante() == "attente"  # l'attente prime : elle explique la majorité du temps


def test_aucune_cause_pour_un_appel_court() -> None:
    assert _mesure(duree_s=2.0, tokens_sortie=58, tokens_reflexion=1).cause_dominante() is None


def test_la_cause_est_incluse_dans_le_dictionnaire_transmis() -> None:
    assert _mesure(tokens_sortie=19_229, tokens_reflexion=17_388).en_dict()["cause"] == "reflexion"


# --- Remontée dans le flux de génération ---------------------------------------------------------


def test_resume_lisible_d_une_mesure() -> None:
    mesure = MesureAppelLLM(
        reussi=True,
        duree_s=725.0,
        attente_file_s=38.0,
        tentatives=1,
        refus_429=0,
        modele="kimi-k2.6",
        tokens_entree=6_694,
        tokens_sortie=19_229,
        tokens_reflexion=17_388,
    )

    resume = graph.resumer_mesure(mesure)

    assert resume.startswith("kimi-k2.6 · 12 min 05 s (dont 38 s d'attente d'une place)")
    assert "6 694 → 19 229 tokens, dont 17 388 de réflexion" in resume


def test_hors_d_une_generation_la_mesure_est_ignoree_sans_erreur() -> None:
    graph._emettre_mesure_appel(_mesure())  # aucun contexte de graphe : ne doit rien lever


def test_dans_une_generation_la_mesure_remonte_rattachee_au_bon_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_llm, "_observateur_appels", graph._emettre_mesure_appel)
    monkeypatch.delenv("PRISME_LLM_CONCURRENCE_MAX", raising=False)

    class Etat(TypedDict):
        fait: bool

    def benchmarker(_: Etat) -> dict:
        client_llm._avec_retry(lambda: _message(sortie=2_797, reflexion=615))()
        return {"fait": True}

    constructeur = StateGraph(Etat)
    constructeur.add_node("benchmarker", benchmarker)
    constructeur.add_edge(START, "benchmarker")
    constructeur.add_edge("benchmarker", END)
    evenements = list(constructeur.compile().stream({"fait": False}, stream_mode="custom"))

    (evenement,) = evenements
    assert evenement["agent"] == "benchmarker"
    assert evenement["statut"] == "mesure"
    assert evenement["details"]["tokens_reflexion"] == 615
    assert evenement["details"]["modele"] == "kimi-k2.6"
    assert "2 797 tokens" in evenement["resume"]


def test_l_observateur_du_graphe_est_pose_a_l_import() -> None:
    # C'est ce branchement, fait à l'import de `generation.graph`, qui relie la mesure au flux.
    assert client_llm._observateur_appels is graph._emettre_mesure_appel


# --- Réponse coupée à la limite de tokens de sortie ---------------------------------------------
# Vu en pratique : le Développeur avec réflexion a produit 32 768 tokens (la limite), dont 31 099 de
# réflexion — le JSON du code était coupé, illisible, après 14 min d'appel.


def _erreur_reponse_coupee() -> Exception:
    import openai
    from openai.types.chat import ChatCompletion
    from openai.types.completion_usage import CompletionTokensDetails, CompletionUsage

    usage = CompletionUsage(
        completion_tokens=32_768,
        prompt_tokens=13_581,
        total_tokens=46_349,
        completion_tokens_details=CompletionTokensDetails(reasoning_tokens=31_099),
    )
    return openai.LengthFinishReasonError(
        completion=ChatCompletion.model_construct(model="kimi-k2.6", usage=usage)
    )


def test_une_reponse_coupee_est_mesuree_avec_son_usage(mesures: list[MesureAppelLLM]) -> None:
    erreur = _erreur_reponse_coupee()

    def appel() -> AIMessage:
        raise erreur

    with pytest.raises(type(erreur)):
        client_llm._avec_retry(appel)()

    (mesure,) = mesures
    assert not mesure.reussi
    assert mesure.limite_sortie_atteinte
    assert mesure.tentatives == 1  # jamais retentée : le même prompt recouperait au même endroit
    assert (mesure.tokens_entree, mesure.tokens_sortie, mesure.tokens_reflexion) == (13_581, 32_768, 31_099)
    assert mesure.modele == "kimi-k2.6"
    assert mesure.cause_dominante() == "longueur"
    assert "réponse coupée" in graph.resumer_mesure(mesure)


class _ModeleQuiCoupe:
    """Faux modèle dont la sortie structurée lève l'erreur de réponse coupée du SDK."""

    def with_structured_output(self, schema: object, include_raw: bool = True, method: str | None = None):
        erreur = _erreur_reponse_coupee()

        class _Runnable:
            def invoke(self, messages: object) -> dict:
                raise erreur

        return _Runnable()


def test_un_agent_coupe_renvoie_un_message_qui_dit_quoi_faire(mesures: list[MesureAppelLLM]) -> None:
    from pydantic import BaseModel

    class _Schema(BaseModel):
        code: str

    with pytest.raises(client_llm.ErreurReponseAgentInvalide) as erreur:
        client_llm.invoquer_agent_structure(_ModeleQuiCoupe(), _Schema, [])

    message = str(erreur.value)
    assert "réponse coupée" in message
    assert "32768 tokens, dont 31099 de réflexion (95 %)" in message
    assert "PRISME_LLM_REFLEXION_<AGENT>=desactivee" in message
    assert len(mesures) == 1  # un seul appel : pas de nouvelle tentative structurée derrière
