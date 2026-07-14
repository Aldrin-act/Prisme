"""Types partagés par les quatre axes du DSL T-R-C-O."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

# Vocabulaire fini et typé (§4.1, §5.3) : un identifiant est une chaîne courte,
# restreinte à un alphabet simple, pour borner la surface de génération.
Identifiant = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
]
