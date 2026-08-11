"""Point de dispatch entre les deux chemins d'intégration GreenSIG — seul module qui connaît les
deux (`extraction.py`/`translator.py` en base directe, `extraction_api.py`/`translator_api.py` en
API HTTP publique). Sélection par `GREENSIG_MODE` (`db` par défaut, `api` en option) : les deux
adaptateurs coexistent délibérément, aucun ne remplace l'autre (voir docstrings respectifs pour
leurs limites propres — notamment la dérivation de compatibilité par compétence, exclusive au
chemin `db`).

Les deux appelants (`api/routes/planifier.py::planifier_depuis_greensig`,
`api/routes/adapters.py::ingerer_depuis_greensig`) passent par ce point unique plutôt que
d'importer directement `extraction.py`/`extraction_api.py` — pour ne jamais dupliquer la logique
de sélection de mode."""

from __future__ import annotations

import os

from dsl.schema import InstanceTRCO

from .extraction import extraire_payload
from .extraction_api import extraire_payload_api
from .translator import traduire
from .translator_api import traduire_api

MODE_PAR_DEFAUT = "db"


def extraire_et_traduire(mode: str | None = None) -> InstanceTRCO:
    """Extrait et traduit une instance T-R-C-O depuis GreenSIG, via le chemin choisi par `mode`
    (ou `GREENSIG_MODE`, `db` par défaut si absent). Les erreurs propres à chaque chemin
    (`psycopg.OperationalError` en `db`, `httpx.HTTPError` en `api`) se propagent telles quelles —
    c'est aux appelants de les convertir en réponse HTTP (même principe que les deux modules
    d'extraction eux-mêmes)."""
    mode_reel = mode or os.environ.get("GREENSIG_MODE", MODE_PAR_DEFAUT)
    if mode_reel == "api":
        return traduire_api(extraire_payload_api())
    return traduire(extraire_payload())
