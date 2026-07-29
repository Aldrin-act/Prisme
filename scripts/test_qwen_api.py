"""Test de l'API Qwen via Together AI."""

from __future__ import annotations

import sys
from pathlib import Path

projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
    print("Fichier .env charge")
except ImportError:
    print("Warning: python-dotenv non installe")

import os

print("\nConfiguration actuelle :")
print(f"  PRISME_LLM_PROVIDER : {os.environ.get('PRISME_LLM_PROVIDER')}")
print(f"  PRISME_LLM_MODEL : {os.environ.get('PRISME_LLM_MODEL')}")
print(f"  TOGETHER_API_KEY : {'***' + os.environ.get('TOGETHER_API_KEY', '')[-8:] if os.environ.get('TOGETHER_API_KEY') else 'NON DEFINIE'}")
print()

if not os.environ.get("TOGETHER_API_KEY") or os.environ.get("TOGETHER_API_KEY") == "VOTRE_CLE_API_TOGETHER_ICI":
    print("ERREUR : TOGETHER_API_KEY non configuree dans .env")
    print("Veuillez remplacer VOTRE_CLE_API_TOGETHER_ICI par votre vraie cle API Together")
    print("Obtenez une cle sur : https://api.together.xyz/settings/api-keys")
    sys.exit(1)

print("Test de connexion a l'API Qwen...\n")

try:
    from langchain_core.messages import HumanMessage, SystemMessage

    from generation.agents.client_llm import construire_modele

    modele = construire_modele()
    print(f"Client LLM cree : {type(modele).__name__}")
    print()

    print("Envoi d'un prompt de test...")
    message = modele.invoke([
        SystemMessage(content="Tu es un assistant utile."),
        HumanMessage(content="Reponds simplement 'Bonjour! Je suis Qwen et je fonctionne correctement.'"),
    ])
    reponse = message.content if isinstance(message.content, str) else str(message.content)

    print("\nReponse recue :")
    print(f"  {reponse}")
    print()

    if "Qwen" in reponse or "bonjour" in reponse.lower():
        print("SUCCES : L'API Qwen fonctionne correctement !")
    else:
        print("ATTENTION : Reponse inattendue, mais l'API repond")

    print()

except Exception as e:
    print(f"\nERREUR : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Test termine avec succes !")
print()
print("Vous pouvez maintenant lancer le pipeline avec :")
print("  python -m scripts.test_pipeline_simple")
