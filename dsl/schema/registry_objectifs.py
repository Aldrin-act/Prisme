"""Registry extensible pour les objectifs — permet d'enregistrer de nouveaux
objectifs sans modifier le code core du DSL.

Pattern similaire au registry des contraintes proposé précédemment.
"""

from __future__ import annotations

from typing import Any, Callable, Type

from pydantic import BaseModel


class RegistryObjectifs:
    """Registry pour objectifs extensibles.

    Permet à chaque client d'enregistrer ses propres objectifs métier sans
    toucher au code du DSL de base.
    """

    _objectifs: dict[str, Type[BaseModel]] = {}
    _validateurs: dict[str, Callable[[BaseModel], list[str]]] = {}
    _metadata: dict[str, dict[str, Any]] = {}

    @classmethod
    def enregistrer(
        cls,
        nom: str,
        modele: Type[BaseModel],
        validateur: Callable[[BaseModel], list[str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Enregistre un nouveau type d'objectif.

        Args:
            nom: Type discriminateur (ex: "minimiser_cout_total")
            modele: Classe Pydantic de l'objectif
            validateur: Fonction optionnelle retournant des warnings
            metadata: Métadonnées (description longue, catégorie, etc.)

        Example:
            >>> class MinimiserCout(BaseModel):
            ...     type: Literal["minimiser_cout"] = "minimiser_cout"
            ...     cout_par_minute: float = 1.0
            >>> RegistryObjectifs.enregistrer("minimiser_cout", MinimiserCout)
        """
        if nom in cls._objectifs:
            raise ValueError(f"Objectif {nom!r} déjà enregistré")

        cls._objectifs[nom] = modele

        if validateur:
            cls._validateurs[nom] = validateur

        cls._metadata[nom] = metadata or {}

    @classmethod
    def obtenir(cls, nom: str) -> Type[BaseModel]:
        """Récupère un type d'objectif enregistré."""
        if nom not in cls._objectifs:
            raise ValueError(
                f"Type d'objectif inconnu: {nom!r}. "
                f"Disponibles: {sorted(cls._objectifs.keys())}"
            )
        return cls._objectifs[nom]

    @classmethod
    def types_disponibles(cls) -> list[str]:
        """Liste tous les types d'objectifs enregistrés."""
        return sorted(cls._objectifs.keys())

    @classmethod
    def valider(cls, objectif: BaseModel) -> list[str]:
        """Valide un objectif et retourne des avertissements éventuels.

        Returns:
            Liste d'avertissements (vide si tout est OK)
        """
        if not hasattr(objectif, "type"):
            return ["Objectif sans champ 'type'"]

        type_obj = getattr(objectif, "type")
        validateur = cls._validateurs.get(type_obj)

        if validateur:
            return validateur(objectif)

        return []

    @classmethod
    def obtenir_metadata(cls, nom: str) -> dict[str, Any]:
        """Récupère les métadonnées d'un type d'objectif."""
        return cls._metadata.get(nom, {})

    @classmethod
    def objectifs_par_categorie(cls) -> dict[str, list[str]]:
        """Regroupe les objectifs par catégorie (selon metadata)."""
        par_categorie: dict[str, list[str]] = {}

        for nom, metadata in cls._metadata.items():
            categorie = metadata.get("categorie", "autre")
            if categorie not in par_categorie:
                par_categorie[categorie] = []
            par_categorie[categorie].append(nom)

        return par_categorie

    @classmethod
    def reinitialiser(cls) -> None:
        """Réinitialise le registry (utilisé principalement en tests)."""
        cls._objectifs.clear()
        cls._validateurs.clear()
        cls._metadata.clear()


# Bootstrap : enregistrer les objectifs de base
def _enregistrer_objectifs_base() -> None:
    """Enregistre les objectifs fournis par défaut dans PRISME."""
    from .objectifs_parametrables import (
        EquilibrerCharge,
        MaximiserUtilisation,
        MinimiserChangements,
        MinimiserMakespan,
        MinimiserRetards,
    )

    RegistryObjectifs.enregistrer(
        "minimiser_makespan",
        MinimiserMakespan,
        metadata={
            "categorie": "temps",
            "description": "Minimise la durée totale du planning",
            "conflit_potentiel": ["equilibrer_charge"],
        },
    )

    RegistryObjectifs.enregistrer(
        "equilibrer_charge",
        EquilibrerCharge,
        metadata={
            "categorie": "ressources",
            "description": "Équilibre la charge entre ressources",
            "conflit_potentiel": ["minimiser_makespan"],
        },
    )

    RegistryObjectifs.enregistrer(
        "minimiser_retards",
        MinimiserRetards,
        metadata={
            "categorie": "delais",
            "description": "Minimise les retards par rapport aux échéances",
            "necessite_contraintes": ["echeance"],
        },
    )

    RegistryObjectifs.enregistrer(
        "maximiser_utilisation",
        MaximiserUtilisation,
        metadata={
            "categorie": "ressources",
            "description": "Maximise le taux d'utilisation des ressources",
        },
    )

    RegistryObjectifs.enregistrer(
        "minimiser_changements",
        MinimiserChangements,
        metadata={
            "categorie": "efficacite",
            "description": "Minimise les changements de ressources",
        },
    )


# Enregistrement automatique au chargement du module
_enregistrer_objectifs_base()
