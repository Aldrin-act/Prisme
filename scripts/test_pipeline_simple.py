"""Test simple et rapide du pipeline avec benchmarker."""

from __future__ import annotations

import sys
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Forcer flush immediat
import functools
print = functools.partial(print, flush=True)

try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass

print("Debut du test...", flush=True)

try:
    print("Import du client LLM...", flush=True)
    from generation.agents.client_llm import construire_appel_llm

    print("Import du pipeline...", flush=True)
    from generation.pipeline_multi_agents import tenter_generation_multi_agents

    print("Construction du client LLM...", flush=True)
    appel_llm = construire_appel_llm()

    print(f"Client LLM pret : {type(appel_llm).__name__}", flush=True)

    print("\nLancement du pipeline (instance par defaut 10 taches)...", flush=True)
    print("Cela va prendre 2-3 minutes...\n", flush=True)

    resultat = tenter_generation_multi_agents(appel_llm)

    print("\n" + "="*70, flush=True)
    print("RESULTAT", flush=True)
    print("="*70, flush=True)
    print(f"Algorithme recommande : {resultat.algorithme_recommande}", flush=True)
    print(f"Justification : {resultat.justification_algorithme[:200]}...", flush=True)
    print(f"Succes : {resultat.reussi}", flush=True)

except Exception as e:
    print(f"\nERREUR : {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTermine !", flush=True)
