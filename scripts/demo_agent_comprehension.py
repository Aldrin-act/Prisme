"""Démonstration de l'agent de compréhension avec données simulées.

Ce script montre comment l'agent de compréhension traduit différents formats
de données brutes vers le DSL T-R-C-O canonique.

Usage:
    python -m scripts.demo_agent_comprehension
"""

from __future__ import annotations

import json
from typing import Any

from adapters.agent_comprehension import ResultatComprehension, comprendre_donnees_erp
from dsl.schema import InstanceTRCO


# ============================================================================
# Simulation du LLM (remplace l'appel API réel)
# ============================================================================

def llm_simule(prompt_systeme: str, prompt_utilisateur: str) -> str:
    """Simule les réponses du LLM selon les données en entrée.

    En production, c'est ici qu'on appellerait vraiment l'API Anthropic/OpenAI.
    Pour la démo, on retourne des réponses pré-calculées.
    """
    # Détecter quel exemple est demandé
    if "CSV" in prompt_utilisateur or "Task,Machine,Duration" in prompt_utilisateur:
        return _reponse_exemple_csv()
    elif "work_orders" in prompt_utilisateur:
        return _reponse_exemple_json_erp()
    elif "3 tâches" in prompt_utilisateur or "Découpe du métal" in prompt_utilisateur:
        return _reponse_exemple_texte_libre()
    elif "URGENT" in prompt_utilisateur:
        return _reponse_exemple_avec_problemes()
    else:
        return _reponse_exemple_simple()


def _reponse_exemple_csv() -> str:
    """Réponse du LLM pour un CSV simple."""
    return json.dumps({
        "instance": {
            "taches": [
                {"id": "Cut_Metal", "nom": "Découpe métal"},
                {"id": "Weld_Parts", "nom": "Soudure pièces"},
                {"id": "Paint_Surface", "nom": "Peinture surface"}
            ],
            "ressources": [
                {"id": "Laser_Cutter", "nom": "Découpeuse laser"},
                {"id": "Welder_Station", "nom": "Poste de soudure"},
                {"id": "Paint_Booth", "nom": "Cabine de peinture"}
            ],
            "contraintes": [
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "Cut_Metal",
                    "ressource": "Laser_Cutter",
                    "duree": 150
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "Weld_Parts",
                    "ressource": "Welder_Station",
                    "duree": 90
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "Paint_Surface",
                    "ressource": "Paint_Booth",
                    "duree": 180
                }
            ],
            "objectifs": [
                {"type": "minimiser_makespan"}
            ]
        },
        "avertissements": [
            "Durées converties de heures en minutes (2.5h → 150min, etc.)",
            "Aucune précédence détectée dans les données CSV",
            "Une seule ressource compatible par tâche (pas de flexibilité FJSP)"
        ]
    })


def _reponse_exemple_json_erp() -> str:
    """Réponse du LLM pour un JSON ERP complexe avec compétences."""
    return json.dumps({
        "instance": {
            "taches": [
                {"id": "WO_1001", "nom": "Assembly", "priorite": 2},
                {"id": "WO_1002", "nom": "Quality_Check", "priorite": 1}
            ],
            "ressources": [
                {
                    "id": "WS_A",
                    "nom": "Assembly Station",
                    "competences": ["mechanical", "electrical"]
                },
                {
                    "id": "WS_Q",
                    "nom": "QC Station",
                    "competences": ["quality"]
                }
            ],
            "contraintes": [
                {
                    "type": "precedence",
                    "avant": "WO_1001",
                    "apres": "WO_1002"
                },
                {
                    "type": "competence_requise",
                    "tache": "WO_1001",
                    "competence": "mechanical"
                },
                {
                    "type": "competence_requise",
                    "tache": "WO_1002",
                    "competence": "quality"
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "WO_1001",
                    "ressource": "WS_A",
                    "duree": 45
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "WO_1002",
                    "ressource": "WS_Q",
                    "duree": 15
                }
            ],
            "objectifs": [
                {"type": "minimiser_makespan"}
            ]
        },
        "avertissements": [
            "Précédence détectée via 'must_finish_before_wo'",
            "Compatibilités déduites des compétences déclarées",
            "Priorités extraites des work orders"
        ]
    })


def _reponse_exemple_texte_libre() -> str:
    """Réponse du LLM pour du texte libre en langage naturel."""
    return json.dumps({
        "instance": {
            "taches": [
                {"id": "T_Decoupe", "nom": "Découpe du métal"},
                {"id": "T_Soudure", "nom": "Soudure"},
                {"id": "T_Peinture", "nom": "Peinture"}
            ],
            "ressources": [
                {"id": "R_Laser", "nom": "Machine laser"},
                {"id": "R_Soudure", "nom": "Poste de soudure"},
                {"id": "R_Peinture", "nom": "Stand de peinture"}
            ],
            "contraintes": [
                {
                    "type": "precedence",
                    "avant": "T_Decoupe",
                    "apres": "T_Soudure"
                },
                {
                    "type": "precedence",
                    "avant": "T_Soudure",
                    "apres": "T_Peinture"
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "T_Decoupe",
                    "ressource": "R_Laser",
                    "duree": 120
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "T_Soudure",
                    "ressource": "R_Soudure",
                    "duree": 90
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "T_Peinture",
                    "ressource": "R_Peinture",
                    "duree": 180
                }
            ],
            "objectifs": [
                {"type": "minimiser_makespan"}
            ]
        },
        "avertissements": [
            "Durée de découpe marquée 'environ' - peut être imprécise",
            "IDs générés automatiquement (T_*, R_*) depuis le texte",
            "Chaîne de précédences détectée : Découpe → Soudure → Peinture",
            "Une seule ressource compatible par tâche déduite du contexte"
        ]
    })


def _reponse_exemple_simple() -> str:
    """Réponse du LLM pour un exemple simple."""
    return json.dumps({
        "instance": {
            "taches": [
                {"id": "T1", "nom": "Tâche 1"}
            ],
            "ressources": [
                {"id": "R1", "nom": "Ressource 1"}
            ],
            "contraintes": [
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "T1",
                    "ressource": "R1",
                    "duree": 60
                }
            ],
            "objectifs": [
                {"type": "minimiser_makespan"}
            ]
        },
        "avertissements": []
    })


def _reponse_exemple_avec_problemes() -> str:
    """Exemple avec des avertissements importants."""
    return json.dumps({
        "instance": {
            "taches": [
                {"id": "URGENT_001", "nom": "Réparation urgente"},
                {"id": "MAINT_002", "nom": "Maintenance"}
            ],
            "ressources": [
                {"id": "TECH_A", "nom": "Technicien A"},
                {"id": "TECH_B", "nom": "Technicien B"}
            ],
            "contraintes": [
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "URGENT_001",
                    "ressource": "TECH_A",
                    "duree": 30
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "MAINT_002",
                    "ressource": "TECH_A",
                    "duree": 45
                },
                {
                    "type": "compatibilite_ressource_tache",
                    "tache": "MAINT_002",
                    "ressource": "TECH_B",
                    "duree": 60
                }
            ],
            "objectifs": [
                {"type": "minimiser_makespan"}
            ]
        },
        "avertissements": [
            "⚠️ URGENT_001 sans durée spécifiée - durée estimée à 30 min par défaut",
            "⚠️ URGENT_001 compatible uniquement avec TECH_A - pas de flexibilité",
            "MAINT_002 flexible (2 ressources compatibles) mais durées différentes déduites",
            "Aucune précédence détectée - tâches peuvent s'exécuter en parallèle"
        ]
    })


# ============================================================================
# Exemples de données brutes
# ============================================================================

EXEMPLE_1_CSV = """Task,Machine,Duration_Hours
Cut_Metal,Laser_Cutter,2.5
Weld_Parts,Welder_Station,1.5
Paint_Surface,Paint_Booth,3.0"""

EXEMPLE_2_JSON_ERP = """{
  "work_orders": [
    {
      "wo_id": 1001,
      "operation": "Assembly",
      "estimated_time_min": 45,
      "requires_skill": "mechanical",
      "priority": 2,
      "must_finish_before_wo": 1002
    },
    {
      "wo_id": 1002,
      "operation": "Quality_Check",
      "estimated_time_min": 15,
      "requires_skill": "quality",
      "priority": 1
    }
  ],
  "workstations": [
    {
      "station_id": "WS_A",
      "station_name": "Assembly Station",
      "available_skills": ["mechanical", "electrical"]
    },
    {
      "station_id": "WS_Q",
      "station_name": "QC Station",
      "available_skills": ["quality"]
    }
  ]
}"""

EXEMPLE_3_TEXTE_LIBRE = """Nous avons 3 tâches à faire aujourd'hui :
- Découpe du métal (environ 2 heures) sur la machine laser
- Soudure (1h30) nécessite le poste de soudure
- Peinture (3h) doit être faite APRÈS la soudure, au stand de peinture

La découpe doit être terminée avant la soudure."""

EXEMPLE_4_AVEC_PROBLEMES = """URGENT: Réparation à faire sur TECH_A
Aussi prévoir maintenance (pas sûr de la durée, peut-être 45min?).
TECH_B peut faire la maintenance aussi."""


# ============================================================================
# Fonctions de démonstration
# ============================================================================

def afficher_separateur(titre: str) -> None:
    """Affiche un séparateur visuel."""
    print("\n" + "=" * 70)
    print(f"  {titre}")
    print("=" * 70 + "\n")


def demo_exemple(
    numero: int,
    titre: str,
    donnees_brutes: str,
    description: str
) -> None:
    """Exécute une démonstration complète pour un exemple."""
    afficher_separateur(f"EXEMPLE {numero}: {titre}")

    print(f"📋 {description}\n")

    # Étape 1: Afficher les données brutes
    print("📥 DONNÉES BRUTES (Input)")
    print("-" * 70)
    print(donnees_brutes)
    print()

    # Étape 2: Appeler l'agent (avec LLM simulé)
    print("🧠 TRAITEMENT PAR L'AGENT DE COMPRÉHENSION...")
    print("-" * 70)
    try:
        resultat = comprendre_donnees_erp(llm_simule, donnees_brutes)
        print("✅ Agent a généré une réponse JSON")
        print()

        # Étape 3: Afficher le JSON généré
        print("📄 JSON T-R-C-O GÉNÉRÉ (Output de l'agent)")
        print("-" * 70)
        print(json.dumps(resultat.instance_brute, indent=2, ensure_ascii=False))
        print()

        # Étape 4: Afficher les avertissements
        if resultat.avertissements:
            print("⚠️  AVERTISSEMENTS")
            print("-" * 70)
            for i, avert in enumerate(resultat.avertissements, 1):
                print(f"  {i}. {avert}")
            print()
        else:
            print("✅ Aucun avertissement\n")

        # Étape 5: Validation stricte
        print("🔒 VALIDATION STRICTE (Garde-fou §6.7)")
        print("-" * 70)
        try:
            instance_validee = InstanceTRCO.model_validate(resultat.instance_brute)
            print("✅ SUCCÈS - Instance T-R-C-O valide !")
            print(f"   - {len(instance_validee.taches)} tâche(s)")
            print(f"   - {len(instance_validee.ressources)} ressource(s)")
            print(f"   - {len(instance_validee.contraintes)} contrainte(s)")
            print(f"   - {len(instance_validee.objectifs)} objectif(s)")
            print()

            # Résumé
            print("📊 RÉSULTAT FINAL")
            print("-" * 70)
            print("✅ Instance prête pour l'ingestion")
            print("✅ Peut être envoyée au générateur de solveur")
            if resultat.avertissements:
                print(f"⚠️  {len(resultat.avertissements)} avertissement(s) à vérifier par un humain")
            print()

        except Exception as e:
            print(f"❌ ÉCHEC - Validation rejetée")
            print(f"   Erreur: {str(e)}")
            print("\n   → L'instance sera REJETÉE, ne passera pas à l'ingestion")
            print()

    except Exception as e:
        print(f"❌ ERREUR lors du traitement")
        print(f"   {str(e)}")
        print()


def demo_complete() -> None:
    """Lance la démonstration complète avec tous les exemples."""
    print("\n" + "=" * 70)
    print("  DÉMONSTRATION : AGENT DE COMPRÉHENSION")
    print("  Traduction automatique ERP → DSL T-R-C-O via LLM")
    print("=" * 70)

    print("\n📖 Cette démo montre comment l'agent traduit différents formats")
    print("   de données brutes vers le format canonique PRISME.\n")

    input("Appuyez sur Entrée pour commencer...")

    # Exemple 1: CSV simple
    demo_exemple(
        1,
        "CSV Simple",
        EXEMPLE_1_CSV,
        "Format CSV basique avec tâches, ressources et durées en heures"
    )
    input("Appuyez sur Entrée pour l'exemple suivant...")

    # Exemple 2: JSON ERP complexe
    demo_exemple(
        2,
        "JSON ERP Complexe",
        EXEMPLE_2_JSON_ERP,
        "Format ERP avec work orders, compétences et précédences"
    )
    input("Appuyez sur Entrée pour l'exemple suivant...")

    # Exemple 3: Texte libre
    demo_exemple(
        3,
        "Texte Libre (Langage Naturel)",
        EXEMPLE_3_TEXTE_LIBRE,
        "Description en français naturel avec précédences implicites"
    )
    input("Appuyez sur Entrée pour l'exemple suivant...")

    # Exemple 4: Avec problèmes
    demo_exemple(
        4,
        "Données Incomplètes",
        EXEMPLE_4_AVEC_PROBLEMES,
        "Données avec informations manquantes → avertissements importants"
    )

    # Conclusion
    afficher_separateur("CONCLUSION")
    print("📊 L'agent de compréhension peut traiter :")
    print("   ✅ CSV, JSON, texte libre")
    print("   ✅ Formats ERP propriétaires variés")
    print("   ✅ Données incomplètes (avec avertissements)")
    print()
    print("🔒 Sécurité garantie par :")
    print("   ✅ Validation stricte Pydantic (InstanceTRCO)")
    print("   ✅ Règle 'ne jamais inventer' dans le prompt")
    print("   ✅ Avertissements pour toute incertitude")
    print()
    print("💰 Coût estimé : ~$0.01-0.10 par traduction (selon taille)")
    print("⏱️  Temps : 2-5 secondes avec un LLM réel")
    print()
    print("🎯 Idéal pour : prototypage, clients ponctuels, formats changeants")
    print("❌ À éviter pour : haute fréquence, production critique")
    print()


# ============================================================================
# Point d'entrée
# ============================================================================

if __name__ == "__main__":
    demo_complete()
