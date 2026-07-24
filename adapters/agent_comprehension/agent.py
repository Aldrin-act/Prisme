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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generation.agents.base import extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parent / "prompts" / "comprehension.md"
CHEMIN_REGLES_DSL = Path(__file__).resolve().parents[2] / "docs" / "dsl" / "modele_ingestion_client.md"

_PROMPT_SYSTEME = (
    "Tu es un analyste d'intégration de données spécialisé dans la traduction de formats ERP "
    "propriétaires vers un format d'ordonnancement canonique. Tu réponds toujours en JSON strict, "
    "jamais en texte libre."
)


@dataclass(frozen=True)
class Justification:
    contrainte: str
    raison: str


@dataclass(frozen=True)
class ResultatComprehension:
    reponse_brute: str
    instance_brute: dict[str, Any]
    avertissements: tuple[str, ...]
    # Une entrée par contrainte precedence/echeance/competence_requise produite
    # (pas compatibilite_ressource_tache, trop nombreuses) — citant le champ
    # des données brutes qui l'a justifiée, pour qu'un humain puisse vérifier
    # la déduction sans relire tout le fichier source (voir prompts/comprehension.md).
    justifications: tuple[Justification, ...]


def comprendre_donnees_erp(appel_llm: AppelLLM, donnees_brutes: str) -> ResultatComprehension:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    regles_dsl = CHEMIN_REGLES_DSL.read_text(encoding="utf-8")
    prompt = gabarit.format(regles_dsl=regles_dsl, donnees_brutes=donnees_brutes)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)
    return ResultatComprehension(
        reponse_brute=reponse,
        instance_brute=donnees["instance"],
        avertissements=tuple(donnees.get("avertissements", [])),
        justifications=tuple(
            Justification(contrainte=j["contrainte"], raison=j["raison"])
            for j in donnees.get("justifications", [])
        ),
    )
