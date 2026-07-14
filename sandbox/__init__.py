"""sandbox — Exécution éphémère en conteneur jetable (§5.2, §5.3, §7).

Le SDK `docker` est importé à la demande (extra optionnel `sandbox`,
`pip install -e .[sandbox]`) : `import sandbox` ne requiert pas Docker.
"""

from .runner import (
    ErreurExecutionSandbox,
    LimitesSandbox,
    ResultatExecution,
    executer_dans_sandbox,
    executer_solveur_valide,
)

__all__ = [
    "ErreurExecutionSandbox",
    "LimitesSandbox",
    "ResultatExecution",
    "executer_dans_sandbox",
    "executer_solveur_valide",
]
