"""Démonstration de `estimation/` (MT3 du plan directeur, §3.3.2) : entraîne
un estimateur de durée sur l'historique synthétique (faute d'historique réel
d'exécution — voir `docs/perspective_estimation_charge.md`), vérifie qu'il
retrouve le signal connu sur un cas jamais vu à l'entraînement, puis prouve
le branchement réel dans `adapters/csv_import/` : une durée manquante
comblée par le modèle, avec l'avertissement explicite que cela produit
(§FC4, décision humaine préservée).

Nécessite l'extra optionnel `estimation` : `uv sync --extra estimation`.
Usage, depuis la racine du dépôt : uv run python -m scripts.demo_estimation_charge
"""

from __future__ import annotations

from adapters.csv_import import ErreurFichierInvalide, traduire
from dsl.schema import CompatibiliteRessourceTache, Ressource, Tache
from estimation import EstimateurDuree, historique_synthetique
from estimation.donnees_historique import TYPES_RESSOURCE_CYCLE, _duree_observee, _residu, _traits_synthetiques
from validation_engine.synthetic_bench.construction_inverse import FormeJob, construire_instance


def _partie_1_recouvrement_du_signal() -> EstimateurDuree:
    print("=== 1. Entraînement sur l'historique synthétique (banc Étape 3) ===")
    observations = historique_synthetique()
    estimateur = EstimateurDuree.entrainer(observations)
    print(f"{len(observations)} observations synthétiques, entraînement terminé.")

    # Une forme de job absente des 5 cas du catalogue existant (validation_engine/
    # synthetic_bench/catalogue.py) — un vrai cas jamais présenté à l'entraînement.
    cas = construire_instance("demo_cas_inedit", [FormeJob(n_taches=4, n_ressources=2)])
    print(f"\nCas jamais vu à l'entraînement : {cas.nom!r}")
    for indice, tache in enumerate(cas.instance.taches):
        compat = next(
            c
            for c in cas.instance.contraintes
            if isinstance(c, CompatibiliteRessourceTache) and c.tache == tache.id
        )
        quantite, priorite, type_index, nb_competences = _traits_synthetiques(indice)
        residu = _residu(compat.tache, compat.ressource)
        vraie_duree = _duree_observee(quantite, priorite, type_index, nb_competences, residu)

        tache_avec_traits = Tache(id=tache.id, quantite=quantite, priorite=priorite)
        ressource_avec_traits = Ressource(
            id=compat.ressource,
            type=TYPES_RESSOURCE_CYCLE[type_index],
            competences=[f"c{i}" for i in range(nb_competences)],
        )
        estimation = estimateur.estimer(tache_avec_traits, ressource_avec_traits)
        print(
            f"  {tache.id} / {compat.ressource} : estimée {estimation.duree_estimee_jours} j "
            f"(confiance {estimation.confiance:.2f}) — vraie durée, connue par construction : {vraie_duree} j"
        )
    return estimateur


def _partie_2_integration_adaptateur_csv(estimateur: EstimateurDuree) -> None:
    print("\n=== 2. Branchement réel dans adapters/csv_import (durée manquante) ===")
    taches_csv = b"id\nT_SANS_DUREE\n"
    ressources_csv = b"id,competences\nR_QUALIFIEE,decoupe\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T_SANS_DUREE,decoupe\n"

    try:
        traduire(taches_csv, ressources_csv, contraintes_csv)
    except ErreurFichierInvalide as erreur:
        print(f"Sans estimateur (comportement inchangé) : {erreur}")

    resultat = traduire(taches_csv, ressources_csv, contraintes_csv, estimateur_duree=estimateur)
    compat = next(c for c in resultat.instance.contraintes if isinstance(c, CompatibiliteRessourceTache))
    print(f"Avec estimateur : compatibilité dérivée avec duree={compat.duree} j")
    print("Avertissements renvoyés à l'appelant (jamais une estimation qui se fait passer pour un fait) :")
    for avertissement in resultat.avertissements:
        print(f"  - {avertissement}")


def main() -> None:
    estimateur = _partie_1_recouvrement_du_signal()
    _partie_2_integration_adaptateur_csv(estimateur)


if __name__ == "__main__":
    main()
