"""Installe les dépendances LLM sans uv."""

import subprocess
import sys

packages = [
    "anthropic>=0.25.0",
    "openai>=1.0.0",
    "mistralai>=0.1.0",
    "python-dotenv>=1.0.0",
]

print("📦 Installation des dépendances LLM...\n")

for package in packages:
    print(f"   Installing {package}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Erreur : {e}")
        sys.exit(1)

print("\n✅ Dépendances LLM installées !")
print("\nVous pouvez maintenant lancer :")
print("   python -m scripts.generer_premier_solveur")
