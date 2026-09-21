"""Couche 1 (§6.1) : `construire_modele`/`construire_modele_pour_agent` ne
doivent jamais transmettre un modèle vide à un SDK — régression trouvée en
testant l'agent de compréhension en conditions réelles : `.env` déclare
`PRISME_LLM_MODEL=` (présent, vide), distinct d'une variable absente pour
`os.environ.get`, le fournisseur rejetait alors l'appel avec une erreur
"modèle manquant" sans que l'erreur ne pointe vers la vraie cause.

Aucun appel réseau ici : le constructeur LangChain (`ChatOpenAI`, utilisé en
mode compatible pour OpenRouter) ne contacte le fournisseur qu'au premier
`.invoke()`, sa construction est pure.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from generation.agents import client_llm


def test_modele_vide_dans_env_retombe_sur_le_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_MODEL", "")  # présent mais vide, comme dans .env par défaut
    modeles_construits: list[str] = []
    monkeypatch.setattr(
        client_llm, "_construire_modele_fournisseur", lambda m, timeout, **_: modeles_construits.append(m)
    )

    client_llm.construire_modele()

    assert modeles_construits == [client_llm._MODELE_PAR_DEFAUT]


def test_modele_explicite_dans_env_est_respecte(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_MODEL", "mon-modele-precis")
    modeles_construits: list[str] = []
    monkeypatch.setattr(
        client_llm, "_construire_modele_fournisseur", lambda m, timeout, **_: modeles_construits.append(m)
    )

    client_llm.construire_modele()

    assert modeles_construits == ["mon-modele-precis"]


class TestTimeoutParAgent:
    def test_defaut_global_si_aucune_surcharge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRISME_LLM_TIMEOUT_SECONDES", raising=False)
        monkeypatch.delenv("PRISME_LLM_TIMEOUT_SECONDES_ANALYSTE", raising=False)
        assert client_llm._timeout_pour_agent("analyste") == client_llm._TIMEOUT_DEFAUT_SECONDES

    def test_surcharge_globale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRISME_LLM_TIMEOUT_SECONDES", "45")
        monkeypatch.delenv("PRISME_LLM_TIMEOUT_SECONDES_ANALYSTE", raising=False)
        assert client_llm._timeout_pour_agent("analyste") == 45.0

    def test_surcharge_par_agent_prioritaire_sur_la_globale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRISME_LLM_TIMEOUT_SECONDES", "45")
        monkeypatch.setenv("PRISME_LLM_TIMEOUT_SECONDES_ANALYSTE", "10")
        assert client_llm._timeout_pour_agent("analyste") == 10.0


def test_construire_modele_openrouter_construit_bien_un_chat_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "cle-test")
    # `api/routes/auth.py`/`api/auth_db.py` chargent le vrai `.env` au moment de l'import (sans
    # `override`) — dans une suite complète, un module de test important l'un des deux avant
    # celui-ci suffit à injecter un `OPENROUTER_API_BASE_URL` réel dans `os.environ`, invisible
    # en lançant ce fichier seul. Même précaution que `TestTimeoutParAgent` plus haut.
    monkeypatch.delenv("OPENROUTER_API_BASE_URL", raising=False)
    modele = client_llm._construire_modele_openrouter("moonshotai/kimi-k2.6", 120.0)
    assert modele.model == "moonshotai/kimi-k2.6"
    assert str(modele.openai_api_base) == "https://openrouter.ai/api/v1"


def test_construire_modele_openrouter_respecte_lurl_personnalisee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "cle-test")
    monkeypatch.setenv("OPENROUTER_API_BASE_URL", "https://openrouter.example/api/v1")
    modele = client_llm._construire_modele_openrouter("moonshotai/kimi-k2.6", 120.0)
    assert str(modele.openai_api_base) == "https://openrouter.example/api/v1"


def test_construire_modele_pour_agent_respecte_la_surcharge_de_modele(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_MODEL_DOCUMENTATION", "un-modele-precis")
    modeles_construits: list[str] = []
    monkeypatch.setattr(
        client_llm, "_construire_modele_fournisseur", lambda m, timeout, **_: modeles_construits.append(m)
    )

    client_llm.construire_modele_pour_agent("documentation")

    assert modeles_construits == ["un-modele-precis"]


def test_construire_modele_pour_agent_retombe_sur_le_modele_global_sans_surcharge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bug reproduit en conditions réelles (pipeline `generation/graph.py` pointée sur un
    fournisseur alternatif via `PRISME_LLM_MODEL` seul, sans surcharge par agent) :
    `construire_modele_pour_agent` ignorait `PRISME_LLM_MODEL`, retombant directement sur
    `_MODELE_PAR_DEFAUT` codé en dur dès qu'aucune variable `PRISME_LLM_MODEL_<AGENT>`
    n'était définie — rendant le réglage global sans effet sur le pipeline réel."""
    monkeypatch.delenv("PRISME_LLM_MODEL_ANALYSTE", raising=False)
    monkeypatch.setenv("PRISME_LLM_MODEL", "mon-modele-global")
    modeles_construits: list[str] = []
    monkeypatch.setattr(
        client_llm, "_construire_modele_fournisseur", lambda m, timeout, **_: modeles_construits.append(m)
    )

    client_llm.construire_modele_pour_agent("analyste")

    assert modeles_construits == ["mon-modele-global"]


class _ErreurAvecStatut(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"erreur {status_code}")
        self.status_code = status_code


class TestErreurTransitoire:
    """429 (quota/débit dépassé) doit être retenté comme un 5xx — vu en
    pratique : le fournisseur LLM, unique pour tous les agents, peut
    suffire à dépasser son débit pendant la boucle de réparation, plusieurs
    agents y appelant coup sur coup. Les autres 4xx (clé invalide...)
    restent définitifs."""

    @pytest.mark.parametrize("code_statut", [500, 502, 503, 504, 429])
    def test_erreurs_retentables(self, code_statut: int) -> None:
        assert client_llm._est_erreur_transitoire(_ErreurAvecStatut(code_statut))

    @pytest.mark.parametrize("code_statut", [400, 401, 403, 404])
    def test_erreurs_non_retentables(self, code_statut: int) -> None:
        assert not client_llm._est_erreur_transitoire(_ErreurAvecStatut(code_statut))

    def test_timeout_est_retentable_sans_status_code(self) -> None:
        class FauxAPITimeoutError(Exception):
            pass

        assert client_llm._est_erreur_transitoire(FauxAPITimeoutError("timeout"))

    def test_erreur_sans_rapport_n_est_pas_retentable(self) -> None:
        assert not client_llm._est_erreur_transitoire(ValueError("prompt rejeté"))


class TestAvecRetry:
    def test_reessaie_jusqu_au_succes_sur_erreur_transitoire(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(client_llm.time, "sleep", lambda _: None)
        appels = {"n": 0}

        def appel() -> str:
            appels["n"] += 1
            if appels["n"] < 3:
                raise _ErreurAvecStatut(429)
            return "ok"

        resultat = client_llm._avec_retry(appel)()

        assert resultat == "ok"
        assert appels["n"] == 3

    def test_ne_reessaie_pas_sur_erreur_definitive(self) -> None:
        def appel() -> str:
            raise _ErreurAvecStatut(401)

        with pytest.raises(_ErreurAvecStatut):
            client_llm._avec_retry(appel)()


class _SchemaFactice(BaseModel):
    valeur: str


class _RunnableStructureFactice:
    """Contrairement à `tests/unit/aides_test_agents.py::ModeleFactice`
    (stateless — renvoie toujours la même sortie), celui-ci consomme une
    séquence : nécessaire pour tester qu'`invoquer_agent_structure` retente
    bien un *nouvel* appel LLM plutôt que de rejouer indéfiniment la même
    réponse."""

    def __init__(self, sequence: list[dict]) -> None:
        self._sequence = iter(sequence)

    def invoke(self, messages: object) -> dict:
        return next(self._sequence)


class _ModeleFactice:
    def __init__(self, sequence: list[dict]) -> None:
        self._sequence = sequence

    def with_structured_output(
        self, schema: type, include_raw: bool = True, method: str | None = None
    ) -> _RunnableStructureFactice:
        return _RunnableStructureFactice(self._sequence)


def _sortie(contenu: str, parsed: _SchemaFactice | None, parsing_error: Exception | None = None) -> dict:
    return {"raw": AIMessage(content=contenu), "parsed": parsed, "parsing_error": parsing_error}


class TestInvoquerAgentStructure:
    """`invoquer_agent_structure` (bug reproduit sur l'agent Architecte,
    `fonctions_internes` renvoyé comme un objet imbriqué au lieu d'une
    chaîne) : retente un nouvel appel LLM complet — jamais couvert par
    `_avec_retry`, qui ne réagit qu'à une exception réseau transitoire,
    jamais à un JSON syntaxiquement valide mais non conforme au schéma."""

    def test_reussit_du_premier_coup_sans_second_appel(self) -> None:
        parsed = _SchemaFactice(valeur="ok")
        modele = _ModeleFactice([_sortie("ok", parsed)])

        donnees, reponse_brute = client_llm.invoquer_agent_structure(
            modele, _SchemaFactice, [HumanMessage(content="x")]
        )

        assert donnees is parsed
        assert reponse_brute == "ok"

    def test_reessaie_puis_reussit_sur_sortie_non_conforme(self) -> None:
        parsed = _SchemaFactice(valeur="ok")
        modele = _ModeleFactice(
            [
                _sortie("mal formé", None, ValueError("mal formé")),
                _sortie("ok", parsed),
            ]
        )

        donnees, reponse_brute = client_llm.invoquer_agent_structure(
            modele, _SchemaFactice, [HumanMessage(content="x")]
        )

        assert donnees is parsed
        assert reponse_brute == "ok"

    def test_leve_apres_epuisement_des_tentatives(self) -> None:
        modele = _ModeleFactice([_sortie(f"mal formé {i}", None, ValueError("x")) for i in range(3)])

        with pytest.raises(client_llm.ErreurReponseAgentInvalide, match="mal formé 2"):
            client_llm.invoquer_agent_structure(
                modele, _SchemaFactice, [HumanMessage(content="x")], tentatives_max=3
            )

    def test_respecte_tentatives_max_personnalise(self) -> None:
        appels = {"n": 0}

        class _RunnableCompteur:
            def invoke(self, messages: object) -> dict:
                appels["n"] += 1
                return _sortie("mal formé", None, ValueError("x"))

        class _ModeleCompteur:
            def with_structured_output(self, schema: type, include_raw: bool = True, method=None):
                return _RunnableCompteur()

        with pytest.raises(client_llm.ErreurReponseAgentInvalide):
            client_llm.invoquer_agent_structure(
                _ModeleCompteur(), _SchemaFactice, [HumanMessage(content="x")], tentatives_max=2
            )

        assert appels["n"] == 2


class _ModeleLieFactice:
    """Modèle « lié » renvoyé par `_ModeleAvecOutilsFactice.bind_tools` — rejoue
    une séquence de réponses (`AIMessage`, avec ou sans `tool_calls`)."""

    def __init__(self, sequence: list[AIMessage]) -> None:
        self._sequence = iter(sequence)

    def invoke(self, conversation: object) -> AIMessage:
        return next(self._sequence)


class _ModeleAvecOutilsFactice:
    """`bind_tools` renvoie un modèle lié qui rejoue `sequence_liee` ;
    `with_structured_output` (phase finale, appelée sur le modèle d'origine,
    jamais le modèle lié — voir `invoquer_agent_avec_outils`) renvoie
    directement `sortie_finale`."""

    def __init__(self, sequence_liee: list[AIMessage], sortie_finale: dict) -> None:
        self._sequence_liee = sequence_liee
        self._sortie_finale = sortie_finale

    def bind_tools(self, outils: list) -> _ModeleLieFactice:
        return _ModeleLieFactice(self._sequence_liee)

    def with_structured_output(
        self, schema: type, include_raw: bool = True, method: str | None = None
    ) -> _RunnableStructureFactice:
        return _RunnableStructureFactice([self._sortie_finale])


class TestInvoquerAgentAvecOutils:
    """`invoquer_agent_avec_outils` (premier mécanisme de tool-calling du
    projet, voir `generation/agents/analyste.py`/`benchmarker.py`) : boucle
    d'outils en sortie libre, puis un dernier appel `invoquer_agent_structure`
    classique sur le modèle d'origine pour la réponse conforme au schéma."""

    def test_sans_outils_equivaut_a_invoquer_agent_structure(self) -> None:
        parsed = _SchemaFactice(valeur="ok")
        modele = _ModeleFactice([_sortie("ok", parsed)])

        donnees, reponse_brute, appels = client_llm.invoquer_agent_avec_outils(
            modele, _SchemaFactice, [], [HumanMessage(content="x")]
        )

        assert donnees is parsed
        assert reponse_brute == "ok"
        assert appels == []

    def test_appelle_l_outil_puis_produit_la_reponse_structuree(self) -> None:
        from langchain_core.tools import tool

        @tool
        def mon_outil(x: int) -> str:
            """Un outil factice."""
            return f"resultat:{x}"

        appel_ia = AIMessage(content="", tool_calls=[{"name": "mon_outil", "args": {"x": 1}, "id": "call1"}])
        reponse_finale_ia = AIMessage(content="")
        parsed = _SchemaFactice(valeur="ok")
        modele = _ModeleAvecOutilsFactice(
            sequence_liee=[appel_ia, reponse_finale_ia], sortie_finale=_sortie("ok", parsed)
        )

        donnees, reponse_brute, appels = client_llm.invoquer_agent_avec_outils(
            modele, _SchemaFactice, [mon_outil], [HumanMessage(content="x")]
        )

        assert donnees is parsed
        assert appels == ["mon_outil({'x': 1})"]

    def test_arrete_apres_max_appels_outils_et_repond_quand_meme(self) -> None:
        from langchain_core.tools import tool

        @tool
        def mon_outil(x: int) -> str:
            """Un outil factice."""
            return f"resultat:{x}"

        appel_ia = AIMessage(content="", tool_calls=[{"name": "mon_outil", "args": {"x": 1}, "id": "call1"}])
        parsed = _SchemaFactice(valeur="ok")
        modele = _ModeleAvecOutilsFactice(
            sequence_liee=[appel_ia, appel_ia, appel_ia], sortie_finale=_sortie("ok", parsed)
        )

        donnees, reponse_brute, appels = client_llm.invoquer_agent_avec_outils(
            modele, _SchemaFactice, [mon_outil], [HumanMessage(content="x")], max_appels_outils=3
        )

        assert donnees is parsed
        assert appels == ["mon_outil({'x': 1})"] * 3

    def test_outil_inconnu_ne_bloque_pas_la_boucle(self) -> None:
        from langchain_core.tools import tool

        @tool
        def mon_outil(x: int) -> str:
            """Un outil factice."""
            return f"resultat:{x}"

        appel_inconnu = AIMessage(content="", tool_calls=[{"name": "outil_fantome", "args": {}, "id": "call1"}])
        reponse_finale_ia = AIMessage(content="")
        parsed = _SchemaFactice(valeur="ok")
        modele = _ModeleAvecOutilsFactice(
            sequence_liee=[appel_inconnu, reponse_finale_ia], sortie_finale=_sortie("ok", parsed)
        )

        donnees, reponse_brute, appels = client_llm.invoquer_agent_avec_outils(
            modele, _SchemaFactice, [mon_outil], [HumanMessage(content="x")]
        )

        assert donnees is parsed
        assert appels == ["outil_fantome({})"]


# --- Choix du fournisseur : Kimi en direct ou OpenRouter ---


def test_kimi_choisi_des_que_sa_cle_est_renseignee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISME_LLM_FOURNISSEUR", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")
    assert client_llm.fournisseur_llm() == "kimi"


def test_openrouter_en_repli_sans_cle_kimi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISME_LLM_FOURNISSEUR", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    assert client_llm.fournisseur_llm() == "openrouter"


def test_fournisseur_force_par_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")
    monkeypatch.setenv("PRISME_LLM_FOURNISSEUR", "openrouter")
    assert client_llm.fournisseur_llm() == "openrouter"


def test_construire_modele_kimi_vise_l_api_kimi(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("langchain_openai")
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")
    monkeypatch.delenv("KIMI_API_BASE_URL", raising=False)

    modele = client_llm._construire_modele_kimi("moonshotai/kimi-k2.6", 120.0)

    assert modele.model_name == "kimi-k2.6"  # préfixe d'éditeur du catalogue OpenRouter retiré
    # URL de l'hôte d'API Kimi international — valeur technique, seul endpoint qui réponde.
    assert str(modele.openai_api_base).rstrip("/") == client_llm._KIMI_API_BASE_URL_PAR_DEFAUT


def test_aiguillage_vers_kimi_quand_il_est_le_fournisseur(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_FOURNISSEUR", "kimi")
    appels: list[str] = []
    monkeypatch.setattr(client_llm, "_construire_modele_kimi", lambda modele, timeout, **_: appels.append("kimi"))
    monkeypatch.setattr(
        client_llm, "_construire_modele_openrouter", lambda modele, timeout: appels.append("openrouter")
    )

    client_llm.construire_modele_pour_agent("analyste")

    assert appels == ["kimi"]


# --- Limiteur de concurrence (`PRISME_LLM_CONCURRENCE_MAX`) ------------------------------------
# Régression vécue : compte Kimi plafonné à une requête simultanée, erreur 429 « max organization
# concurrency: 1 » — l'Analyste et le Benchmarker partent en parallèle dans le graphe, l'un des
# deux épuisait ses tentatives pendant que l'autre occupait l'unique place.


class _CompteurConcurrence:
    """Appel factice qui mesure combien d'exécutions se chevauchent réellement."""

    def __init__(self, duree_s: float = 0.05) -> None:
        import threading

        self._verrou = threading.Lock()
        self.en_cours = 0
        self.maximum_observe = 0
        self.duree_s = duree_s

    def __call__(self) -> str:
        import time

        with self._verrou:
            self.en_cours += 1
            self.maximum_observe = max(self.maximum_observe, self.en_cours)
        time.sleep(self.duree_s)
        with self._verrou:
            self.en_cours -= 1
        return "ok"


def _lancer_en_parallele(appel, nombre: int) -> list[str]:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=nombre) as executeur:
        return list(executeur.map(lambda _: client_llm._avec_retry(appel)(), range(nombre)))


def test_sans_limite_les_appels_se_chevauchent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISME_LLM_CONCURRENCE_MAX", raising=False)
    compteur = _CompteurConcurrence()

    assert _lancer_en_parallele(compteur, 4) == ["ok"] * 4
    assert compteur.maximum_observe > 1  # comportement historique, aucune file d'attente


def test_limite_a_un_serialise_les_appels_simultanes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_CONCURRENCE_MAX", "1")
    compteur = _CompteurConcurrence()

    assert _lancer_en_parallele(compteur, 4) == ["ok"] * 4
    assert compteur.maximum_observe == 1


def test_limite_a_deux_autorise_deux_appels_au_plus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_CONCURRENCE_MAX", "2")
    compteur = _CompteurConcurrence()

    _lancer_en_parallele(compteur, 6)

    assert compteur.maximum_observe == 2


def test_limite_zero_equivaut_a_aucune_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_CONCURRENCE_MAX", "0")

    assert client_llm._limiteur_concurrence() is None


def test_limite_non_entiere_leve_une_erreur_explicite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_CONCURRENCE_MAX", "un")

    with pytest.raises(ValueError, match="PRISME_LLM_CONCURRENCE_MAX"):
        client_llm._avec_retry(lambda: "ok")()


def test_la_place_est_rendue_pendant_l_attente_de_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un appel qui échoue puis patiente avant de réessayer ne doit jamais garder la place du
    limiteur pendant son attente — sinon un seul appel en difficulté bloquerait tout le monde."""
    monkeypatch.setenv("PRISME_LLM_CONCURRENCE_MAX", "1")
    places_libres_pendant_attente: list[bool] = []

    def attente_observee(_delai: float) -> None:
        limiteur = client_llm._limiteur_concurrence()
        libre = limiteur.acquire(blocking=False)
        if libre:
            limiteur.release()
        places_libres_pendant_attente.append(libre)

    monkeypatch.setattr(client_llm.time, "sleep", attente_observee)

    class _ErreurTransitoire(Exception):
        status_code = 429

    tentatives = iter([_ErreurTransitoire(), "ok"])

    def appel_qui_echoue_une_fois() -> str:
        resultat = next(tentatives)
        if isinstance(resultat, Exception):
            raise resultat
        return resultat

    assert client_llm._avec_retry(appel_qui_echoue_une_fois)() == "ok"
    assert places_libres_pendant_attente == [True]


# --- Réflexion du modèle (`PRISME_LLM_REFLEXION`) ----------------------------------------------
# Mesuré : avec la réflexion, `kimi-k2.6` passe 5 à 16 min par appel de compréhension et 85 à
# 92 % de sa sortie est de la réflexion ; `{"thinking": {"type": "disabled"}}` ramène l'appel à
# 39 s — assez pour ne plus monopoliser la place unique d'un compte à concurrence 1.

_CORPS_SANS_REFLEXION = {"thinking": {"type": "disabled"}}


def _nettoyer_reflexion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISME_LLM_REFLEXION", raising=False)
    for agent in ("ANALYSTE", "COMPREHENSION", "GENERATEUR"):
        monkeypatch.delenv(f"PRISME_LLM_REFLEXION_{agent}", raising=False)


def test_reflexion_active_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    _nettoyer_reflexion(monkeypatch)

    assert client_llm._reflexion_desactivee("comprehension") is False


def test_reflexion_desactivee_globalement(monkeypatch: pytest.MonkeyPatch) -> None:
    _nettoyer_reflexion(monkeypatch)
    monkeypatch.setenv("PRISME_LLM_REFLEXION", "desactivee")

    assert client_llm._reflexion_desactivee("comprehension") is True
    assert client_llm._reflexion_desactivee(None) is True


def test_surcharge_par_agent_l_emporte_sur_le_reglage_global(monkeypatch: pytest.MonkeyPatch) -> None:
    _nettoyer_reflexion(monkeypatch)
    monkeypatch.setenv("PRISME_LLM_REFLEXION", "desactivee")
    monkeypatch.setenv("PRISME_LLM_REFLEXION_GENERATEUR", "activee")

    assert client_llm._reflexion_desactivee("generateur") is False
    assert client_llm._reflexion_desactivee("analyste") is True


def test_surcharge_vide_retombe_sur_le_reglage_global(monkeypatch: pytest.MonkeyPatch) -> None:
    _nettoyer_reflexion(monkeypatch)
    monkeypatch.setenv("PRISME_LLM_REFLEXION", "desactivee")
    monkeypatch.setenv("PRISME_LLM_REFLEXION_ANALYSTE", "")  # déclarée vide, comme dans un .env

    assert client_llm._reflexion_desactivee("analyste") is True


def test_valeur_de_reflexion_inconnue_leve_une_erreur_explicite(monkeypatch: pytest.MonkeyPatch) -> None:
    _nettoyer_reflexion(monkeypatch)
    monkeypatch.setenv("PRISME_LLM_REFLEXION", "peut-etre")

    with pytest.raises(ValueError, match="PRISME_LLM_REFLEXION"):
        client_llm._reflexion_desactivee("analyste")


def test_kimi_sans_reflexion_envoie_le_parametre_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("langchain_openai")
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")

    modele = client_llm._construire_modele_kimi("kimi-k2.6", 120.0, reflexion_desactivee=True)

    assert modele.extra_body == _CORPS_SANS_REFLEXION


def test_kimi_avec_reflexion_n_envoie_rien_de_plus(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("langchain_openai")
    monkeypatch.setenv("KIMI_API_KEY", "sk-test")

    modele = client_llm._construire_modele_kimi("kimi-k2.6", 120.0)

    assert not modele.extra_body


def test_openrouter_ne_recoit_jamais_le_parametre_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("langchain_openai")
    monkeypatch.setenv("PRISME_LLM_FOURNISSEUR", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    modele = client_llm._construire_modele_fournisseur("moonshotai/kimi-k2.6", 120.0, reflexion_desactivee=True)

    assert not modele.extra_body


def test_construire_modele_pour_agent_applique_le_reglage_de_l_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _nettoyer_reflexion(monkeypatch)
    monkeypatch.setenv("PRISME_LLM_FOURNISSEUR", "kimi")
    monkeypatch.setenv("PRISME_LLM_REFLEXION_COMPREHENSION", "desactivee")
    reglages: list[bool] = []
    monkeypatch.setattr(
        client_llm,
        "_construire_modele_kimi",
        lambda modele, timeout, *, reflexion_desactivee=False: reglages.append(reflexion_desactivee),
    )

    client_llm.construire_modele_pour_agent("comprehension")
    client_llm.construire_modele_pour_agent("analyste")

    assert reglages == [True, False]
