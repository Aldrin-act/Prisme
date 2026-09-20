"""Couche 1 (§6.1) : la validation statique est écrite à la main,
déterministe — le premier garde-fou avant toute exécution de code généré
(§5.3). Liste blanche : tout ce qui n'est pas explicitement permis est
rejeté.
"""

from __future__ import annotations

import pytest

from generation.validation_statique import valider_code_genere

CODE_LEGITIME = """
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import heapq
import random

from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, OperationPlanifiee, Planning, Precedence


def resoudre(instance: InstanceTRCO) -> Planning | None:
    rng = random.Random(42)
    file_evenements: list[int] = []
    heapq.heappush(file_evenements, rng.randint(0, 9))
    return Planning(operations=[])
"""


@pytest.mark.parametrize(
    "code",
    [
        "import os\n",
        "import subprocess\n",
        "from socket import socket\n",
        "import sys\n",
        "from os import path\n",
        "import shutil\n",
        "import importlib\n",
        "import time\n",
        "import ortools.sat.python.cp_model\n",
        "from ortools.sat.python import cp_model\n",
    ],
)
def test_import_interdit_est_rejete(code: str) -> None:
    resultat = valider_code_genere(code)

    assert not resultat.valide
    assert any("import interdit" in violation for violation in resultat.violations)


@pytest.mark.parametrize(
    "code",
    [
        "eval('1 + 1')\n",
        "exec('print(1)')\n",
        "compile('1', '<s>', 'eval')\n",
        "__import__('os')\n",
        "open('fichier.txt')\n",
        "input()\n",
    ],
)
def test_appel_interdit_est_rejete(code: str) -> None:
    resultat = valider_code_genere(code)

    assert not resultat.valide
    assert any("appel interdit" in violation for violation in resultat.violations)


@pytest.mark.parametrize(
    "code",
    [
        "().__class__.__bases__[0].__subclasses__()\n",
        "(lambda: 0).__globals__\n",
    ],
)
def test_attribut_interdit_est_rejete(code: str) -> None:
    resultat = valider_code_genere(code)

    assert not resultat.valide
    assert any("attribut interdit" in violation for violation in resultat.violations)


def test_erreur_de_syntaxe_est_rejetee() -> None:
    resultat = valider_code_genere("def resoudre(instance:\n")

    assert not resultat.valide
    assert any("erreur de syntaxe" in violation for violation in resultat.violations)


def test_code_legitime_avec_imports_autorises_est_accepte() -> None:
    resultat = valider_code_genere(CODE_LEGITIME)

    assert resultat.valide
    assert resultat.violations == ()


def test_import_dsl_schema_et_utilitaires_purs_sont_acceptes() -> None:
    code = (
        "import heapq\n"
        "import itertools\n"
        "import bisect\n"
        "import functools\n"
        "import copy\n"
        "from dsl.schema import InstanceTRCO\n"
        "from dsl import schema\n"
    )
    resultat = valider_code_genere(code)

    assert resultat.valide
    assert resultat.violations == ()
