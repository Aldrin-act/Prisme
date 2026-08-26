"""Couche 1 (§6.1) : `analyste.analyser_mission` construit correctement son
`ResultatAnalyse` depuis une sortie structurée — aucun appel LLM réel (voir
`tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import analyste
from tests.unit.aides_test_agents import ModeleFactice


def test_analyser_mission_construit_le_resultat_depuis_le_schema() -> None:
    schema = analyste._SchemaAnalyse(
        entrees="Instance T-R-C-O", sorties="Planning", contraintes_a_couvrir=["c1", "c2"]
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = analyste.analyser_mission(modele)

    assert resultat.entrees == "Instance T-R-C-O"
    assert resultat.sorties == "Planning"
    assert resultat.contraintes_a_couvrir == ("c1", "c2")
    assert "### Entrées" in resultat.en_texte()


def test_analyser_mission_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(analyste.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        analyste.analyser_mission(modele)


def test_extraire_structure_instance_isole_les_types_distincts_et_tries() -> None:
    instance_json = {
        "taches": [{"id": "T1"}, {"id": "T2"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 5},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    structure = analyste.extraire_structure_instance(instance_json)

    assert structure.types_contraintes == ("compatibilite_ressource_tache", "precedence")
    assert structure.types_objectifs == ("minimiser_makespan",)
    assert structure.nb_taches == 2
    assert structure.nb_ressources == 1


def test_extraire_structure_instance_gere_une_instance_sans_contraintes_ni_objectifs() -> None:
    structure = analyste.extraire_structure_instance({})

    assert structure.types_contraintes == ()
    assert structure.types_objectifs == ()
    assert structure.nb_taches == 0
    assert structure.nb_ressources == 0


class _ModeleFacticeCapturant(ModeleFactice):
    """Capture le dernier prompt envoyé, pour vérifier son contenu sans dépendre d'un vrai appel LLM."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.dernier_prompt: str | None = None

    def with_structured_output(self, schema: type, include_raw: bool = True, method: str | None = None):
        runnable = super().with_structured_output(schema, include_raw, method)
        invoke_original = runnable.invoke

        def invoke_capturant(messages):
            self.dernier_prompt = messages[-1].content
            return invoke_original(messages)

        runnable.invoke = invoke_capturant
        return runnable


def test_analyser_mission_injecte_la_structure_de_linstance_dans_le_prompt() -> None:
    """`avec_outils=False` : ce test porte sur le contenu du prompt, pas sur
    la boucle d'outils — sans quoi le dernier message capturé dépendrait de
    la disponibilité réelle de Postgres sur la machine de test (voir
    `construire_outil_instances_similaires`), que `tests/unit` ne doit
    jamais présumer (§ « Layer 1 » de `CLAUDE.md`)."""
    schema = analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=["c"])
    modele = _ModeleFacticeCapturant(raw_content=json.dumps(schema.model_dump()), parsed=schema)
    instance_json = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "precedence", "avant": "T1", "apres": "T1"}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    analyste.analyser_mission(modele, instance_json, avec_outils=False)

    assert "precedence" in modele.dernier_prompt
    assert "minimiser_makespan" in modele.dernier_prompt
    assert "1 tâche" in modele.dernier_prompt or "1 ressource" in modele.dernier_prompt


def test_analyser_mission_sans_instance_ne_leve_pas() -> None:
    """Appelants historiques sans instance sous la main (scripts, tests) — `instance_json`
    optionnel, ne doit jamais faire planter la construction du prompt."""
    schema = analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=[])
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = analyste.analyser_mission(modele)

    assert resultat.entrees == "e"


def test_analyser_mission_sans_instance_a_une_trace_d_appels_vide() -> None:
    schema = analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=[])
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = analyste.analyser_mission(modele)

    assert resultat.appels_outils == ()


def test_analyser_mission_avec_instance_a_une_trace_vide_quand_le_faux_modele_naapelle_aucun_outil(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le faux modèle (`bind_tools` simulé, voir `aides_test_agents.py`) ne
    demande jamais d'outil, qu'un outil ait pu être construit ou non —
    `analyser_mission` doit quand même produire une réponse. Le registre est
    forcé à échouer (monkeypatch) : `tests/unit` ne doit jamais dépendre
    d'une vraie base Postgres, disponible ou non sur la machine de test
    (§ « Layer 1 » de `CLAUDE.md`)."""
    import solver_store.registry as registry_module

    def _leve(*args: object, **kwargs: object) -> None:
        raise ConnectionError("base injoignable (test)")

    monkeypatch.setattr(registry_module, "Registre", _leve)

    schema = analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=["c"])
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)
    instance_json = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "precedence", "avant": "T1", "apres": "T1"}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    resultat = analyste.analyser_mission(modele, instance_json, client_id="client-1")

    assert resultat.appels_outils == ()
    assert resultat.entrees == "e"


def test_analyser_mission_avec_outils_faux_ne_construit_aucun_outil(monkeypatch: pytest.MonkeyPatch) -> None:
    """`avec_outils=False` : le registre ne doit même pas être sollicité."""

    def _echoue_si_appele(*args: object, **kwargs: object) -> None:
        raise AssertionError("construire_outil_instances_similaires ne doit pas être appelé")

    monkeypatch.setattr(analyste, "construire_outil_instances_similaires", _echoue_si_appele)
    schema = analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=[])
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)
    instance_json = {"taches": [{"id": "T1"}], "ressources": [], "contraintes": [], "objectifs": []}

    resultat = analyste.analyser_mission(modele, instance_json, avec_outils=False)

    assert resultat.appels_outils == ()


class TestStructureEtSignatureChaines:
    """`_structure_contraintes_str`/`_signature_objectifs_str` — même format
    exact que `api/etat.py::structure_contraintes`/`signature_objectifs`
    (clé de matching du registre), recalculé sur le `dict` brut."""

    def test_structure_contraintes_triee_et_jointe(self) -> None:
        instance_json = {
            "contraintes": [
                {"type": "precedence"},
                {"type": "compatibilite_ressource_tache"},
                {"type": "precedence"},
            ]
        }
        assert analyste._structure_contraintes_str(instance_json) == "compatibilite_ressource_tache,precedence"

    def test_structure_contraintes_vide_vaut_aucune(self) -> None:
        assert analyste._structure_contraintes_str({}) == "aucune"

    def test_signature_objectifs_triee_et_jointe(self) -> None:
        instance_json = {"objectifs": [{"type": "minimiser_makespan"}, {"type": "equilibrer_charge"}]}
        assert analyste._signature_objectifs_str(instance_json) == "equilibrer_charge,minimiser_makespan"

    def test_signature_objectifs_vide_est_une_chaine_vide(self) -> None:
        assert analyste._signature_objectifs_str({}) == ""


class _SolveurFactice:
    def __init__(self, client_id: str | None) -> None:
        self.client_id = client_id


class TestResumerSolveursSimilaires:
    """`_resumer_solveurs_similaires` — fonction pure derrière l'outil LLM,
    testable sans registre réel."""

    def test_aucun_solveur(self) -> None:
        resultat = analyste._resumer_solveurs_similaires([], client_id="client-1")
        assert "Aucun solveur" in resultat

    def test_compte_les_solveurs_du_meme_client_separement(self) -> None:
        solveurs = [_SolveurFactice("client-1"), _SolveurFactice("client-1"), _SolveurFactice("client-2")]
        resultat = analyste._resumer_solveurs_similaires(solveurs, client_id="client-1")
        assert "3 solveur(s)" in resultat
        assert "2 pour ce client précis" in resultat
        assert "1 pour d'autres clients" in resultat

    def test_sans_client_id_aucun_ne_compte_comme_meme_client(self) -> None:
        solveurs = [_SolveurFactice("client-1"), _SolveurFactice(None)]
        resultat = analyste._resumer_solveurs_similaires(solveurs, client_id=None)
        assert "0 pour ce client précis" in resultat
        assert "2 pour d'autres clients" in resultat


def test_construire_outil_instances_similaires_degrade_en_silence_si_registre_injoignable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Registre.__init__` lève (base injoignable/mal configurée) — ne doit
    jamais remonter, seulement dégrader vers `None` (voir docstring de
    `construire_outil_instances_similaires`). Force l'échec via monkeypatch
    plutôt que de compter sur l'absence de Postgres dans l'environnement de
    test, qui n'est pas garantie (voir `docker-compose.yml`)."""
    import solver_store.registry as registry_module

    def _leve(*args: object, **kwargs: object) -> None:
        raise ConnectionError("base injoignable (test)")

    monkeypatch.setattr(registry_module, "Registre", _leve)

    outil = analyste.construire_outil_instances_similaires("precedence", "minimiser_makespan", "client-1")

    assert outil is None


def test_construire_outil_instances_similaires_interroge_le_registre_avec_la_bonne_cle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le registre est interrogé une fois construit — `client_id` filtre le
    résumé (voir `_resumer_solveurs_similaires`), jamais la requête au
    registre elle-même (recherche par structure/objectifs uniquement, tous
    clients confondus — voir docstring de `construire_outil_instances_similaires`)."""
    import solver_store.registry as registry_module

    appels: list[dict] = []

    class _RegistreFactice:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def rechercher_solveurs(self, **kwargs: object) -> list:
            appels.append(kwargs)
            return [_SolveurFactice("client-1")]

    monkeypatch.setattr(registry_module, "Registre", _RegistreFactice)

    outil = analyste.construire_outil_instances_similaires("precedence", "minimiser_makespan", "client-1")

    assert outil is not None
    resultat = outil.invoke({})
    assert appels == [
        {"client_id": None, "structure_contraintes": "precedence", "signature_objectifs": "minimiser_makespan"}
    ]
    assert "1 solveur(s)" in resultat
    assert "1 pour ce client précis" in resultat
