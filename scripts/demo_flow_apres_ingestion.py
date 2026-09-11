"""Démo pratique : Flow complet après l'ingestion.

Montre les étapes 2-6 du cycle PRISME en utilisant le solveur de référence.
"""

from __future__ import annotations

import json
from pathlib import Path


def afficher_etape(numero: int, titre: str) -> None:
    """Affiche un en-tête d'étape."""
    print("\n" + "=" * 70)
    print(f"  ÉTAPE {numero} : {titre}")
    print("=" * 70 + "\n")


def demo_flow():
    """Démontre le flow après ingestion."""
    print("\n" + "🔄" * 35)
    print("  DÉMONSTRATION : FLOW APRÈS INGESTION")
    print("🔄" * 35 + "\n")

    print("📖 Ce script montre ce qui se passe APRÈS avoir ingéré des données ERP.")
    print("   On suppose que l'Étape 1 (Ingestion) est déjà terminée avec succès.\n")

    # ========================================================================
    # ÉTAPE 1 : Instance T-R-C-O disponible
    # ========================================================================

    afficher_etape(1, "Instance T-R-C-O validée (POST-INGESTION)")

    print("✅ Nous avons déjà une InstanceTRCO valide depuis l'ingestion.")
    print("   Exemple : atelier_trois_taches.json\n")

    chemin_instance = Path(__file__).parent.parent / "dsl/examples/valid/atelier_trois_taches.json"

    with open(chemin_instance, encoding="utf-8") as f:
        instance_data = json.load(f)

    print("📄 Contenu de l'instance :")
    print(f"   - {len(instance_data['taches'])} tâche(s)")
    print(f"   - {len(instance_data['ressources'])} ressource(s)")
    print(f"   - {len(instance_data['contraintes'])} contrainte(s)")

    # Signature de contraintes
    types_contraintes = sorted(set(c["type"] for c in instance_data["contraintes"]))
    signature = ",".join(types_contraintes)

    print(f"\n🔑 Signature des contraintes : {signature}")
    print("   (Utilisée pour lookup du solveur)")

    # ========================================================================
    # ÉTAPE 2 : Lookup ou Génération du solveur
    # ========================================================================

    afficher_etape(2, "Lookup / Génération du solveur")

    print("🔍 Le système cherche un solveur existant pour cette signature...")
    print("   - client_id : 'client_test_1'")
    print(f"   - signature : '{signature}'")

    print("\n💡 Deux cas possibles :")
    print("   A) Solveur EXISTE déjà → Skip génération, passer à Étape 4 (Exécution)")
    print("   B) Solveur N'EXISTE PAS → Génération nécessaire (ci-dessous)\n")

    print("⚠️  GÉNÉRATION (si nécessaire) :")
    print("   1. LLM reçoit l'InstanceTRCO et génère du code Python CP-SAT")
    print("   2. Validation statique (AST allowlist)")
    print("   3. Exécution test sur l'instance source")
    print("   4. Cascade de validation (faisabilité, optimalité, fidélité)")
    print("   5. Si VERT → Enregistrement dans solver_store/")
    print("   6. Si ROUGE → Alerte humain, pas d'action automatique")

    print("\n💰 Coût génération : ~$0.05-0.10 (Anthropic Claude)")
    print("⏱️  Temps génération : ~30-60 secondes")
    print("🎯 Taux de succès attendu : 60-80% (non mesuré en production)")

    print("\n✅ Pour cette démo, on suppose que le solveur de référence existe déjà.")

    # ========================================================================
    # ÉTAPE 3 : Stockage (si génération a eu lieu)
    # ========================================================================

    afficher_etape(3, "Stockage (si génération)")

    print("💾 Si un solveur vient d'être généré, il est enregistré :")
    print("   - Fichier : solver_store/artifacts/<sha256>.py (code Python frozen)")
    print("   - Base de données : métadonnées (client_id, signature, verdict)")
    print("   - Index : permet lookup rapide lors des exécutions futures\n")

    print("🔒 Sécurité :")
    print("   - Seuls les solveurs avec verdict VERT sont acceptés")
    print("   - Hash SHA-256 vérifié à chaque retrieval")
    print("   - Code jamais modifié après enregistrement (immutable)")

    # ========================================================================
    # ÉTAPE 4 : Exécution dans le sandbox
    # ========================================================================

    afficher_etape(4, "Exécution dans sandbox Docker")

    print("🐳 Le solveur est exécuté dans un conteneur éphémère isolé :")
    print("   - Image : prisme-sandbox (Debian minimal + Python 3.11 + OR-Tools)")
    print("   - Mode : --rm (détruit après exécution)")
    print("   - Réseau : désactivé (--network none)")
    print("   - Filesystem : read-only sauf /tmp")
    print("   - User : non-root (uid 10001)")
    print("   - Limites : CPU, mémoire, PIDs, timeout\n")

    print("📥 Input :")
    print("   - InstanceTRCO (JSON sérialisé)")
    print("   - Code solveur (copié dans /tmp/solveur.py)")

    print("\n⚙️  Exécution :")
    print("   - Le harness charge le module")
    print("   - Appelle resoudre(instance) → Planning | None")
    print("   - Sérialise le résultat en JSON")

    print("\n📤 Output :")
    print("   - Planning JSON (si succès)")
    print("   - None (si infeasible)")
    print("   - Exception (si crash du solveur)")

    print("\n⏱️  Temps : 1-5 secondes selon taille instance")

    # ========================================================================
    # ÉTAPE 5 : Validation opérationnelle (§6.7)
    # ========================================================================

    afficher_etape(5, "Validation opérationnelle (Garde-fou)")

    print("🔒 Le planning généré passe par le feasibility checker :")
    print("   ✓ Précédences respectées (avant → après)")
    print("   ✓ Compatibilité ressource-tâche (duree correspondante)")
    print("   ✓ Une seule affectation par tâche")
    print("   ✓ Pas de chevauchement sur une ressource")
    print("   ✓ Dates cohérentes (debut + duree = fin)")

    print("\n📊 Résultat possible :")
    print("   ✅ VALIDE → Passer à Étape 6 (Output)")
    print("   ❌ INVALIDE → Alerte humain :")
    print("      - Diagnostic attribution de cause")
    print("      - Proposition d'action (jamais automatique)")
    print("      - Logging + métriques")

    print("\n⚠️  Cas d'invalidité typiques :")
    print("   - Données corrompues (durée négative, ID manquant)")
    print("   - Bug dans le solveur généré (rare si cascade OK)")
    print("   - Contraintes insatisfiables (instance infeasible)")

    # ========================================================================
    # ÉTAPE 6 : Output (canaux opérationnel et audit)
    # ========================================================================

    afficher_etape(6, "Output (2 canaux)")

    print("📋 CANAL OPÉRATIONNEL : /planning/{instance_id}")
    print("   Format : JSON Planning")
    print("   Contenu :")
    print("     - Liste OperationPlanifiee (tache, ressource, debut, fin)")
    print("     - Makespan total")
    print("     - Métadonnées (timestamp, solveur_id)\n")

    exemple_planning = {
        "operations": [
            {"tache": "T1", "ressource": "R1", "debut": 0, "fin": 60},
            {"tache": "T2", "ressource": "R2", "debut": 60, "fin": 150},
            {"tache": "T3", "ressource": "R1", "debut": 60, "fin": 150},
        ],
        "makespan": 150,
        "metadata": {"solver_id": "abc123...", "timestamp": "2026-07-20T14:30:00Z"},
    }

    print("   Exemple :")
    print("   " + json.dumps(exemple_planning, indent=6))

    print("\n\n🔍 CANAL AUDIT : /audit/solver/{client_id}")
    print("   Format : Texte (code Python)")
    print("   Accès : Sur demande explicite seulement")
    print("   Usage : Inspection humaine, debugging, compliance")

    print("\n⚠️  Sécurité :")
    print("   - Code source jamais mélangé avec output opérationnel")
    print("   - Audit logging de toute consultation de code")
    print("   - Rotation des solveurs en cas de détection d'anomalie")

    # ========================================================================
    # CONCLUSION
    # ========================================================================

    print("\n\n" + "=" * 70)
    print("  RÉSUMÉ DU FLOW")
    print("=" * 70 + "\n")

    print("📌 PREMIÈRE EXÉCUTION (nouveau client ou nouvelle signature) :")
    print("   Ingestion → Génération (30-60s) → Stockage → Exécution (2s) → Planning")
    print("   Coût : ~$0.10 (une fois)")

    print("\n📌 EXÉCUTIONS SUIVANTES (même signature, données différentes) :")
    print("   Ingestion → Lookup (0.1s) → Exécution (2s) → Planning")
    print("   Coût : $0 (pas d'appel LLM)")

    print("\n💡 INNOVATION PRISME :")
    print("   Le solveur est généré UNE FOIS, puis ré-exécuté des milliers de fois")
    print("   → Performance : pas de latence LLM à chaque exécution")
    print("   → Coût : amorti sur toutes les exécutions futures")
    print("   → Sécurité : code validé et gelé, pas de régression")

    print("\n🚀 PROCHAINES ÉTAPES SUGGÉRÉES :")
    print("   1. Lancer scripts/demo_bout_en_bout.py (flow réel)")
    print("   2. Démarrer l'API : uvicorn api.app:app --reload")
    print("   3. Tester via curl ou Postman")
    print("   4. Explorer le dashboard : cd dashboard && npm run dev")

    print("\n📚 Documentation complète : docs/flow_complet_prisme.md")
    print()


if __name__ == "__main__":
    demo_flow()
