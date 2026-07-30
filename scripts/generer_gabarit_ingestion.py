"""Génère le gabarit tableur (xlsx) d'ingestion T-R-C-O — la version tableur
de `docs/dsl/modele_ingestion_client.md`, à remettre à une personne qui n'a
pas à écrire de JSON à la main : elle remplit les onglets, puis le fichier
est ingéré tel quel via `POST /adapters/tableur/{client_id}`
(`adapters/tableur/`), qui lit exactement les onglets produits ici.

À relancer si les règles du DSL (`dsl/schema/`) changent — et si les noms/
colonnes d'onglets changent, mettre à jour `adapters/tableur/traducteur.py`
en même temps, les deux doivent rester en accord.

Le frontend (page Données, import de données brutes) sert sa propre copie en
téléchargement direct — `Front/prismatron-solver-forge/public/gabarits/
gabarit_ingestion_trco.xlsx` — jamais lue dynamiquement depuis `docs/dsl/`
(le frontend peut être déployé sans le dépôt Python à côté). Recopier
manuellement après régénération, ce script ne le fait pas lui-même.

    uv run python -m scripts.generer_gabarit_ingestion
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

CHEMIN_SORTIE = Path(__file__).resolve().parent.parent / "docs" / "dsl" / "gabarit_ingestion_trco.xlsx"

BLEU_ENTETE = "1A2233"
GRIS_EXEMPLE = "F4F5F7"
BLANC = "FFFFFF"
AMBRE_FONCE = "7A5C00"
AMBRE_CLAIR = "FFF3CD"
BORDURE = Side(style="thin", color="DCDFE4")

FONT_TITRE = Font(name="Calibri", size=16, bold=True, color=BLEU_ENTETE)
FONT_SOUS_TITRE = Font(name="Calibri", size=11, italic=True, color="565F74")
FONT_ENTETE = Font(name="Calibri", size=11, bold=True, color=BLANC)
FONT_EXEMPLE = Font(name="Calibri", size=11, italic=True, color="8A93A8")
FONT_BANNIERE_TITRE = Font(name="Calibri", size=13, bold=True, color=AMBRE_FONCE)
FONT_BANNIERE_TEXTE = Font(name="Calibri", size=10.5, color=AMBRE_FONCE)
FILL_ENTETE = PatternFill("solid", fgColor=BLEU_ENTETE)
FILL_EXEMPLE = PatternFill("solid", fgColor=GRIS_EXEMPLE)
FILL_BANNIERE = PatternFill("solid", fgColor=AMBRE_CLAIR)
BORDURE_CELLULE = Border(left=BORDURE, right=BORDURE, top=BORDURE, bottom=BORDURE)

N_LIGNES_VALIDATION = 500  # plage couverte par les listes déroulantes / validations


def _entete(ws, colonnes: list[tuple[str, int, str | None]], ligne: int = 1) -> None:
    """colonnes = [(libellé, largeur, commentaire ou None), ...]"""
    for i, (libelle, largeur, commentaire) in enumerate(colonnes, start=1):
        cellule = ws.cell(row=ligne, column=i, value=libelle)
        cellule.font = FONT_ENTETE
        cellule.fill = FILL_ENTETE
        cellule.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[cellule.column_letter].width = largeur
        if commentaire:
            cellule.comment = Comment(commentaire, "PRISME")
    ws.freeze_panes = f"A{ligne + 1}"
    ws.row_dimensions[ligne].height = 32


def _ligne_exemple(ws, valeurs: list, ligne: int = 2, note: str | None = None) -> None:
    for i, v in enumerate(valeurs, start=1):
        c = ws.cell(row=ligne, column=i, value=v)
        c.font = FONT_EXEMPLE
        c.fill = FILL_EXEMPLE
        c.border = BORDURE_CELLULE
    if note:
        c = ws.cell(row=ligne, column=len(valeurs) + 2, value=note)
        c.font = FONT_EXEMPLE


def _bordures_vides(ws, n_colonnes: int, ligne_debut: int = 3) -> None:
    for r in range(ligne_debut, N_LIGNES_VALIDATION + 1):
        for col in range(1, n_colonnes + 1):
            ws.cell(row=r, column=col).border = BORDURE_CELLULE


def construire(chemin_sortie: Path) -> None:
    wb = Workbook()

    # ---------------------------------------------------------------- Instructions
    ws = wb.active
    ws.title = "Instructions"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 100

    lignes: list[tuple[str, Font | None]] = [
        ("Gabarit de données — planification (ordonnancement d'ateliers)", FONT_TITRE),
        ("À remplir puis à renvoyer tel quel — la conversion vers le système est automatique.", FONT_SOUS_TITRE),
        ("", None),
        ("5 onglets à remplir, dans cet ordre :", Font(bold=True)),
        ("  1. Tâches — la liste des travaux à planifier.", None),
        ("  2. Ressources — la liste des ressource/équipes qui peuvent réaliser ces travaux.", None),
        ("  3. Précédences (optionnel) — quelles tâches doivent être finies avant que d'autres démarrent.", None),
        ("  4. Compatibilités — quelle tâche peut être faite par quelle ressource, et en combien de temps.", None),
        (
            "  5. Besoins additionnels (optionnel) — tout ce qui ne rentre pas dans les 4 onglets ci-dessus,",
            None,
        ),
        ("     en langage libre (voir plus bas).", None),
        ("", None),
        ("Règles à respecter :", Font(bold=True)),
        (
            '  • Les identifiants (colonnes "id") : lettres, chiffres, "_" et "-" uniquement, sans espace',
            None,
        ),
        ("    ni accent.", None),
        ("  • Un identifiant ne doit jamais être réutilisé deux fois dans le même onglet.", None),
        (
            '  • Chaque tâche doit apparaître au moins une fois dans l\'onglet "Compatibilités" — sinon sa',
            None,
        ),
        ("    durée est inconnue et elle ne peut pas être planifiée.", None),
        ("  • L'onglet \"Précédences\" peut rester vide si l'ordre des tâches n'a pas d'importance.", None),
        ("  • Ne pas ajouter/supprimer de colonnes, ne pas renommer les onglets, ne pas fusionner de", None),
        ("    cellules.", None),
        ("  • La ligne 2 de chaque onglet est un exemple (fond grisé, italique) — à remplacer ou effacer.", None),
        ("", None),
        ("Objectif du planning :", Font(bold=True)),
        ("  Minimiser la durée totale (le \"makespan\") — c'est la seule option aujourd'hui, rien à", None),
        ("  remplir.", None),
        ("", None),
        ("Besoins non couverts par le système aujourd'hui :", Font(bold=True)),
        (
            "  Répartir la charge, respecter un calendrier, prioriser certaines commandes... le système ne",
            None,
        ),
        (
            "  le sait pas encore faire automatiquement — décrivez-le avec vos propres mots dans l'onglet",
            None,
        ),
        ('  "Besoins additionnels", ce sera examiné à la main.', None),
        ("", None),
        ("Une fois rempli :", Font(bold=True)),
        ("  Renvoyez ce fichier tel quel — pas besoin de le convertir vous-même.", None),
    ]
    for i, (texte, police) in enumerate(lignes, start=1):
        c = ws.cell(row=i, column=1, value=texte)
        c.font = police or Font(name="Calibri", size=11)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---------------------------------------------------------------- Tâches
    ws = wb.create_sheet("Tâches")
    _entete(
        ws,
        [
            ("id *", 22, "Identifiant unique de la tâche. Lettres/chiffres/_/- uniquement, ex. T1, decoupe-01."),
            ("nom", 34, "Libre, pour la lisibilité humaine seulement (facultatif)."),
        ],
    )
    _ligne_exemple(ws, ["T1", "Découpe"], note="← exemple, à remplacer")
    _bordures_vides(ws, 2)

    # ---------------------------------------------------------------- Ressources
    ws = wb.create_sheet("Ressources")
    _entete(
        ws,
        [
            ("id *", 22, "Identifiant unique de la ressource (ressource, équipe...). Même règle que les tâches."),
            ("nom", 34, "Libre, pour la lisibilité humaine seulement (facultatif)."),
        ],
    )
    _ligne_exemple(ws, ["R1", "Découpeuse"], note="← exemple, à remplacer")
    _bordures_vides(ws, 2)

    # ---------------------------------------------------------------- Précédences
    ws = wb.create_sheet("Précédences")
    _entete(
        ws,
        [
            ("tache_avant *", 22, 'Cette tâche doit être terminée avant que "tache_apres" ne commence.'),
            ("tache_apres *", 22, "Doit être un id déjà déclaré dans l'onglet Tâches."),
        ],
    )
    _ligne_exemple(ws, ["T1", "T2"], note="← exemple : T1 doit finir avant que T2 commence")
    _bordures_vides(ws, 2)
    dv_taches_a = DataValidation(
        type="list", formula1=f"='Tâches'!$A$2:$A${N_LIGNES_VALIDATION}", allow_blank=True, showErrorMessage=True
    )
    dv_taches_a.error = "Doit être un id déclaré dans l'onglet Tâches."
    ws.add_data_validation(dv_taches_a)
    dv_taches_a.add(f"A3:A{N_LIGNES_VALIDATION}")
    dv_taches_b = DataValidation(
        type="list", formula1=f"='Tâches'!$A$2:$A${N_LIGNES_VALIDATION}", allow_blank=True, showErrorMessage=True
    )
    dv_taches_b.error = "Doit être un id déclaré dans l'onglet Tâches."
    ws.add_data_validation(dv_taches_b)
    dv_taches_b.add(f"B3:B{N_LIGNES_VALIDATION}")

    # ---------------------------------------------------------------- Compatibilités
    ws = wb.create_sheet("Compatibilités")
    _entete(
        ws,
        [
            ("tache *", 22, "Doit être un id déclaré dans l'onglet Tâches."),
            ("ressource *", 22, "Doit être un id déclaré dans l'onglet Ressources."),
            (
                "duree_minutes *",
                18,
                "Durée en minutes pour CE couple tâche-ressource précisément (nombre entier positif).",
            ),
        ],
    )
    _ligne_exemple(ws, ["T1", "R1", 30], note="← exemple : T1 prend 30 min sur M1")
    _bordures_vides(ws, 3)
    dv_c_tache = DataValidation(
        type="list", formula1=f"='Tâches'!$A$2:$A${N_LIGNES_VALIDATION}", allow_blank=True, showErrorMessage=True
    )
    dv_c_tache.error = "Doit être un id déclaré dans l'onglet Tâches."
    ws.add_data_validation(dv_c_tache)
    dv_c_tache.add(f"A3:A{N_LIGNES_VALIDATION}")
    dv_c_ressource = DataValidation(
        type="list",
        formula1=f"='Ressources'!$A$2:$A${N_LIGNES_VALIDATION}",
        allow_blank=True,
        showErrorMessage=True,
    )
    dv_c_ressource.error = "Doit être un id déclaré dans l'onglet Ressources."
    ws.add_data_validation(dv_c_ressource)
    dv_c_ressource.add(f"B3:B{N_LIGNES_VALIDATION}")
    dv_duree = DataValidation(
        type="whole", operator="greaterThan", formula1="0", allow_blank=True, showErrorMessage=True
    )
    dv_duree.error = "La durée doit être un nombre entier positif (en minutes)."
    ws.add_data_validation(dv_duree)
    dv_duree.add(f"C3:C{N_LIGNES_VALIDATION}")

    # ---------------------------------------------------------------- Besoins additionnels
    # Contraintes/objectifs hors du périmètre minimal actuel (calendriers, priorités,
    # équilibrage de charge... — voir dsl/schema/objectifs.py, "noyau minimal : makespan
    # seul"). Capturés en langage libre plutôt que perdus ou forcés dans un schéma qui ne
    # les représente pas encore — examinés à la main, jamais transmis tels quels au solveur.
    ws = wb.create_sheet("Besoins additionnels")
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 46
    ws.column_dimensions["D"].width = 24

    ws.merge_cells("A1:D1")
    c = ws.cell(row=1, column=1, value="Besoins additionnels — non couverts par le système aujourd'hui")
    c.font = FONT_BANNIERE_TITRE
    c.fill = FILL_BANNIERE
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 22
    for col in range(1, 5):
        ws.cell(row=1, column=col).fill = FILL_BANNIERE

    ws.merge_cells("A2:D2")
    c = ws.cell(
        row=2,
        column=1,
        value=(
            "Ce que le système sait faire aujourd'hui : ordonner des tâches selon des contraintes "
            "de précédence et de compatibilité ressource-tâche, en minimisant la durée totale. Tout le "
            "reste (calendriers, équilibrage de charge, priorités, délais...) se note ici, en langage "
            "courant. Ce n'est PAS traité automatiquement — c'est examiné à la main avant toute évolution."
        ),
    )
    c.font = FONT_BANNIERE_TEXTE
    c.fill = FILL_BANNIERE
    c.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True, indent=1)
    ws.row_dimensions[2].height = 48
    for col in range(1, 5):
        ws.cell(row=2, column=col).fill = FILL_BANNIERE

    ws.row_dimensions[3].height = 8  # respiration avant le tableau

    _entete(
        ws,
        [
            ("besoin_exprime *", 46, "Ce que la personne veut, dans ses propres mots — pas de jargon technique."),
            ("type_indicatif", 22, "Aide au tri (facultatif) : plutôt une contrainte ou plutôt un objectif ?"),
            ("contexte", 46, "Pourquoi c'est important, dans quel cas ça se produit (facultatif)."),
            ("contact", 24, "Qui contacter pour en discuter (facultatif)."),
        ],
        ligne=4,
    )
    _ligne_exemple(
        ws,
        [
            "Optimiser la répartition des commandes selon les heures de travail de confirmation de commande",
            "Objectif supplémentaire",
            "Les commandes confirmées tard dans la journée surchargent l'équipe du matin",
            "DSI — j.dupont@client.fr",
        ],
        ligne=5,
    )
    # Constat réel (pas un exemple à effacer) : voir adapters/greensig/rapport_dsl.md — 228/1007
    # tâches (23 %) n'ont jamais été affectées à une équipe, donc rejetées par le garde-fou §6.7
    # plutôt que planifiées. Ce n'est PAS une affectation à faire en amont — juste établir quelles
    # équipes seraient compatibles (via les compétences), pour que le solveur choisisse ensuite.
    ligne_constat = [
        "Déterminer, à partir des compétences des opérateurs, quelles équipes sont compatibles "
        "avec les tâches jamais affectées (228/1007 sur le dernier export, 23 %) — pas les "
        "affecter nous-mêmes, juste leur donner des candidates pour que le solveur choisisse.",
        "Contrainte supplémentaire",
        "api_users_competence/api_users_competenceoperateur existe côté GreenSIG mais n'est relié "
        'aux types de tâche par aucune clé fiable (noms proches mais pas identiques, ex. "Tonte" '
        'vs "Utilisation de tondeuse") — demande un mappage type_tache↔compétence validé à la '
        "main avant d'être exploitable.",
        "Constat interne — adapters/greensig/rapport_dsl.md, 2026-07-16",
    ]
    for i, valeur in enumerate(ligne_constat, start=1):
        c = ws.cell(row=6, column=i, value=valeur)
        c.font = Font(name="Calibri", size=11)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.border = BORDURE_CELLULE
    ws.row_dimensions[6].height = 60

    _bordures_vides(ws, 4, ligne_debut=7)
    dv_type = DataValidation(
        type="list",
        formula1='"Contrainte supplémentaire,Objectif supplémentaire,Autre"',
        allow_blank=True,
        showErrorMessage=True,
    )
    dv_type.error = "Choisir une valeur dans la liste (ou laisser vide)."
    ws.add_data_validation(dv_type)
    dv_type.add(f"B6:B{N_LIGNES_VALIDATION}")

    chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
    wb.save(chemin_sortie)


def main() -> None:
    construire(CHEMIN_SORTIE)
    print("écrit :", CHEMIN_SORTIE)


if __name__ == "__main__":
    main()
