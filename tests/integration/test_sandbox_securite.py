"""Couche 1 (§6.1), Docker requis. Test de sécurité de l'Étape 7 : un code
malveillant injecté dans le sandbox ne peut ni accéder au réseau ni sortir
du conteneur (écrire hors des points de montage prévus).

Ce code malveillant est fourni directement à `executer_dans_sandbox`, en
contournant délibérément `generation/validation_statique.py` (le garde-fou
par AST) : l'objectif ici est de vérifier la couche d'isolation du
*conteneur* lui-même — défense en profondeur, indépendante de ce que l'AST
aurait ou non intercepté en amont (§5.3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dsl.schema import CompatibiliteMachineTache, InstanceTRCO, MinimiserMakespan, Ressource, Tache
from sandbox.runner import ErreurExecutionSandbox, executer_dans_sandbox

CODE_TENTATIVE_RESEAU = """
import socket

def resoudre(instance):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect(("8.8.8.8", 53))
    return None
"""

CODE_TENTATIVE_ECRITURE_HORS_MONTAGE = """
def resoudre(instance):
    with open("/etc/malveillant.txt", "w") as fichier:
        fichier.write("evasion")
    return None
"""


def _instance_triviale() -> InstanceTRCO:
    return InstanceTRCO(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="M1")],
        contraintes=[CompatibiliteMachineTache(tache="T1", ressource="M1", duree=10)],
        objectifs=[MinimiserMakespan()],
    )


def test_acces_reseau_est_bloque(tmp_path: Path, image_sandbox: str) -> None:
    chemin_code = tmp_path / "malveillant_reseau.py"
    chemin_code.write_text(CODE_TENTATIVE_RESEAU, encoding="utf-8")

    with pytest.raises(ErreurExecutionSandbox) as excinfo:
        executer_dans_sandbox(chemin_code, _instance_triviale())

    message = str(excinfo.value).lower()
    assert "network" in message or "unreachable" in message or "réseau" in message


def test_ecriture_hors_des_points_de_montage_est_bloquee(tmp_path: Path, image_sandbox: str) -> None:
    chemin_code = tmp_path / "malveillant_ecriture.py"
    chemin_code.write_text(CODE_TENTATIVE_ECRITURE_HORS_MONTAGE, encoding="utf-8")

    with pytest.raises(ErreurExecutionSandbox) as excinfo:
        executer_dans_sandbox(chemin_code, _instance_triviale())

    message = str(excinfo.value).lower()
    assert "read-only" in message or "readonly" in message or "lecture seule" in message
