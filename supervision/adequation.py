"""Adéquation d'un solveur à son atelier (§2, MT7) — répond à « faut-il régénérer ce solveur ? »
pour un couple (instance, solveur), **avec des arguments**, jamais par règle mécanique.

Ajouter ou retirer une contrainte, ajouter un objectif, voir le Benchmarker préférer un autre
algorithme : aucun de ces changements ne suffit à lui seul. Chacun devient un `Constat` argumenté,
classé `bloquant` (preuve que le solveur ne répond plus), `a_surveiller` (risque réel mais non
démontré), `sans_impact` (preuve ou raison claire que le solveur répond toujours) ou
`non_verifie` (pas de quoi trancher). **Seul un constat `bloquant` recommande une régénération.**

Les preuves utilisées, de la plus forte à la plus faible :

1. **Essai réel** — le solveur figé est exécuté dans le bac à sable sur l'instance *actuelle*
   (`sandbox/runner.py::executer_solveur_valide`), puis le vérificateur de faisabilité
   (`validation_engine/feasibility_checker.py`) relève les violations. Un plan qui viole une
   échéance ajoutée depuis la génération est une preuve ; un plan faisable en est une aussi, dans
   l'autre sens. Lancé seulement si les contraintes ont changé et que le bac à sable est joignable.
2. **Lecture du code** — le code source du solveur mentionne-t-il le type ajouté (`"echeance"`,
   `Echeance`...) ? Un objectif jamais lu dans le code n'est pas optimisé : c'est un argument net.
3. **Nature de la contrainte** — `taille_lot` et `competence_requise` ne sont jamais lues par un
   solveur généré (contrôle à l'ingestion / par le vérificateur), leur ajout est sans impact.
4. **Benchmarker** — rejoué sur l'instance actuelle. Un autre algorithme recommandé n'est
   bloquant que si celui du solveur ne figure pas non plus parmi les alternatives jugées valables,
   et l'argument cite les caractéristiques de l'instance sur lesquelles il s'appuie.

Le résultat reste une **indication** : la supervision propose, un humain décide (principe
fondateur).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from api.etat import (
    EtatAPI,
    signature_objectifs,
    solveurs_pour_instance_ou_scenario_de_base,
    structure_contraintes,
)
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.benchmarker import benchmarker_algorithmes
from sandbox.runner import ResultatExecution, executer_solveur_valide, sandbox_disponible
from solver_store.registry import ArtefactSolveur, Registre

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from dsl.schema import InstanceTRCO

_LOGGER = logging.getLogger(__name__)

Verdict = Literal["bloquant", "a_surveiller", "sans_impact", "non_verifie"]
Categorie = Literal["contraintes", "objectifs", "algorithme", "essai"]

# Type de contrainte DSL -> violations du vérificateur qui prouvent qu'elle n'est pas respectée.
_VIOLATIONS_PAR_CONTRAINTE: dict[str, frozenset[str]] = {
    "precedence": frozenset({"precedence_violee"}),
    "compatibilite_ressource_tache": frozenset({"incompatibilite_ressource_tache"}),
    "echeance": frozenset({"echeance_depassee"}),
    "capacite": frozenset({"capacite_depassee", "chevauchement_ressource"}),
    "incompatibilite": frozenset({"incompatibilite_taches_violee"}),
    "disponibilite_ressource": frozenset({"ressource_indisponible"}),
    "changement_serie": frozenset({"changement_serie_insuffisant"}),
    "declaration_materiau": frozenset({"stock_insuffisant"}),
    "consommation_matiere": frozenset({"stock_insuffisant"}),
}

# Jamais lues par le code d'un solveur généré (voir CLAUDE.md, DSL) : contrôlées à l'ingestion ou
# par le vérificateur seul — leur présence ou absence ne change rien à ce que le solveur doit faire.
_CONTRAINTES_HORS_SOLVEUR: dict[str, str] = {
    "taille_lot": "vérifiée uniquement par le contrôle de faisabilité, jamais lue par le solveur",
    "competence_requise": "traduite en compatibilités ressource-tâche avant le solveur, qui ne la lit jamais",
}

_NOMS_CLASSES: dict[str, str] = {
    "precedence": "Precedence",
    "compatibilite_ressource_tache": "CompatibiliteRessourceTache",
    "echeance": "Echeance",
    "competence_requise": "CompetenceRequise",
    "capacite": "ContrainteCapacite",
    "incompatibilite": "ContrainteIncompatibilite",
    "disponibilite_ressource": "ContrainteDisponibiliteRessource",
    "taille_lot": "ContrainteTailleLot",
    "changement_serie": "ContrainteChangementSerie",
    "declaration_materiau": "DeclarationMateriau",
    "consommation_matiere": "ConsommationMatiere",
    "minimiser_makespan": "MinimiserMakespan",
    "equilibrer_charge": "EquilibrerCharge",
    "minimiser_retards": "MinimiserRetards",
    "maximiser_utilisation": "MaximiserUtilisation",
    "minimiser_changements": "MinimiserChangements",
}

_MAX_PREUVES = 3


class SolveurHorsAtelier(ValueError):
    """`id_solveur` fourni pour l'analyse n'est pas un solveur actif de l'atelier analysé
    (inconnu, désactivé, ou généré pour une autre instance) — un solveur ne sert jamais que
    l'instance qui l'a fait générer."""


@dataclass(frozen=True)
class Constat:
    categorie: Categorie
    sujet: str
    verdict: Verdict
    argument: str
    preuves: tuple[str, ...] = ()

    def en_dict(self) -> dict[str, object]:
        return {
            "categorie": self.categorie,
            "sujet": self.sujet,
            "verdict": self.verdict,
            "argument": self.argument,
            "preuves": list(self.preuves),
        }


@dataclass(frozen=True)
class EssaiSolveur:
    """Résultat de l'exécution réelle du solveur sur l'instance actuelle."""

    reussi: bool
    erreur: str | None
    violations: tuple[tuple[str, str], ...]  # (type de violation, message)


@dataclass(frozen=True)
class EvaluationSolveur:
    instance_id: str
    id_solveur: str
    constats: tuple[Constat, ...]
    contraintes_ajoutees: tuple[str, ...]
    contraintes_retirees: tuple[str, ...]
    objectifs_ajoutes: tuple[str, ...]
    objectifs_retires: tuple[str, ...]
    algorithme_utilise: str | None
    algorithme_recommande: str | None
    essai: EssaiSolveur | None

    @property
    def a_regenerer(self) -> bool:
        return any(c.verdict == "bloquant" for c in self.constats)

    @property
    def instance_jugee_infaisable(self) -> bool:
        """L'essai réel a répondu « aucune solution » : à signaler (données possiblement
        impossibles), jamais une raison de régénérer à elle seule."""
        return self.essai is not None and self.essai.erreur == MESSAGE_INFAISABLE

    def raisons(self) -> tuple[str, ...]:
        """Arguments des constats bloquants — vide si rien ne justifie une régénération."""
        return tuple(f"{c.sujet} — {c.argument}" for c in self.constats if c.verdict == "bloquant")

    def en_dict(self) -> dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "id_solveur": self.id_solveur,
            "a_regenerer": self.a_regenerer,
            "raisons": list(self.raisons()),
            "constats": [c.en_dict() for c in self.constats],
            "contraintes_ajoutees": list(self.contraintes_ajoutees),
            "contraintes_retirees": list(self.contraintes_retirees),
            "objectifs_ajoutes": list(self.objectifs_ajoutes),
            "objectifs_retires": list(self.objectifs_retires),
            "algorithme_utilise": self.algorithme_utilise,
            "algorithme_recommande": self.algorithme_recommande,
            "essai": None
            if self.essai is None
            else {
                "reussi": self.essai.reussi,
                "erreur": self.essai.erreur,
                "nb_violations": len(self.essai.violations),
            },
        }


def _types(signature: str) -> set[str]:
    return {t for t in signature.split(",") if t and t != "aucune"}


def _code_mentionne(code_source: str, type_dsl: str) -> bool:
    """Le code cite-t-il ce type, par sa valeur `type` ou par son nom de classe DSL ?"""
    nom_classe = _NOMS_CLASSES.get(type_dsl)
    return type_dsl in code_source or (nom_classe is not None and nom_classe in code_source)


def solveurs_actifs_atelier(
    etat: EtatAPI, registre: Registre, client_id: str, instance_id: str
) -> dict[str, ArtefactSolveur]:
    """Solveurs actifs de cet atelier — y compris, pour un scénario sans solveur propre, celui de
    l'instance de base dont il varie (voir `api/etat.py::solveurs_pour_instance_ou_scenario_de_base`) :
    « l'atelier » d'un scénario reste, pour la supervision, celui de sa base."""
    return {s.id: s for s in solveurs_pour_instance_ou_scenario_de_base(etat, registre, client_id, instance_id)}


def solveur_a_evaluer(
    etat: EtatAPI, registre: Registre, client_id: str, instance_id: str, id_solveur: str | None
) -> ArtefactSolveur | None:
    """Le solveur demandé (vérifié comme appartenant à l'atelier, sinon `SolveurHorsAtelier`), ou à
    défaut le plus récemment validé de l'atelier ; `None` si l'atelier n'en a aucun."""
    solveurs = solveurs_actifs_atelier(etat, registre, client_id, instance_id)
    if id_solveur is not None:
        if id_solveur not in solveurs:
            raise SolveurHorsAtelier(
                f"le solveur {id_solveur!r} n'est pas un solveur actif de l'atelier {instance_id!r}"
            )
        return solveurs[id_solveur]
    if not solveurs:
        return None
    return max(solveurs.values(), key=lambda s: s.date_validation)


# ---------------------------------------------------------------------------------------------
# Constats
# ---------------------------------------------------------------------------------------------


def _essayer(
    registre: Registre,
    solveur: ArtefactSolveur,
    instance: InstanceTRCO,
    executer: Callable[[Registre, str, InstanceTRCO], ResultatExecution],
) -> EssaiSolveur:
    resultat = executer(registre, solveur.id, instance)
    violations = (
        tuple((v.type, v.message) for v in resultat.verdict_faisabilite.violations)
        if resultat.verdict_faisabilite is not None
        else ()
    )
    return EssaiSolveur(reussi=resultat.reussi, erreur=resultat.erreur, violations=violations)


# Message posé par `sandbox/runner.py::executer_solveur_valide` quand le solveur répond « aucune
# solution » — distinct d'un plantage ou d'un dépassement de temps.
MESSAGE_INFAISABLE = "le solveur a jugé l'instance infaisable"


def _constat_essai_en_echec(essai: EssaiSolveur) -> Constat:
    if essai.erreur == MESSAGE_INFAISABLE:
        # Jamais « améliorer » un solveur sain pour des données impossibles (voir CLAUDE.md,
        # boucle de diagnostic) : l'infaisabilité peut venir des données autant que du solveur.
        return Constat(
            categorie="essai",
            sujet="Exécution sur l'instance actuelle",
            verdict="a_surveiller",
            argument=(
                "le solveur juge l'instance actuelle infaisable — cela peut venir des données (échéances "
                "impossibles, stock insuffisant...) autant que du solveur : un diagnostic doit trancher "
                "avant toute régénération"
            ),
            preuves=(f"erreur : {essai.erreur}",),
        )
    return Constat(
        categorie="essai",
        sujet="Exécution sur l'instance actuelle",
        verdict="bloquant",
        argument=(
            "le solveur ne produit aucun planning sur l'instance telle qu'elle est aujourd'hui — il ne "
            "répond plus à cet atelier"
        ),
        preuves=(f"erreur : {essai.erreur}",),
    )


def _constat_contrainte_ajoutee(type_c: str, solveur: ArtefactSolveur, essai: EssaiSolveur | None) -> Constat:
    sujet = f"Contrainte ajoutée : {type_c}"
    if type_c in _CONTRAINTES_HORS_SOLVEUR:
        return Constat("contraintes", sujet, "sans_impact", _CONTRAINTES_HORS_SOLVEUR[type_c] + ".")

    mentionnee = _code_mentionne(solveur.code_source, type_c)
    types_violation = _VIOLATIONS_PAR_CONTRAINTE.get(type_c, frozenset())

    if essai is not None and essai.reussi is False and essai.erreur is None:
        # Planning produit mais illégal : on regarde si c'est bien CETTE contrainte qui est violée.
        pertinentes = [m for t, m in essai.violations if t in types_violation]
        if pertinentes:
            return Constat(
                "contraintes",
                sujet,
                "bloquant",
                f"essai réel sur l'instance actuelle : le planning produit viole {len(pertinentes)} fois "
                "cette contrainte — le solveur ne la respecte pas",
                tuple(pertinentes[:_MAX_PREUVES]),
            )

    if essai is not None and essai.erreur is None:
        pertinentes = [m for t, m in essai.violations if t in types_violation]
        if not pertinentes:
            if mentionnee:
                return Constat(
                    "contraintes",
                    sujet,
                    "sans_impact",
                    "le code du solveur traite déjà ce type de contrainte, et l'essai réel sur l'instance "
                    "actuelle la respecte",
                )
            return Constat(
                "contraintes",
                sujet,
                "a_surveiller",
                "l'essai réel sur l'instance actuelle la respecte, mais le code du solveur ne mentionne jamais "
                "ce type : le respect tient aux données actuelles, pas au solveur, et peut cesser dès "
                "qu'elles changent",
            )

    # Pas d'essai exploitable (bac à sable injoignable) : seule la lecture du code tranche.
    if not mentionnee:
        return Constat(
            "contraintes",
            sujet,
            "bloquant",
            "le code du solveur ne mentionne ce type de contrainte nulle part : il ne peut pas en tenir compte",
            ("recherche dans le code source : aucune occurrence",),
        )
    return Constat(
        "contraintes",
        sujet,
        "non_verifie",
        "le code du solveur mentionne ce type, mais aucun essai réel n'a pu confirmer qu'il est respecté "
        "(bac à sable injoignable)",
    )


def _constat_contrainte_retiree(type_c: str, essai: EssaiSolveur | None) -> Constat:
    sujet = f"Contrainte retirée : {type_c}"
    if essai is not None and essai.erreur is None:
        return Constat(
            "contraintes",
            sujet,
            "sans_impact",
            "le solveur n'a simplement plus rien à traiter pour ce type, et l'essai réel sur l'instance actuelle "
            "produit toujours un planning",
        )
    return Constat(
        "contraintes",
        sujet,
        "sans_impact",
        "le solveur n'a plus rien à traiter pour ce type : une contrainte en moins ne le rend pas inadapté",
    )


def _constat_objectif_ajoute(type_o: str, solveur: ArtefactSolveur) -> Constat:
    sujet = f"Objectif ajouté : {type_o}"
    if _code_mentionne(solveur.code_source, type_o):
        return Constat(
            "objectifs",
            sujet,
            "sans_impact",
            "le code du solveur traite déjà cet objectif et lit ses réglages dans l'instance à chaque exécution",
        )
    return Constat(
        "objectifs",
        sujet,
        "bloquant",
        "le code du solveur ne lit jamais cet objectif : il ne l'optimise pas, le planning l'ignorera",
        ("recherche dans le code source : aucune occurrence",),
    )


def _constat_objectif_retire(type_o: str, solveur: ArtefactSolveur) -> Constat:
    sujet = f"Objectif retiré : {type_o}"
    if _code_mentionne(solveur.code_source, type_o):
        return Constat(
            "objectifs",
            sujet,
            "a_surveiller",
            "le planning reste valide, mais le code du solveur traite encore cet objectif : s'il l'applique "
            "sans vérifier qu'il est demandé, la qualité du planning peut en pâtir (jamais sa faisabilité)",
        )
    return Constat("objectifs", sujet, "sans_impact", "le solveur ne traitait pas cet objectif de toute façon.")


def _constat_algorithme(
    modele: BaseChatModel, instance: InstanceTRCO, solveur: ArtefactSolveur
) -> tuple[Constat, str | None]:
    sujet = "Algorithme"
    if solveur.algorithme is None:
        return (
            Constat(
                "algorithme",
                sujet,
                "non_verifie",
                "l'algorithme de ce solveur n'a pas été enregistré (solveur antérieur à ce suivi) — "
                "impossible de le comparer à la recommandation actuelle",
            ),
            None,
        )
    try:
        benchmark = benchmarker_algorithmes(modele, instance.model_dump(mode="json"), avec_outils=False)
    except ErreurReponseAgentInvalide as erreur:
        _LOGGER.warning("Benchmarker inexploitable : %s", erreur)
        return (
            Constat(
                "algorithme",
                sujet,
                "non_verifie",
                "le Benchmarker n'a pas renvoyé de recommandation exploitable",
            ),
            None,
        )

    reco = benchmark.recommandation
    carac = benchmark.caracteristiques
    faits = (
        f"instance actuelle : {carac.nb_taches} tâches ({carac.taille_categorie}), "
        f"{carac.nb_ressources} ressources, flexibilité moyenne {carac.flexibilite_moyenne:.1f}",
        f"contraintes : {', '.join(carac.types_contraintes) or 'aucune'}",
        f"justification du Benchmarker : {reco.raison}",
    )
    if solveur.algorithme == reco.algorithme:
        constat = Constat(
            "algorithme",
            sujet,
            "sans_impact",
            f"{solveur.algorithme} reste l'algorithme recommandé pour l'instance actuelle",
            faits,
        )
    elif solveur.algorithme in reco.alternatives:
        constat = Constat(
            "algorithme",
            sujet,
            "sans_impact",
            f"{reco.algorithme} est désormais préféré, mais {solveur.algorithme} figure parmi les alternatives "
            "jugées valables — pas une raison suffisante pour régénérer",
            faits,
        )
    else:
        constat = Constat(
            "algorithme",
            sujet,
            "bloquant",
            f"{solveur.algorithme} n'est ni recommandé ni parmi les alternatives valables pour l'instance "
            f"actuelle ; {reco.algorithme} est recommandé",
            faits,
        )
    return constat, reco.algorithme


def evaluer_solveur(
    etat: EtatAPI,
    registre: Registre,
    modele: BaseChatModel,
    instance_id: str,
    solveur: ArtefactSolveur,
    *,
    executer: Callable[[Registre, str, InstanceTRCO], ResultatExecution] | None = None,
    bac_a_sable_disponible: Callable[[], bool] | None = None,
) -> EvaluationSolveur:
    """Évalue `solveur` contre l'instance `instance_id` telle qu'elle est aujourd'hui (voir
    docstring de module). Au plus un essai en bac à sable (seulement si les contraintes ont changé)
    et un appel LLM (Benchmarker, sans outil de recherche web). `executer`/`bac_a_sable_disponible`
    sont injectables pour les tests."""
    # Résolus à l'appel (pas en valeur par défaut figée à l'import) : remplaçables dans les tests.
    executer = executer or executer_solveur_valide
    bac_a_sable_disponible = bac_a_sable_disponible or sandbox_disponible
    _, instance = etat.recuperer_instance(instance_id)

    types_c_instance = _types(structure_contraintes(instance))
    types_c_solveur = _types(solveur.structure_contraintes)
    types_o_instance = _types(signature_objectifs(instance))
    types_o_solveur = _types(solveur.signature_objectifs)
    contraintes_ajoutees = tuple(sorted(types_c_instance - types_c_solveur))
    contraintes_retirees = tuple(sorted(types_c_solveur - types_c_instance))
    objectifs_ajoutes = tuple(sorted(types_o_instance - types_o_solveur))
    objectifs_retires = tuple(sorted(types_o_solveur - types_o_instance))

    constats: list[Constat] = []

    essai: EssaiSolveur | None = None
    if (contraintes_ajoutees or contraintes_retirees) and bac_a_sable_disponible():
        essai = _essayer(registre, solveur, instance, executer)
        if essai.erreur is not None:
            constats.append(_constat_essai_en_echec(essai))

    constats += [_constat_contrainte_ajoutee(t, solveur, essai) for t in contraintes_ajoutees]
    constats += [_constat_contrainte_retiree(t, essai) for t in contraintes_retirees]
    constats += [_constat_objectif_ajoute(t, solveur) for t in objectifs_ajoutes]
    constats += [_constat_objectif_retire(t, solveur) for t in objectifs_retires]
    if not (contraintes_ajoutees or contraintes_retirees or objectifs_ajoutes or objectifs_retires):
        constats.append(
            Constat(
                "contraintes",
                "Contraintes et objectifs",
                "sans_impact",
                "aucun type de contrainte ni d'objectif n'a changé depuis la génération du solveur",
            )
        )

    constat_algo, algorithme_recommande = _constat_algorithme(modele, instance, solveur)
    constats.append(constat_algo)

    return EvaluationSolveur(
        instance_id=instance_id,
        id_solveur=solveur.id,
        constats=tuple(constats),
        contraintes_ajoutees=contraintes_ajoutees,
        contraintes_retirees=contraintes_retirees,
        objectifs_ajoutes=objectifs_ajoutes,
        objectifs_retires=objectifs_retires,
        algorithme_utilise=solveur.algorithme,
        algorithme_recommande=algorithme_recommande,
        essai=essai,
    )
