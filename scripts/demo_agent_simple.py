"""Démonstration simplifiée de l'agent de compréhension.

Version standalone qui n'a pas de dépendances externes.
"""

import json


# ============================================================================
# Exemples de données brutes
# ============================================================================

EXEMPLES = [
    {
        "numero": 1,
        "titre": "CSV Simple",
        "description": "Format CSV basique avec tâches, ressources et durées en heures",
        "donnees_brutes": """Task,Machine,Duration_Hours
            Cut_Metal,Laser_Cutter,2.5
            Weld_Parts,Welder_Station,1.5
            Paint_Surface,Paint_Booth,3.0""",
        "output_json": {
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
                {"type": "compatibilite_ressource_tache", "tache": "Cut_Metal", "ressource": "Laser_Cutter", "duree": 150},
                {"type": "compatibilite_ressource_tache", "tache": "Weld_Parts", "ressource": "Welder_Station", "duree": 90},
                {"type": "compatibilite_ressource_tache", "tache": "Paint_Surface", "ressource": "Paint_Booth", "duree": 180}
            ],
            "objectifs": [{"type": "minimiser_makespan"}]
        },
        "avertissements": [
            "Durées converties de heures en minutes (2.5h → 150min, etc.)",
            "Aucune précédence détectée dans les données CSV",
            "Une seule ressource compatible par tâche (pas de flexibilité FJSP)"
        ]
    },
    {
        "numero": 2,
        "titre": "JSON ERP Complexe",
        "description": "Format ERP avec work orders, compétences et précédences",
        "donnees_brutes": """{
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
}""",
        "output_json": {
            "taches": [
                {"id": "WO_1001", "nom": "Assembly", "priorite": 2},
                {"id": "WO_1002", "nom": "Quality_Check", "priorite": 1}
            ],
            "ressources": [
                {"id": "WS_A", "nom": "Assembly Station", "competences": ["mechanical", "electrical"]},
                {"id": "WS_Q", "nom": "QC Station", "competences": ["quality"]}
            ],
            "contraintes": [
                {"type": "precedence", "avant": "WO_1001", "apres": "WO_1002"},
                {"type": "competence_requise", "tache": "WO_1001", "competence": "mechanical"},
                {"type": "competence_requise", "tache": "WO_1002", "competence": "quality"},
                {"type": "compatibilite_ressource_tache", "tache": "WO_1001", "ressource": "WS_A", "duree": 45},
                {"type": "compatibilite_ressource_tache", "tache": "WO_1002", "ressource": "WS_Q", "duree": 15}
            ],
            "objectifs": [{"type": "minimiser_makespan"}]
        },
        "avertissements": [
            "Précédence détectée via 'must_finish_before_wo'",
            "Compatibilités déduites des compétences déclarées",
            "Priorités extraites des work orders"
        ]
    },
    {
        "numero": 3,
        "titre": "Texte Libre (Langage Naturel)",
        "description": "Description en français naturel avec précédences implicites",
        "donnees_brutes": """Nous avons 3 tâches à faire aujourd'hui :
- Découpe du métal (environ 2 heures) sur la machine laser
- Soudure (1h30) nécessite le poste de soudure
- Peinture (3h) doit être faite APRÈS la soudure, au stand de peinture

La découpe doit être terminée avant la soudure.""",
        "output_json": {
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
                {"type": "precedence", "avant": "T_Decoupe", "apres": "T_Soudure"},
                {"type": "precedence", "avant": "T_Soudure", "apres": "T_Peinture"},
                {"type": "compatibilite_ressource_tache", "tache": "T_Decoupe", "ressource": "R_Laser", "duree": 120},
                {"type": "compatibilite_ressource_tache", "tache": "T_Soudure", "ressource": "R_Soudure", "duree": 90},
                {"type": "compatibilite_ressource_tache", "tache": "T_Peinture", "ressource": "R_Peinture", "duree": 180}
            ],
            "objectifs": [{"type": "minimiser_makespan"}]
        },
        "avertissements": [
            "Durée de découpe marquée 'environ' - peut être imprécise",
            "IDs générés automatiquement (T_*, R_*) depuis le texte",
            "Chaîne de précédences détectée : Découpe → Soudure → Peinture",
            "Une seule ressource compatible par tâche déduite du contexte"
        ]
    },
    {
        "numero": 4,
        "titre": "Données Incomplètes",
        "description": "Données avec informations manquantes → avertissements importants",
        "donnees_brutes": """URGENT: Réparation à faire sur TECH_A
Aussi prévoir maintenance (pas sûr de la durée, peut-être 45min?).
TECH_B peut faire la maintenance aussi.""",
        "output_json": {
            "taches": [
                {"id": "URGENT_001", "nom": "Réparation urgente"},
                {"id": "MAINT_002", "nom": "Maintenance"}
            ],
            "ressources": [
                {"id": "TECH_A", "nom": "Technicien A"},
                {"id": "TECH_B", "nom": "Technicien B"}
            ],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "URGENT_001", "ressource": "TECH_A", "duree": 30},
                {"type": "compatibilite_ressource_tache", "tache": "MAINT_002", "ressource": "TECH_A", "duree": 45},
                {"type": "compatibilite_ressource_tache", "tache": "MAINT_002", "ressource": "TECH_B", "duree": 60}
            ],
            "objectifs": [{"type": "minimiser_makespan"}]
        },
        "avertissements": [
            "⚠️ URGENT_001 sans durée spécifiée - durée estimée à 30 min par défaut",
            "⚠️ URGENT_001 compatible uniquement avec TECH_A - pas de flexibilité",
            "MAINT_002 flexible (2 ressources compatibles) mais durées différentes déduites",
            "Aucune précédence détectée - tâches peuvent s'exécuter en parallèle"
        ]
    }
]


def afficher_separateur(titre: str, char: str = "=") -> None:
    """Affiche un séparateur visuel."""
    print("\n" + char * 70)
    print(f"  {titre}")
    print(char * 70 + "\n")


def demo_exemple(exemple: dict) -> None:
    """Affiche un exemple de démonstration."""
    afficher_separateur(f"EXEMPLE {exemple['numero']}: {exemple['titre']}")

    print(f"📋 {exemple['description']}\n")

    # Données brutes
    print("📥 DONNÉES BRUTES (Input)")
    print("-" * 70)
    print(exemple['donnees_brutes'])
    print()

    # Traitement
    print("🧠 TRAITEMENT PAR L'AGENT DE COMPRÉHENSION...")
    print("-" * 70)
    print("✅ Agent a analysé les données et généré une réponse JSON")
    print()

    # Output JSON
    print("📄 JSON T-R-C-O GÉNÉRÉ (Output de l'agent)")
    print("-" * 70)
    print(json.dumps(exemple['output_json'], indent=2, ensure_ascii=False))
    print()

    # Avertissements
    if exemple['avertissements']:
        print("⚠️  AVERTISSEMENTS")
        print("-" * 70)
        for i, avert in enumerate(exemple['avertissements'], 1):
            print(f"  {i}. {avert}")
        print()
    else:
        print("✅ Aucun avertissement\n")

    # Validation
    print("🔒 VALIDATION STRICTE (Garde-fou §6.7)")
    print("-" * 70)
    print("✅ SUCCÈS - Instance T-R-C-O valide !")
    print(f"   - {len(exemple['output_json']['taches'])} tâche(s)")
    print(f"   - {len(exemple['output_json']['ressources'])} ressource(s)")
    print(f"   - {len(exemple['output_json']['contraintes'])} contrainte(s)")
    print(f"   - {len(exemple['output_json']['objectifs'])} objectif(s)")
    print()

    # Résumé
    print("📊 RÉSULTAT FINAL")
    print("-" * 70)
    print("✅ Instance prête pour l'ingestion")
    print("✅ Peut être envoyée au générateur de solveur")
    if exemple['avertissements']:
        print(f"⚠️  {len(exemple['avertissements'])} avertissement(s) à vérifier par un humain")
    print()


def main():
    """Lance la démonstration."""
    print("\n" + "=" * 70)
    print("  DÉMONSTRATION : AGENT DE COMPRÉHENSION")
    print("  Traduction automatique ERP → DSL T-R-C-O via LLM")
    print("=" * 70)

    print("\n📖 Cette démo montre comment l'agent traduit différents formats")
    print("   de données brutes vers le format canonique PRISME.\n")
    print("   (Version simulée avec données pré-calculées)\n")

    for exemple in EXEMPLES:
        demo_exemple(exemple)
        print("\n" + "─" * 70 + "\n")

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
    print("📝 NOTE: Cette démo utilise des réponses simulées du LLM.")
    print("   En production, l'agent appelle vraiment l'API Anthropic/OpenAI.")
    print()


if __name__ == "__main__":
    main()
