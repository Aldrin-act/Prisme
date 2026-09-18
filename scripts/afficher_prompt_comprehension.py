"""Construit et affiche le prompt système + utilisateur **réel** envoyé à l'agent de
compréhension (`adapters.agent_comprehension.agent.comprendre_donnees_erp`) pour un fichier de
données brutes donné — via `construire_prompt_comprehension`, la même fonction que la route API
`GET /sources/{source_id}/prompt-comprehension` (aperçu frontend), jamais une reconstruction
dupliquée ici.

But : normaliser la présentation de n'importe quel exemple du catalogue
`data/donnees_brutes/semi_structure/` (ou tout autre fichier texte) — même gabarit affiché,
quel que soit le fichier, plutôt qu'une commande `python -c` différente copiée-collée à chaque
fois dans une documentation.

Usage :
    uv run python -m scripts.afficher_prompt_comprehension \
        data/donnees_brutes/semi_structure/fonderie_export.json
    uv run python -m scripts.afficher_prompt_comprehension --executer \
        data/donnees_brutes/semi_structure/fonderie_export.json

`--executer` appelle réellement l'agent (coût réel en tokens, voir `PRISME_LLM_MODEL`) — absent
par défaut, seul le prompt est construit et affiché, gratuit et hors ligne.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adapters.agent_comprehension import construire_prompt_comprehension

_SEPARATEUR = "=" * 70


def main() -> None:
    # Console Windows par défaut en cp1252 — plusieurs fichiers de données brutes/gabarits
    # contiennent des caractères hors de cette table (ex. "→") ; sans ceci, print() lève
    # UnicodeEncodeError avant même d'afficher le prompt.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fichier", type=Path, help="Fichier de données brutes (texte quelconque)")
    parser.add_argument(
        "--executer",
        action="store_true",
        help="Appelle réellement l'agent (coût réel en tokens) au lieu de seulement afficher le prompt",
    )
    args = parser.parse_args()

    donnees_brutes = args.fichier.read_text(encoding="utf-8")
    prompt_systeme, prompt_utilisateur = construire_prompt_comprehension(donnees_brutes)

    print(_SEPARATEUR)
    print(f"PROMPT SYSTÈME — {args.fichier.name}")
    print(_SEPARATEUR)
    print(prompt_systeme)
    print()
    print(_SEPARATEUR)
    print("PROMPT UTILISATEUR (gabarit + règles DSL + données brutes du fichier)")
    print(_SEPARATEUR)
    print(prompt_utilisateur)

    if not args.executer:
        print(f"\n(prompt seulement — relancer avec --executer pour un vrai appel LLM sur {args.fichier.name})")
        return

    from adapters.agent_comprehension import comprendre_donnees_erp
    from generation.agents.client_llm import construire_modele_comprehension

    print(f"\n{_SEPARATEUR}\nAPPEL RÉEL EN COURS...\n{_SEPARATEUR}")
    resultat = comprendre_donnees_erp(construire_modele_comprehension(), donnees_brutes)
    print(f"\ndescription_metier :\n{resultat.description_metier}")
    print(f"\navertissements : {list(resultat.avertissements)}")
    print("\ninstance_brute :")
    print(json.dumps(resultat.instance_brute, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
