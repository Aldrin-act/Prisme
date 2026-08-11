"""Extraction depuis l'API HTTP publique de GreenSIG vers `PayloadGreenSIGApi` — variante
alternative à `extraction.py` (base Postgres directe), sélectionnée par `GREENSIG_MODE=api` (voir
`service.py`).

Authentification par clé porteur (`Authorization: Bearer <clé>`, confirmé par l'en-tête
`www-authenticate: Bearer realm="api"` renvoyé par l'API sans authentification). Connexion via
`GREENSIG_API_BASE_URL`/`GREENSIG_API_KEY` — aucune valeur par défaut pour l'URL, contrairement à
`extraction.py::dsn_par_defaut` : le port `db_greensig` est fixe et partagé par tout le projet
(`docker-compose.yml`), alors que l'URL de l'API dépend entièrement du déploiement GreenSIG du
client — une absence doit lever une erreur explicite au premier appel plutôt que de retomber
silencieusement sur un mauvais hôte.

Les 5 ressources lues sont toutes en lecture seule côté API (`GET, HEAD, OPTIONS` uniquement,
vérifié) — cohérent avec le principe fondateur "generate once" : PRISME n'écrit jamais vers
GreenSIG. Les réclamations (`reclamations/`) existent côté API mais ne sont jamais lues ici — hors
périmètre, décision explicite.

Erreurs réseau (connexion, timeout, statut HTTP en erreur) laissées se propager telles quelles,
jamais avalées — même principe que `extraction.py` qui laisse `psycopg.OperationalError` remonter
tel quel ; c'est aux appelants (`api/routes/planifier.py`, `api/routes/adapters.py`) de les
convertir en réponse HTTP.
"""

from __future__ import annotations

import os

import httpx

from .schema_greensig_api import PayloadGreenSIGApi

_RESSOURCES = ("taches", "equipes", "operateurs", "absences", "jours-feries")


def config_api_par_defaut() -> tuple[str, str]:
    """`(base_url, clé)` depuis `GREENSIG_API_BASE_URL`/`GREENSIG_API_KEY` — lève `KeyError` si
    l'une des deux est absente (erreur de configuration, jamais masquée)."""
    base_url = os.environ["GREENSIG_API_BASE_URL"]
    cle = os.environ["GREENSIG_API_KEY"]
    return base_url, cle


def _pages(client: httpx.Client, chemin: str) -> list[dict]:
    """Suit `next` jusqu'à épuisement — pagination DRF standard (`count`/`next`/`previous`/`results`)."""
    resultats: list[dict] = []
    url: str | None = chemin
    while url:
        reponse = client.get(url)
        reponse.raise_for_status()
        corps = reponse.json()
        resultats.extend(corps["results"])
        url = corps.get("next")
    return resultats


def extraire_payload_api(
    base_url: str | None = None, cle: str | None = None, client: httpx.Client | None = None
) -> PayloadGreenSIGApi:
    """Interroge les 5 ressources pertinentes de l'API publique et construit un
    `PayloadGreenSIGApi` — `translator_api.traduire_api` se charge ensuite de la traduction vers
    `InstanceTRCO`.

    `client` injectable (ex. `httpx.Client(transport=httpx.MockTransport(...))`) pour les tests —
    jamais de connexion réseau réelle en test."""
    if client is not None:
        return PayloadGreenSIGApi(
            **{ressource.replace("-", "_"): _pages(client, f"{ressource}/") for ressource in _RESSOURCES}
        )

    base_url_reelle, cle_reelle = (base_url, cle) if base_url and cle else config_api_par_defaut()
    if not base_url_reelle.endswith("/"):
        base_url_reelle += "/"
    with httpx.Client(base_url=base_url_reelle, headers={"Authorization": f"Bearer {cle_reelle}"}) as c:
        return PayloadGreenSIGApi(
            **{ressource.replace("-", "_"): _pages(c, f"{ressource}/") for ressource in _RESSOURCES}
        )
