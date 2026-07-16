"""Fait passer les données réelles de `db_greensig` (profil `greensig`, voir
docker-compose.yml) à travers l'adaptateur GreenSIG (`adapters/greensig/`) et
documente le résultat : un rapport par tâche (CSV) et un résumé (Markdown),
écrits dans `adapters/greensig/`.

Ne contourne pas le garde-fou §6.7 : la traduction du lot brut complet est
tentée telle quelle (et son échec, s'il y en a un, est documenté comme tel) ;
un second essai, filtré aux seules tâches déjà traduisibles, sert uniquement
à illustrer à quoi ressemblerait l'InstanceTRCO obtenue — ce n'est jamais ce
sous-ensemble que le système utiliserait réellement (voir §7.2 bis,
`api/routes/adapters.py`, décision explicite de garder le rejet total).

Usage, depuis la racine du dépôt : uv run python -m scripts.rapport_greensig_dsl
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from adapters.greensig import PayloadGreenSIG, extraire_payload, traduire
from adapters.greensig.translator import duree_minutes_pour, id_tache
from dsl.schema import InstanceTRCO

DOSSIER_SORTIE = Path(__file__).resolve().parent.parent / "adapters" / "greensig"
CHEMIN_CSV = DOSSIER_SORTIE / "rapport_dsl.csv"
CHEMIN_MD = DOSSIER_SORTIE / "rapport_dsl.md"


def _lignes_par_tache(payload: PayloadGreenSIG) -> list[dict[str, object]]:
    types_par_id = {t.id: t.nom_tache for t in payload.types_tache}
    equipes_actives_ids = {e.id for e in payload.equipes if e.actif}

    lignes: list[dict[str, object]] = []
    for tache in payload.taches:
        if tache.deleted_at is not None:
            continue  # hors périmètre canonique, comme traduire()
        nb_actives = sum(1 for eid in tache.equipes_ids if eid in equipes_actives_ids)
        lignes.append(
            {
                "tache_id": id_tache(tache.id),
                "type_tache": types_par_id.get(tache.id_type_tache_id, "?"),
                "charge_estimee_heures": tache.charge_estimee_heures,
                "duree_minutes_calculee": duree_minutes_pour(tache.charge_estimee_heures),
                "nb_equipes_actives_affectees": nb_actives,
                "statut": "traduit" if nb_actives > 0 else "rejeté : aucune équipe active",
            }
        )
    return lignes


def _ecrire_csv(lignes: list[dict[str, object]], chemin: Path) -> None:
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


def _instance_illustrative(payload: PayloadGreenSIG) -> InstanceTRCO:
    """Traduit le sous-ensemble déjà traduisible, uniquement pour illustrer la forme de
    l'InstanceTRCO obtenue — jamais ce que le système ingère réellement (voir docstring)."""
    equipes_actives_ids = {e.id for e in payload.equipes if e.actif}
    taches_traduisibles = [
        t
        for t in payload.taches
        if t.deleted_at is None and any(eid in equipes_actives_ids for eid in t.equipes_ids)
    ]
    payload_filtre = PayloadGreenSIG(
        taches=taches_traduisibles, equipes=payload.equipes, types_tache=payload.types_tache
    )
    return traduire(payload_filtre)


def main() -> None:
    payload = extraire_payload()
    lignes = _lignes_par_tache(payload)

    total = len(lignes)
    traduites = [ligne for ligne in lignes if ligne["statut"] == "traduit"]
    rejetees = [ligne for ligne in lignes if ligne["statut"] != "traduit"]

    print(f"Tâches actives extraites (statut à planifier, non supprimées) : {total}")
    print(f"  traduisibles (≥1 équipe active) : {len(traduites)}")
    print(f"  rejetées (aucune équipe active) : {len(rejetees)}")

    if rejetees:
        print("\nRejets par type de tâche (top 10) :")
        for type_tache, n in Counter(ligne["type_tache"] for ligne in rejetees).most_common(10):
            print(f"  {type_tache:<40} {n}")

    print("\nTentative de traduction du lot brut complet (comportement réel du système) :")
    try:
        traduire(payload)
        resultat_brut = "réussie"
    except ValidationError as erreur:
        resultat_brut = f"rejetée — {erreur.error_count()} violation(s), voir détail dans le rapport"
        detail_erreur_brute = str(erreur)
    else:
        detail_erreur_brute = None
    print(f"  {resultat_brut}")

    instance_illustrative = _instance_illustrative(payload) if traduites else None
    if instance_illustrative:
        print("\nInstanceTRCO illustrative (sous-ensemble traduisible seulement, jamais ingérée telle quelle) :")
        print(f"  {len(instance_illustrative.taches)} tâches, {len(instance_illustrative.ressources)} ressources,")
        print(f"  {len(instance_illustrative.contraintes)} contraintes de compatibilité machine-tâche")

    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    _ecrire_csv(lignes, CHEMIN_CSV)

    horodatage = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    with open(CHEMIN_MD, "w", encoding="utf-8") as f:
        f.write("# Rapport — données GreenSIG à travers le DSL T-R-C-O\n\n")
        f.write(f"Généré le {horodatage} depuis `db_greensig` (`adapters/greensig/extraction.py` → ")
        f.write("`adapters/greensig/translator.py`). Détail par tâche : [`rapport_dsl.csv`](rapport_dsl.csv).\n\n")
        f.write("## Résumé\n\n")
        f.write("| | |\n|---|---:|\n")
        f.write(f"| Tâches actives extraites | {total} |\n")
        f.write(f"| Traduisibles (≥1 équipe active) | {len(traduites)} |\n")
        f.write(f"| Rejetées (aucune équipe active) | {len(rejetees)} |\n")
        f.write(f"| Taux de rejet | {len(rejetees) / total:.0%} |\n\n" if total else "\n")

        f.write("## Traduction du lot brut complet (comportement réel du système)\n\n")
        f.write(
            "`api/routes/adapters.py` (`POST /adapters/greensig/ingerer`) tente exactement cette traduction, "
            "sans filtrage — une seule tâche sans compatibilité suffit à faire rejeter tout le lot par "
            "`InstanceTRCO` (garde-fou §6.7, `adapters/greensig/mapping/regles.md` limite 3). "
            "Décision explicite : ne jamais ingérer un sous-ensemble silencieusement tronqué.\n\n"
        )
        f.write(f"**Résultat : {resultat_brut}.**\n\n")
        if detail_erreur_brute:
            f.write("<details><summary>Détail de l'erreur de validation</summary>\n\n```\n")
            f.write(detail_erreur_brute)
            f.write("\n```\n\n</details>\n\n")

        if rejetees:
            f.write("## Rejets par type de tâche\n\n")
            f.write("| Type de tâche | Tâches rejetées |\n|---|---:|\n")
            for type_tache, n in Counter(ligne["type_tache"] for ligne in rejetees).most_common():
                f.write(f"| {type_tache} | {n} |\n")
            f.write("\n")

        if instance_illustrative:
            f.write("## Instance T-R-C-O illustrative (sous-ensemble traduisible)\n\n")
            f.write(
                "**Jamais ce que le système ingère réellement** — construite ici uniquement pour montrer la "
                "forme de l'InstanceTRCO obtenue une fois les tâches sans équipe active écartées.\n\n"
            )
            f.write("| | |\n|---|---:|\n")
            f.write(f"| Tâches | {len(instance_illustrative.taches)} |\n")
            f.write(f"| Ressources (équipes) | {len(instance_illustrative.ressources)} |\n")
            f.write(f"| Contraintes de compatibilité machine-tâche | {len(instance_illustrative.contraintes)} |\n")
            f.write("| Contraintes de précédence | 0 (GreenSIG n'en produit jamais, voir regles.md) |\n")
            f.write("| Objectif | minimiser_makespan |\n")

    print(f"\nÉcrit : {CHEMIN_CSV}")
    print(f"Écrit : {CHEMIN_MD}")


if __name__ == "__main__":
    main()
