"""Durée de travail quotidienne d'une ressource (`Ressource.heures_par_jour`) → indisponibilités.

Une ressource qui travaille 8 h par jour n'est pas disponible les 16 autres heures : plutôt
qu'un nouveau mécanisme, cette information devient une `ContrainteDisponibiliteRessource`
ordinaire, dérivée ici, à l'ingestion (même principe que la dérivation des compatibilités par
compétence, `adapters/competence_derivation.py`). Le DSL, le solveur généré et le vérificateur de
faisabilité n'ont donc rien de nouveau à connaître : ils voient une indisponibilité récurrente
comme n'importe quelle autre.

Convention retenue : la journée de travail commence à la position 0 de chaque journée du cycle —
les `heures_par_jour` premières heures de chaque journée sont travaillées, les suivantes non.
Aligner ça sur un vrai horaire (ex. 8 h–16 h) reste le travail d'un adaptateur en amont, qui sait
à quel instant réel correspond l'instant 0 de l'instance (voir `dsl/schema/contraintes.py`, aucune
date calendaire dans le DSL).

Ne s'applique qu'à une instance en **heures** (`InstanceTRCO.unite_temps`) : en mode jours, le
cycle ne compte que 7 positions d'une journée entière, une fraction de journée n'y est pas
exprimable — la valeur reste alors purement informative, signalée par un avertissement plutôt
qu'appliquée de travers.
"""

from __future__ import annotations

from typing import Literal

from dsl.schema import Contrainte, ContrainteDisponibiliteRessource, Ressource

HEURES_PAR_JOUR_COMPLET = 24
_CYCLE_HEURES = 7 * HEURES_PAR_JOUR_COMPLET


def deriver_disponibilites_horaires(
    ressources: list[Ressource],
    contraintes_existantes: list[Contrainte],
    unite_temps: Literal["jours", "heures"] = "jours",
) -> tuple[list[Contrainte], list[str]]:
    """Renvoie `(contraintes dérivées, avertissements)`.

    Une ressource déjà couverte par une `ContrainteDisponibiliteRessource` explicite n'est jamais
    doublée : la déclaration explicite l'emporte (même règle que les échéances dérivées d'une
    commande), et la divergence est signalée."""
    derivees: list[Contrainte] = []
    avertissements: list[str] = []
    deja_declarees = {
        c.ressource for c in contraintes_existantes if isinstance(c, ContrainteDisponibiliteRessource)
    }

    for ressource in ressources:
        heures = ressource.heures_par_jour
        if heures is None or heures >= HEURES_PAR_JOUR_COMPLET:
            continue
        if unite_temps != "heures":
            avertissements.append(
                f"ressource {ressource.id!r} : heures_par_jour={heures} n'est pas appliqué — l'instance est "
                f"en jours, où une fraction de journée n'est pas exprimable. Valeur conservée à titre "
                f"informatif ; ré-importer en heures pour qu'elle soit prise en compte."
            )
            continue
        if ressource.id in deja_declarees:
            avertissements.append(
                f"ressource {ressource.id!r} : heures_par_jour={heures} ignoré — une disponibilité explicite "
                f"est déjà déclarée pour cette ressource, elle l'emporte."
            )
            continue
        positions = [p for p in range(_CYCLE_HEURES) if p % HEURES_PAR_JOUR_COMPLET >= heures]
        derivees.append(
            ContrainteDisponibiliteRessource(ressource=ressource.id, jours_semaine_indisponibles=positions)
        )
        avertissements.append(
            f"ressource {ressource.id!r} : journée de travail de {heures} h — indisponible les "
            f"{HEURES_PAR_JOUR_COMPLET - heures} h restantes de chaque journée (indisponibilité dérivée)."
        )
    return derivees, avertissements
