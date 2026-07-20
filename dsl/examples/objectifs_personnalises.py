"""Exemples d'objectifs personnalisés par client.

Montre comment étendre le système d'objectifs sans modifier le code core.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dsl.schema.registry_objectifs import RegistryObjectifs


# ============================================================================
# Exemple 1 : Client BARAA - Objectif métier spécifique
# ============================================================================


class MinimiserCoutTotal(BaseModel):
    """Objectif personnalisé BARAA : minimiser le coût total du planning.

    Prend en compte :
    - Coût horaire par ressource
    - Coûts de setup
    - Pénalités de retard
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["minimiser_cout_total"] = "minimiser_cout_total"

    poids: float = Field(default=1.0, ge=0.0)

    cout_horaire_par_ressource: dict[str, float] = Field(
        default_factory=dict,
        description="Coût horaire d'utilisation de chaque ressource (€/h)"
    )

    cout_setup_par_changement: dict[str, float] = Field(
        default_factory=dict,
        description="Coût fixe de changement de série par ressource (€)"
    )

    penalite_retard_par_jour: float = Field(
        default=100.0,
        ge=0.0,
        description="Pénalité financière par jour de retard (€/jour)"
    )

    cout_inactivite_par_heure: float = Field(
        default=10.0,
        ge=0.0,
        description="Coût d'inactivité d'une ressource (€/h)"
    )


# Enregistrer l'objectif personnalisé BARAA
RegistryObjectifs.enregistrer(
    "minimiser_cout_total",
    MinimiserCoutTotal,
    metadata={
        "categorie": "economique",
        "description": "Minimise le coût total (ressources + setup + pénalités)",
        "client": "BARAA",
    },
)


# ============================================================================
# Exemple 2 : Client avec contraintes environnementales
# ============================================================================


class MinimiserEmpreinteCO2(BaseModel):
    """Objectif environnemental : minimiser les émissions CO2 du planning."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["minimiser_empreinte_co2"] = "minimiser_empreinte_co2"

    poids: float = Field(default=1.0, ge=0.0)

    emission_co2_par_ressource_par_heure: dict[str, float] = Field(
        default_factory=dict,
        description="Émissions CO2 par heure d'utilisation (kg CO2/h)"
    )

    emission_co2_par_changement: dict[str, float] = Field(
        default_factory=dict,
        description="Émissions CO2 liées au changement de série (kg CO2)"
    )

    seuil_alerte_co2: float | None = Field(
        default=None,
        ge=0.0,
        description="Seuil d'alerte CO2 total (kg) - génère un warning si dépassé"
    )


def validateur_co2(objectif: MinimiserEmpreinteCO2) -> list[str]:
    """Validateur pour l'objectif CO2."""
    avertissements = []

    if not objectif.emission_co2_par_ressource_par_heure:
        avertissements.append(
            "Aucune émission CO2 renseignée par ressource - objectif sans effet"
        )

    return avertissements


RegistryObjectifs.enregistrer(
    "minimiser_empreinte_co2",
    MinimiserEmpreinteCO2,
    validateur=validateur_co2,
    metadata={
        "categorie": "environnemental",
        "description": "Minimise l'empreinte carbone du planning",
        "norme": "ISO 14064",
    },
)


# ============================================================================
# Exemple 3 : Objectif multi-critères pondéré
# ============================================================================


class ObjectifMultiCriteres(BaseModel):
    """Meta-objectif permettant de combiner plusieurs objectifs avec des poids."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["objectif_multi_criteres"] = "objectif_multi_criteres"

    # Pas de poids propre - les poids sont dans les sous-objectifs

    methode_agregation: Literal["somme_ponderee", "produit", "lexicographique"] = Field(
        default="somme_ponderee",
        description=(
            "Méthode d'agrégation:\n"
            "- somme_ponderee: Σ(poids_i × objectif_i)\n"
            "- produit: Π(objectif_i^poids_i)\n"
            "- lexicographique: optimise par ordre de priorité"
        )
    )

    normalisation: bool = Field(
        default=True,
        description="Normaliser chaque objectif avant agrégation (recommandé)"
    )


RegistryObjectifs.enregistrer(
    "objectif_multi_criteres",
    ObjectifMultiCriteres,
    metadata={
        "categorie": "meta",
        "description": "Combine plusieurs objectifs avec des poids",
    },
)


# ============================================================================
# Exemple 4 : Objectif avec contraintes soft
# ============================================================================


class RespectPreferences(BaseModel):
    """Respecter les préférences d'affectation (contraintes souples).

    Différent des contraintes dures : une violation n'invalide pas le planning,
    mais dégrade l'objectif.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["respect_preferences"] = "respect_preferences"

    poids: float = Field(default=1.0, ge=0.0)

    preferences_tache_ressource: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description=(
            "Préférences d'affectation par tâche:\n"
            "{'tache_id': {'ressource_id': score_preference}}\n"
            "score > 1.0 = préféré, < 1.0 = éviter, 1.0 = neutre"
        )
    )

    preferences_horaires: dict[str, dict[str, tuple[int, int]]] = Field(
        default_factory=dict,
        description=(
            "Plages horaires préférées par tâche:\n"
            "{'tache_id': {'préféré': (debut, fin), 'éviter': (debut, fin)}}"
        )
    )


RegistryObjectifs.enregistrer(
    "respect_preferences",
    RespectPreferences,
    metadata={
        "categorie": "qualite",
        "description": "Respecte les préférences d'affectation (contraintes souples)",
    },
)


# ============================================================================
# Fonction utilitaire : créer une instance avec objectifs configurables
# ============================================================================


def creer_instance_avec_objectifs_configures(
    taches: list,
    ressources: list,
    contraintes: list,
    objectifs_config: list[dict],
) -> dict:
    """Crée une InstanceTRCO avec des objectifs configurés dynamiquement.

    Args:
        taches, ressources, contraintes: Axes T-R-C classiques
        objectifs_config: Liste de configs d'objectifs, ex:
            [
                {"type": "minimiser_makespan", "poids": 0.7, "makespan_cible": 480},
                {"type": "equilibrer_charge", "poids": 0.3, "methode": "variance"}
            ]

    Returns:
        Dict représentant une InstanceTRCO avec objectifs validés
    """
    # Valider chaque objectif via le registry
    objectifs_valides = []

    for config in objectifs_config:
        type_obj = config.get("type")
        if not type_obj:
            raise ValueError("Objectif sans champ 'type'")

        # Obtenir la classe depuis le registry
        ClasseObjectif = RegistryObjectifs.obtenir(type_obj)

        # Instancier et valider via Pydantic
        objectif = ClasseObjectif.model_validate(config)

        # Validation métier supplémentaire
        warnings = RegistryObjectifs.valider(objectif)
        if warnings:
            print(f"⚠️  Avertissements pour {type_obj}: {warnings}")

        objectifs_valides.append(objectif.model_dump(mode="json"))

    return {
        "taches": taches,
        "ressources": ressources,
        "contraintes": contraintes,
        "objectifs": objectifs_valides,
    }


# ============================================================================
# Exemples d'utilisation
# ============================================================================

if __name__ == "__main__":
    # Exemple 1 : Planning avec objectif économique personnalisé BARAA
    instance_baraa = creer_instance_avec_objectifs_configures(
        taches=[{"id": "T1"}, {"id": "T2"}],
        ressources=[{"id": "R1"}, {"id": "R2"}],
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 60},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 90},
        ],
        objectifs_config=[
            {
                "type": "minimiser_cout_total",
                "poids": 1.0,
                "cout_horaire_par_ressource": {"R1": 50.0, "R2": 75.0},
                "cout_setup_par_changement": {"R1": 100.0, "R2": 150.0},
                "penalite_retard_par_jour": 200.0,
            }
        ],
    )

    print("✅ Instance BARAA créée avec objectif économique personnalisé")
    print(f"Objectifs: {instance_baraa['objectifs']}")

    # Exemple 2 : Planning multi-objectifs pondérés
    instance_multi = creer_instance_avec_objectifs_configures(
        taches=[{"id": "T1"}, {"id": "T2"}],
        ressources=[{"id": "R1"}, {"id": "R2"}],
        contraintes=[
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 60},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 90},
        ],
        objectifs_config=[
            {
                "type": "minimiser_makespan",
                "poids": 0.6,
                "makespan_cible": 480,
            },
            {
                "type": "equilibrer_charge",
                "poids": 0.3,
                "methode": "variance",
            },
            {
                "type": "minimiser_empreinte_co2",
                "poids": 0.1,
                "emission_co2_par_ressource_par_heure": {"R1": 5.0, "R2": 3.0},
                "seuil_alerte_co2": 100.0,
            },
        ],
    )

    print("\n✅ Instance multi-objectifs créée")
    print(f"Nombre d'objectifs: {len(instance_multi['objectifs'])}")

    # Exemple 3 : Lister tous les objectifs disponibles
    print("\n📋 Objectifs disponibles dans le registry:")
    par_categorie = RegistryObjectifs.objectifs_par_categorie()
    for categorie, objectifs in sorted(par_categorie.items()):
        print(f"\n  {categorie.upper()}:")
        for obj in objectifs:
            metadata = RegistryObjectifs.obtenir_metadata(obj)
            print(f"    - {obj}: {metadata.get('description', 'Pas de description')}")
