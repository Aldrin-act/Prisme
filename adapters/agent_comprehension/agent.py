"""Agent de compréhension (§5.4 bis) — propose une traduction de données ERP
brutes (n'importe quel format : CSV, dump JSON, texte libre...) vers le JSON
T-R-C-O canonique, pour un ERP sans adaptateur écrit à la main dédié.

Ne remplace jamais le garde-fou déterministe (§6.7) : la sortie de cet agent
passe par exactement la même validation (`api.input_validation.valider_payload_trco`
→ `InstanceTRCO`) que n'importe quel autre payload T-R-C-O, qu'il vienne
d'un humain, d'un `translator.py` écrit à la main, ou d'ici. Cette
validation attrape les incohérences structurelles (identifiants dupliqués,
tâche sans compatibilité...) mais pas une erreur d'interprétation
sémantique — d'où `avertissements`, que l'agent remplit pour tout ce dont
il n'est pas certain, à faire vérifier par un humain avant de faire
confiance au planning qui en résultera.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_args

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from dsl.schema import Contrainte, Objectif
from generation.agents.base import ErreurReponseAgentInvalide, extraire_texte_brut
from generation.agents.client_llm import _avec_retry

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parent / "prompts" / "comprehension.md"
CHEMIN_REGLES_DSL = Path(__file__).resolve().parents[2] / "docs" / "dsl" / "modele_ingestion_client.md"

# Seuil `difflib` : assez haut pour ne corriger que de vraies fautes d'orthographe/traduction du
# LLM sur le tag discriminant `type` ("minimizer_makespan" -> "minimiser_makespan"), jamais assez
# permissif pour faire correspondre deux types réellement différents entre eux.
_SEUIL_CORRESPONDANCE_TYPE = 0.6


def _valeurs_type_valides(union_annote: Any) -> tuple[str, ...]:
    """Extrait par introspection les valeurs `Literal` du champ discriminant `type` de chaque
    membre d'une union annotée façon `Contrainte`/`Objectif` (`dsl/schema`) — jamais recopiées à la
    main, pour ne jamais désynchroniser cette liste du DSL réel si un type est ajouté/retiré."""
    membres = get_args(get_args(union_annote)[0])
    return tuple(get_args(membre.model_fields["type"].annotation)[0] for membre in membres)


def _corriger_types_dsl(entrees: list[Any], valeurs_valides: tuple[str, ...], categorie: str) -> list[str]:
    """Corrige en place le champ `type` de chaque entrée (dict) dont la valeur ne correspond à
    aucun type DSL connu mais s'en approche assez pour qu'il s'agisse manifestement d'une faute du
    LLM plutôt que d'un type réellement différent — jamais une réinterprétation sémantique, juste
    une correction orthographique. Une entrée sans correspondance suffisamment proche est laissée
    intacte : la validation `InstanceTRCO` en aval reste l'arbitre final, honnête, de ce cas.
    Retourne la liste des corrections effectuées (pour transparence dans `avertissements`)."""
    corrections: list[str] = []
    for entree in entrees:
        if not isinstance(entree, dict):
            continue
        type_fourni = entree.get("type")
        if not isinstance(type_fourni, str) or type_fourni in valeurs_valides:
            continue
        correspondance = difflib.get_close_matches(
            type_fourni, valeurs_valides, n=1, cutoff=_SEUIL_CORRESPONDANCE_TYPE
        )
        if correspondance:
            entree["type"] = correspondance[0]
            corrections.append(f"{categorie} : type {type_fourni!r} corrigé en {correspondance[0]!r}")
    return corrections


_PROMPT_SYSTEME = (
    "Tu es un analyste d'intégration de données spécialisé dans la traduction de formats ERP "
    "propriétaires vers un format d'ordonnancement canonique. Tu réponds toujours en JSON strict, "
    "jamais en texte libre."
)


class _SchemaJustification(BaseModel):
    contrainte: str = Field(description="La contrainte produite (ex: 'precedence: T1 → T2').")
    raison: str = Field(description="Citation exacte du champ des données brutes qui l'a justifiée.")


class _SchemaComprehension(BaseModel):
    # `dict[str, Any]` volontairement : le schéma T-R-C-O réel (union discriminée
    # de contraintes, axes optionnels...) n'est jamais dupliqué ici — la seule
    # validation qui compte est celle, déterministe, d'`InstanceTRCO` en aval
    # (§6.7, `api.input_validation.valider_payload_trco`), jamais une contrainte
    # imposée au LLM au moment de la génération.
    instance: dict[str, Any] = Field(description="Instance T-R-C-O candidate, format canonique.")
    description_metier: str = Field(
        description="Description du processus métier tel qu'il ressort des données brutes fournies "
        "(nature du processus, étapes, acteurs) — jamais de contexte non mentionné dans les données."
    )
    avertissements: list[str] = Field(
        default_factory=list, description="Incertitudes à faire vérifier par un humain."
    )
    justifications: list[_SchemaJustification] = Field(default_factory=list)


@dataclass(frozen=True)
class Justification:
    contrainte: str
    raison: str


@dataclass(frozen=True)
class ResultatComprehension:
    reponse_brute: str
    instance_brute: dict[str, Any]
    description_metier: str
    avertissements: tuple[str, ...]
    # Une entrée par contrainte precedence/echeance/competence_requise produite
    # (pas compatibilite_ressource_tache, trop nombreuses) — citant le champ
    # des données brutes qui l'a justifiée, pour qu'un humain puisse vérifier
    # la déduction sans relire tout le fichier source (voir prompts/comprehension.md).
    justifications: tuple[Justification, ...]


def comprendre_donnees_erp(
    modele: BaseChatModel, donnees_brutes: str, secteur_activite: str | None = None
) -> ResultatComprehension:
    """`secteur_activite` (optionnel) : contexte métier fourni explicitement
    par l'utilisateur, jamais deviné par l'agent (voir `comprehension.md`)
    — absent du prompt (chaîne vide) si `None`, jamais interpolé comme la
    chaîne littérale "None"."""
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    regles_dsl = CHEMIN_REGLES_DSL.read_text(encoding="utf-8")
    bloc_secteur = (
        f"## Secteur d'activité déclaré par le client\n\n{secteur_activite}\n"
        if secteur_activite is not None
        else ""
    )
    prompt = gabarit.format(regles_dsl=regles_dsl, donnees_brutes=donnees_brutes, secteur_activite=bloc_secteur)

    # `method="json_mode"` explicite plutôt que `methode_sortie_structuree(modele)` — même valeur
    # aujourd'hui (Kimi, comme le reste du pipeline), mais gardé en dur ici volontairement :
    # `instance: dict[str, Any]` est libre sans `properties` (voir plus haut), et le mode schéma
    # strict (`"json_schema"`) s'était avéré, empiriquement avec l'ancien fournisseur (Mistral),
    # renvoyer un `instance` vide ({}) pour ce genre de schéma sans propriétés déclarées — un
    # schéma JSON sous contrainte stricte semblant se réduire à l'objet minimal valide plutôt que
    # d'être rempli. Pas revérifié contre Kimi ; `json_mode`, sans contrainte de grammaire token
    # par token, reste le choix le plus sûr ici tant que ce n'est pas revalidé par un appel réel.
    structure = modele.with_structured_output(_SchemaComprehension, include_raw=True, method="json_mode")
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    corrections = [
        *_corriger_types_dsl(
            donnees.instance.get("contraintes") or [], _valeurs_type_valides(Contrainte), "contrainte"
        ),
        *_corriger_types_dsl(donnees.instance.get("objectifs") or [], _valeurs_type_valides(Objectif), "objectif"),
    ]
    return ResultatComprehension(
        reponse_brute=reponse_brute,
        instance_brute=donnees.instance,
        description_metier=donnees.description_metier,
        avertissements=(*donnees.avertissements, *corrections),
        justifications=tuple(
            Justification(contrainte=j.contrainte, raison=j.raison) for j in donnees.justifications
        ),
    )
