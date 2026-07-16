"""Dépendances FastAPI partagées entre les routes."""

from __future__ import annotations

from solver_store.registry import Registre

_REGISTRE_GLOBAL: Registre | None = None


def obtenir_registre() -> Registre:
    """Instanciation paresseuse : `Registre()` ouvre une connexion Postgres
    (§7.2) — la retarder jusqu'au premier appel réel évite qu'un simple
    `import api.app` échoue si la base n'est pas encore joignable (les tests
    qui substituent cette dépendance via `app.dependency_overrides` ne
    l'appellent d'ailleurs jamais)."""
    global _REGISTRE_GLOBAL
    if _REGISTRE_GLOBAL is None:
        _REGISTRE_GLOBAL = Registre()
    return _REGISTRE_GLOBAL
