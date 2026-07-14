"""Fixtures partagées pour les tests d'intégration qui nécessitent Docker
(§7). Ces tests sont ignorés (skip), pas en échec, si Docker n'est pas
disponible dans l'environnement d'exécution.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[2]


def _docker_disponible() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def image_sandbox() -> str:
    """Construit (si besoin) l'image du sandbox ; saute les tests si Docker
    est indisponible plutôt que de les faire échouer."""
    if not _docker_disponible():
        pytest.skip("Docker indisponible dans cet environnement")

    import docker

    from sandbox.runner import IMAGE_SANDBOX

    client = docker.from_env()
    client.images.build(
        path=str(RACINE_DEPOT),
        dockerfile=str(RACINE_DEPOT / "sandbox" / "container" / "Dockerfile"),
        tag=IMAGE_SANDBOX,
    )
    return IMAGE_SANDBOX
