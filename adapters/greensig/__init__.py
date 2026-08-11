"""greensig — Adaptateurs pour un ERP réel de gestion d'espaces verts (§5.4) : deux chemins
d'intégration coexistants, base Postgres directe (`extraction.py`/`translator.py`) et API HTTP
publique (`extraction_api.py`/`translator_api.py`), sélectionnés via `GREENSIG_MODE` par
`service.py::extraire_et_traduire` — voir sa docstring pour le détail des différences."""

from .extraction import extraire_payload
from .extraction_api import extraire_payload_api
from .schema_greensig import (
    CompetenceGreenSIG,
    EquipeGreenSIG,
    OperateurGreenSIG,
    PayloadGreenSIG,
    TacheGreenSIG,
    TypeTacheGreenSIG,
)
from .schema_greensig_api import (
    AbsenceApiGreenSIG,
    EquipeApiGreenSIG,
    JourFerieApiGreenSIG,
    OperateurApiGreenSIG,
    PayloadGreenSIGApi,
    TacheApiGreenSIG,
)
from .service import extraire_et_traduire
from .translator import traduire
from .translator_api import traduire_api

__all__ = [
    "AbsenceApiGreenSIG",
    "CompetenceGreenSIG",
    "EquipeApiGreenSIG",
    "EquipeGreenSIG",
    "JourFerieApiGreenSIG",
    "OperateurApiGreenSIG",
    "OperateurGreenSIG",
    "PayloadGreenSIG",
    "PayloadGreenSIGApi",
    "TacheApiGreenSIG",
    "TacheGreenSIG",
    "TypeTacheGreenSIG",
    "extraire_et_traduire",
    "extraire_payload",
    "extraire_payload_api",
    "traduire",
    "traduire_api",
]
