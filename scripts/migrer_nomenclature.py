"""Script de migration de la nomenclature : Ressource → Ressource

Corrige automatiquement tous les fichiers du projet pour utiliser la
nomenclature officielle du DSL T-R-C-O.

Usage:
    # Dry-run (prévisualisation sans modification)
    uv run python -m scripts.migrer_nomenclature --dry-run

    # Application réelle
    uv run python -m scripts.migrer_nomenclature

    # Application avec backup
    uv run python -m scripts.migrer_nomenclature --backup

    # Cibler des fichiers spécifiques
    uv run python -m scripts.migrer_nomenclature --path dsl/examples/
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable


@dataclass
class RegleMigration:
    """Une règle de remplacement avec son pattern et sa fonction."""

    nom: str
    pattern: re.Pattern
    remplacement: str | Callable[[re.Match], str]
    description: str
    categories: list[str] = field(default_factory=list)


@dataclass
class Correction:
    """Une correction détectée dans un fichier."""

    fichier: Path
    ligne: int
    ancien: str
    nouveau: str
    regle: str
    contexte: str


@dataclass
class RapportMigration:
    """Rapport de migration pour un fichier."""

    fichier: Path
    corrections: list[Correction]
    saute: bool = False
    raison_saut: str | None = None
    erreur: str | None = None


# ============================================================================
# Règles de migration
# ============================================================================

REGLES_IDENTIFIANTS = [
    RegleMigration(
        nom="id_machine_simple",
        pattern=re.compile(r'"(M\d+)"'),
        remplacement=lambda m: f'"R{m.group(1)[1:]}"',
        description='Identifiants "R1", "R2" → "R1", "R2"',
        categories=["identifiants", "critique"],
    ),
    RegleMigration(
        nom="id_machine_prefix",
        pattern=re.compile(r'"(MACHINE_[A-Z0-9_]+)"'),
        remplacement=lambda m: f'"RESSOURCE_{m.group(1)[8:]}"',
        description='"RESSOURCE_XXX" → "RESSOURCE_XXX"',
        categories=["identifiants", "critique"],
    ),
    RegleMigration(
        nom="id_machine_name",
        pattern=re.compile(r'"(machine_[a-z0-9_]+)"'),
        remplacement=lambda m: f'"ressource_{m.group(1)[8:]}"',
        description='"ressource_xxx" → "ressource_xxx"',
        categories=["identifiants", "critique"],
    ),
]

REGLES_CHAMPS_JSON = [
    RegleMigration(
        nom="champ_machines",
        pattern=re.compile(r'"machines"(\s*:)'),
        remplacement=r'"ressources"\1',
        description='Champ "machines" → "ressources"',
        categories=["champs", "json"],
    ),
    RegleMigration(
        nom="champ_machine_id",
        pattern=re.compile(r'"ressource_id"(\s*:)'),
        remplacement=r'"ressource_id"\1',
        description='Champ "ressource_id" → "ressource_id"',
        categories=["champs", "json"],
    ),
    RegleMigration(
        nom="champ_machine_ids",
        pattern=re.compile(r'"ressource_ids"(\s*:)'),
        remplacement=r'"ressource_ids"\1',
        description='Champ "ressource_ids" → "ressource_ids"',
        categories=["champs", "json"],
    ),
    RegleMigration(
        nom="champ_par_ressource",
        pattern=re.compile(r'"(\w+)_par_machine"(\s*:)'),
        remplacement=r'"\1_par_ressource"\2',
        description='"*_par_machine" → "*_par_ressource"',
        categories=["champs", "json"],
    ),
    RegleMigration(
        nom="champ_de_machine",
        pattern=re.compile(r'"(\w+)_de_machine"(\s*:)'),
        remplacement=r'"\1_de_ressource"\2',
        description='"*_de_machine" → "*_de_ressource"',
        categories=["champs", "json"],
    ),
]

REGLES_PYTHON = [
    RegleMigration(
        nom="variable_machines",
        pattern=re.compile(r'\bmachines\b(?=\s*[=:\[]|\s*in\s)'),
        remplacement="ressources",
        description='Variable "machines" → "ressources"',
        categories=["python", "variables"],
    ),
    RegleMigration(
        nom="variable_machine_id",
        pattern=re.compile(r'\bmachine_id\b'),
        remplacement="ressource_id",
        description='Variable "ressource_id" → "ressource_id"',
        categories=["python", "variables"],
    ),
    RegleMigration(
        nom="type_Machine",
        pattern=re.compile(r'\bMachine\b(?=\s*[:\(])'),
        remplacement="Ressource",
        description='Type "Machine" → "Ressource"',
        categories=["python", "types"],
    ),
    RegleMigration(
        nom="param_par_ressource",
        pattern=re.compile(r'\b(\w+)_par_machine\b'),
        remplacement=r'\1_par_ressource',
        description='Paramètre "*_par_machine" → "*_par_ressource"',
        categories=["python", "parametres"],
    ),
]

REGLES_COMMENTAIRES = [
    RegleMigration(
        nom="commentaire_machine",
        pattern=re.compile(r'\b([Mm]achine)s?\b(?![_"\'])'),
        remplacement=lambda m: "Ressource" if m.group(1)[0].isupper() else "ressource",
        description='Commentaire "ressource(s)" → "ressource(s)"',
        categories=["commentaires", "documentation"],
    ),
]

TOUTES_LES_REGLES = (
    REGLES_IDENTIFIANTS + REGLES_CHAMPS_JSON + REGLES_PYTHON + REGLES_COMMENTAIRES
)


# ============================================================================
# Moteur de migration
# ============================================================================


class MigrateurNomenclature:
    """Migre la nomenclature dans tous les fichiers du projet."""

    def __init__(
        self,
        racine: Path,
        dry_run: bool = True,
        backup: bool = False,
        verbeux: bool = True,
    ):
        self.racine = racine
        self.dry_run = dry_run
        self.backup = backup
        self.verbeux = verbeux
        self.rapports: list[RapportMigration] = []

    def migrer(
        self,
        patterns_fichiers: list[str] | None = None,
        exclure: list[str] | None = None,
    ) -> list[RapportMigration]:
        """Lance la migration sur les fichiers correspondants.

        Args:
            patterns_fichiers: Patterns glob (ex: ["**/*.py", "**/*.json"])
            exclure: Patterns à exclure (ex: ["**/node_modules/**"])

        Returns:
            Liste des rapports de migration
        """
        patterns_fichiers = patterns_fichiers or [
            "**/*.py",
            "**/*.json",
            "**/*.md",
            "**/*.txt",
        ]

        exclure = exclure or [
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/.git/**",
            "**/venv/**",
            "**/.venv/**",
            "**/uv.lock",
            "**/migrations/**",  # Ce script lui-même !
        ]

        fichiers = self._collecter_fichiers(patterns_fichiers, exclure)

        if self.verbeux:
            print(f"🔍 {len(fichiers)} fichiers à analyser...")
            print()

        for fichier in fichiers:
            rapport = self._migrer_fichier(fichier)
            if rapport and (rapport.corrections or rapport.erreur):
                self.rapports.append(rapport)

        return self.rapports

    def _collecter_fichiers(
        self, patterns: list[str], exclure: list[str]
    ) -> list[Path]:
        """Collecte tous les fichiers à migrer."""
        fichiers = set()

        for pattern in patterns:
            for fichier in self.racine.glob(pattern):
                if fichier.is_file():
                    # Vérifier les exclusions
                    exclus = False
                    for pattern_exclusion in exclure:
                        if fichier.match(pattern_exclusion):
                            exclus = True
                            break

                    if not exclus:
                        fichiers.add(fichier)

        return sorted(fichiers)

    def _migrer_fichier(self, fichier: Path) -> RapportMigration | None:
        """Migre un fichier unique."""
        try:
            # Lire le contenu
            with open(fichier, "r", encoding="utf-8") as f:
                contenu_original = f.read()

            # Détecter les corrections
            corrections = self._detecter_corrections(fichier, contenu_original)

            if not corrections:
                return None  # Rien à corriger

            # Appliquer les corrections
            contenu_nouveau = self._appliquer_corrections(
                contenu_original, corrections
            )

            # Créer le rapport
            rapport = RapportMigration(fichier=fichier, corrections=corrections)

            # Écrire les changements (si pas dry-run)
            if not self.dry_run:
                # Backup si demandé
                if self.backup:
                    self._creer_backup(fichier)

                with open(fichier, "w", encoding="utf-8") as f:
                    f.write(contenu_nouveau)

            # Affichage
            if self.verbeux:
                self._afficher_rapport(rapport)

            return rapport

        except Exception as e:
            return RapportMigration(
                fichier=fichier,
                corrections=[],
                saute=True,
                erreur=str(e),
            )

    def _detecter_corrections(
        self, fichier: Path, contenu: str
    ) -> list[Correction]:
        """Détecte toutes les corrections nécessaires."""
        corrections = []
        lignes = contenu.split("\n")

        # Choisir les règles selon le type de fichier
        regles = self._filtrer_regles(fichier)

        for numero_ligne, ligne in enumerate(lignes, start=1):
            for regle in regles:
                for match in regle.pattern.finditer(ligne):
                    # Calculer le remplacement
                    if callable(regle.remplacement):
                        nouveau = regle.remplacement(match)
                    else:
                        nouveau = match.expand(regle.remplacement)

                    corrections.append(
                        Correction(
                            fichier=fichier,
                            ligne=numero_ligne,
                            ancien=match.group(0),
                            nouveau=nouveau,
                            regle=regle.nom,
                            contexte=ligne.strip()[:80],
                        )
                    )

        return corrections

    def _filtrer_regles(self, fichier: Path) -> list[RegleMigration]:
        """Filtre les règles selon le type de fichier."""
        extension = fichier.suffix.lower()

        if extension == ".json":
            return REGLES_IDENTIFIANTS + REGLES_CHAMPS_JSON
        elif extension == ".py":
            return TOUTES_LES_REGLES
        elif extension in [".md", ".txt"]:
            return REGLES_IDENTIFIANTS + REGLES_COMMENTAIRES
        else:
            return REGLES_IDENTIFIANTS  # Par défaut

    def _appliquer_corrections(
        self, contenu: str, corrections: list[Correction]
    ) -> str:
        """Applique toutes les corrections au contenu."""
        lignes = contenu.split("\n")

        # Grouper corrections par ligne
        corrections_par_ligne: dict[int, list[Correction]] = {}
        for correction in corrections:
            numero = correction.ligne
            if numero not in corrections_par_ligne:
                corrections_par_ligne[numero] = []
            corrections_par_ligne[numero].append(correction)

        # Appliquer ligne par ligne
        for numero_ligne, corrections_ligne in corrections_par_ligne.items():
            ligne_originale = lignes[numero_ligne - 1]
            ligne_nouvelle = ligne_originale

            # Trier par position pour appliquer de droite à gauche
            for correction in sorted(
                corrections_ligne,
                key=lambda c: ligne_originale.find(c.ancien),
                reverse=True,
            ):
                ligne_nouvelle = ligne_nouvelle.replace(
                    correction.ancien, correction.nouveau, 1
                )

            lignes[numero_ligne - 1] = ligne_nouvelle

        return "\n".join(lignes)

    def _creer_backup(self, fichier: Path) -> None:
        """Crée une copie de backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = fichier.with_suffix(f"{fichier.suffix}.backup_{timestamp}")
        shutil.copy2(fichier, backup_path)

    def _afficher_rapport(self, rapport: RapportMigration) -> None:
        """Affiche le rapport pour un fichier."""
        nb = len(rapport.corrections)
        print(f"📝 {rapport.fichier.relative_to(self.racine)}")
        print(f"   {nb} correction(s)")

        for correction in rapport.corrections[:5]:  # Max 5 par fichier
            print(f"   L{correction.ligne}: {correction.ancien} → {correction.nouveau}")

        if nb > 5:
            print(f"   ... et {nb - 5} autre(s)")

        print()

    def generer_rapport_complet(self, output: Path | None = None) -> str:
        """Génère un rapport Markdown complet."""
        lignes = [
            "# Rapport de migration de nomenclature",
            "",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Mode: {'DRY-RUN (simulation)' if self.dry_run else 'RÉEL (modifications appliquées)'}",
            "",
            "## Résumé",
            "",
        ]

        total_fichiers = len(self.rapports)
        total_corrections = sum(len(r.corrections) for r in self.rapports)
        fichiers_erreur = sum(1 for r in self.rapports if r.erreur)

        lignes.extend(
            [
                f"- Fichiers modifiés : **{total_fichiers}**",
                f"- Corrections appliquées : **{total_corrections}**",
                f"- Erreurs : **{fichiers_erreur}**",
                "",
            ]
        )

        # Par catégorie de règle
        corrections_par_regle: dict[str, int] = {}
        for rapport in self.rapports:
            for correction in rapport.corrections:
                corrections_par_regle[correction.regle] = (
                    corrections_par_regle.get(correction.regle, 0) + 1
                )

        if corrections_par_regle:
            lignes.extend(
                [
                    "## Corrections par type",
                    "",
                ]
            )
            for regle, count in sorted(
                corrections_par_regle.items(), key=lambda x: x[1], reverse=True
            ):
                lignes.append(f"- `{regle}` : {count} occurrence(s)")
            lignes.append("")

        # Détail par fichier
        if self.rapports:
            lignes.extend(
                [
                    "## Détail par fichier",
                    "",
                ]
            )

            for rapport in self.rapports:
                lignes.append(
                    f"### {rapport.fichier.relative_to(self.racine)}"
                )
                lignes.append("")

                if rapport.erreur:
                    lignes.append(f"❌ **Erreur** : {rapport.erreur}")
                    lignes.append("")
                    continue

                lignes.append(f"{len(rapport.corrections)} correction(s) :")
                lignes.append("")

                for correction in rapport.corrections:
                    lignes.append(
                        f"- L{correction.ligne}: `{correction.ancien}` → `{correction.nouveau}`"
                    )

                lignes.append("")

        rapport_md = "\n".join(lignes)

        # Écrire dans un fichier si demandé
        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(rapport_md)

        return rapport_md


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Migre la nomenclature Ressource → Ressource",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Dry-run (prévisualisation)
  python -m scripts.migrer_nomenclature --dry-run

  # Application réelle avec backup
  python -m scripts.migrer_nomenclature --backup

  # Cibler un dossier spécifique
  python -m scripts.migrer_nomenclature --path dsl/examples/

  # Générer un rapport
  python -m scripts.migrer_nomenclature --dry-run --rapport rapport.md
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode simulation (aucune modification)",
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        help="Créer des backups avant modification",
    )

    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Chemin spécifique à migrer (défaut: tout le projet)",
    )

    parser.add_argument(
        "--rapport",
        type=Path,
        default=None,
        help="Générer un rapport Markdown",
    )

    parser.add_argument(
        "--silencieux",
        action="store_true",
        help="Pas d'affichage progressif",
    )

    args = parser.parse_args()

    # Déterminer la racine
    racine = Path(__file__).resolve().parents[1]
    if args.path:
        racine = args.path if args.path.is_absolute() else racine / args.path

    # Créer le migrateur
    migrateur = MigrateurNomenclature(
        racine=racine,
        dry_run=args.dry_run,
        backup=args.backup,
        verbeux=not args.silencieux,
    )

    # Lancer la migration
    print("🚀 Lancement de la migration de nomenclature...")
    print(f"📁 Racine: {racine}")
    print(f"🔧 Mode: {'DRY-RUN' if args.dry_run else 'RÉEL'}")
    print()

    rapports = migrateur.migrer()

    # Résumé
    print("\n" + "=" * 60)
    print("✅ Migration terminée !")
    print(f"📊 {len(rapports)} fichier(s) modifié(s)")
    print(
        f"🔧 {sum(len(r.corrections) for r in rapports)} correction(s) au total"
    )

    if args.dry_run:
        print("\n⚠️  Mode DRY-RUN : aucun fichier n'a été modifié")
        print("   Relancez sans --dry-run pour appliquer les changements")

    # Générer le rapport
    if args.rapport or args.dry_run:
        rapport_path = args.rapport or racine / "rapport_migration.md"
        migrateur.generer_rapport_complet(rapport_path)
        print(f"\n📄 Rapport généré : {rapport_path}")

    return 0 if not any(r.erreur for r in rapports) else 1


if __name__ == "__main__":
    exit(main())
