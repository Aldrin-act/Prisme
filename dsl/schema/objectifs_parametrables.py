"""O — Objectifs paramétrables : permettent de configurer le comportement
d'optimisation sans changer le code du solveur.

Chaque objectif peut avoir des paramètres qui influencent son importance
relative, ses seuils, ou son comportement.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class MinimiserMakespan(BaseModel):
    """Minimiser la date de fin de la dernière opération du planning.

    Nouveau : paramètres configurables pour affiner le comportement.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["minimiser_makespan"] = "minimiser_makespan"

    # NOUVEAUX PARAMÈTRES
    poids: float = Field(
        default=1.0,
        ge=0.0,
        description="Importance relative de cet objectif (pour objectifs multiples pondérés)"
    )
    makespan_cible: int | None = Field(
        default=None,
        ge=0,
        description="Makespan cible optionnel - le solveur peut arrêter dès qu'il l'atteint"
    )
    penalite_depassement: float = Field(
        default=1.0,
        ge=0.0,
        description="Pénalité appliquée pour chaque minute au-delà de makespan_cible"
    )


class EquilibrerCharge(BaseModel):
    """Équilibrer la charge de travail entre les ressources.

    Minimise l'écart entre la ressource la plus chargée et la moins chargée.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["equilibrer_charge"] = "equilibrer_charge"

    poids: float = Field(default=1.0, ge=0.0)

    methode: Literal["ecart_max", "variance", "gini"] = Field(
        default="ecart_max",
        description=(
            "Méthode de calcul de l'équilibrage:\n"
            "- ecart_max: minimise (max_charge - min_charge)\n"
            "- variance: minimise la variance des charges\n"
            "- gini: minimise le coefficient de Gini (0=parfaitement équilibré, 1=totalement déséquilibré)"
        )
    )

    ressources_cibles: list[str] | None = Field(
        default=None,
        description="Si spécifié, équilibre uniquement ces ressources (sinon toutes)"
    )


class MinimiserRetards(BaseModel):
    """Minimiser les retards par rapport aux échéances définies.

    Travaille en conjonction avec les contraintes Echeance.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["minimiser_retards"] = "minimiser_retards"

    poids: float = Field(default=1.0, ge=0.0)

    fonction_penalite: Literal["lineaire", "quadratique", "exponentielle"] = Field(
        default="lineaire",
        description=(
            "Fonction de pénalité appliquée au retard:\n"
            "- lineaire: penalite = retard\n"
            "- quadratique: penalite = retard²\n"
            "- exponentielle: penalite = e^retard - 1"
        )
    )

    priorite_par_tache: dict[str, float] = Field(
        default_factory=dict,
        description="Poids spécifique par tâche (défaut: 1.0 pour toutes)"
    )

    seuil_grace: int = Field(
        default=0,
        ge=0,
        description="Jours de grâce avant que le retard ne soit pénalisé"
    )


class MaximiserUtilisation(BaseModel):
    """Maximiser le taux d'utilisation des ressources.

    Minimise le temps d'inactivité total des ressources.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["maximiser_utilisation"] = "maximiser_utilisation"

    poids: float = Field(default=1.0, ge=0.0)

    ressources_prioritaires: list[str] = Field(
        default_factory=list,
        description="Ressources à privilégier (poids plus élevé pour leur utilisation)"
    )

    penalite_inactivite_par_ressource: dict[str, float] = Field(
        default_factory=dict,
        description="Pénalité d'inactivité par ressource (défaut: 1.0)"
    )


class MinimiserChangements(BaseModel):
    """Minimiser le nombre de changements de ressource entre tâches successives.

    Réduit les coûts de setup/changement de série.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["minimiser_changements"] = "minimiser_changements"

    poids: float = Field(default=1.0, ge=0.0)

    cout_changement_par_ressource: dict[str, float] = Field(
        default_factory=dict,
        description="Coût unitaire de changement par ressource (défaut: 1.0)"
    )

    cout_changement_par_paire: dict[tuple[str, str], float] = Field(
        default_factory=dict,
        description="Coût spécifique pour passer de la ressource A à B"
    )


# Union discriminée des objectifs (extensible)
Objectif = Annotated[
    MinimiserMakespan
    | EquilibrerCharge
    | MinimiserRetards
    | MaximiserUtilisation
    | MinimiserChangements,
    Field(discriminator="type"),
]
