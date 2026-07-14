"""Dépendances FastAPI partagées entre les routes."""

from __future__ import annotations

from solver_store.registry import Registre

_REGISTRE_GLOBAL = Registre()


def obtenir_registre() -> Registre:
    return _REGISTRE_GLOBAL
