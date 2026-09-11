"""Script simple pour convertir vos fichiers CSV en instances TRCO.

Usage direct:
    python convertir_mes_csv.py
"""

from __future__ import annotations

from pathlib import Path

from scripts.convertir_csv_vers_instance import csv_vers_instance


def main():
    """Convertit le dossier CSV spécifié par l'utilisateur."""
    # Le chemin vers vos CSV
    chemin_csv = r"c:\Users\ASUS\Desktop\PFE\Prisme\Prisme\data\donnees_brutes\csv"

    print("Conversion des fichiers CSV en instances TRCO")
    print("=" * 80)
    print(f"Repertoire source: {chemin_csv}\n")

    # Trouver tous les dossiers contenant des CSV
    racine = Path(chemin_csv)
    dossiers_avec_csv = []

    for chemin in racine.rglob("*"):
        if chemin.is_dir():
            # Vérifier si les trois fichiers requis existent
            if (
                (chemin / "taches.csv").exists()
                and (chemin / "ressources.csv").exists()
                and (chemin / "contraintes.csv").exists()
            ):
                dossiers_avec_csv.append(chemin)

    print(f"Dossiers trouves: {len(dossiers_avec_csv)}\n")

    # Convertir chaque dossier
    for i, dossier in enumerate(sorted(dossiers_avec_csv), 1):
        chemin_relatif = dossier.relative_to(racine)
        print(f"\n[{i}/{len(dossiers_avec_csv)}] {chemin_relatif}")
        print("-" * 80)

        try:
            # Convertir en instance TRCO
            instance = csv_vers_instance(dossier)

            # Afficher les statistiques
            print(f"  Taches:      {len(instance.taches)}")
            print(f"  Ressources:  {len(instance.ressources)}")
            print(f"  Contraintes: {len(instance.contraintes)}")
            print(f"  Objectifs:   {len(instance.objectifs)}")

            # Optionnel: sauvegarder en JSON
            # nom_fichier = f"instance_{chemin_relatif.name}.json"
            # with open(nom_fichier, "w", encoding="utf-8") as f:
            #     json.dump(instance.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
            # print(f"  Sauvegarde:  {nom_fichier}")

            print("  [OK] Conversion reussie")

        except Exception as e:
            print(f"  [ERREUR] {e}")

    print("\n" + "=" * 80)
    print("Conversion terminee!")


if __name__ == "__main__":
    main()
