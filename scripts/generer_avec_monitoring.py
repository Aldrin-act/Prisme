"""Génération avec monitoring détaillé en temps réel des 9 agents."""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Ajouter le projet au PYTHONPATH
projet_root = Path(__file__).parent.parent
sys.path.insert(0, str(projet_root))

# Charger .env
try:
    from dotenv import load_dotenv
    load_dotenv(projet_root / ".env")
except ImportError:
    pass

# Imports
try:
    from generation.agents import (
        orchestrateur,
        analyste,
        architecte,
        debugger,
        optimiseur,
        reviewer,
        testeur,
    )
    from generation.agents.client_llm import construire_appel_llm, AppelLLM
    from generation.agents.generateur import generer_code_depuis_plan
    from generation.executer import ErreurExecutionGeneree, executer_code_genere
    from generation.validation_statique import valider_code_genere
    from validation_engine.cascade import evaluer_cascade
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    sys.exit(1)


class MoniteurAgents:
    """Moniteur en temps réel de l'exécution des agents."""

    def __init__(self):
        self.debut_total = None
        self.debut_agent = None
        self.etape_actuelle = 0
        self.total_etapes = 9

    def demarrer(self):
        """Démarre le monitoring."""
        self.debut_total = time.time()
        print("\n" + "🔍" * 35)
        print("  MONITORING DU PIPELINE MULTI-AGENTS")
        print("🔍" * 35 + "\n")

    def demarrer_agent(self, numero: int, nom: str, description: str):
        """Début d'exécution d'un agent."""
        self.etape_actuelle = numero
        self.debut_agent = time.time()

        barre = self._barre_progression(numero, self.total_etapes)

        print(f"\n{'='*70}")
        print(f"{barre}")
        print(f"🤖 AGENT {numero}/{self.total_etapes} : {nom.upper()}")
        print(f"{'='*70}")
        print(f"📋 Tâche : {description}")
        print(f"⏱️  Début : {datetime.now().strftime('%H:%M:%S')}")
        print()

    def terminer_agent(self, nom: str, resultat_court: str, details: str = None):
        """Fin d'exécution d'un agent."""
        duree = time.time() - self.debut_agent

        print(f"\n✅ {nom} terminé en {duree:.1f}s")
        print(f"📊 Résultat : {resultat_court}")

        if details:
            lignes = details.split('\n')[:3]
            for ligne in lignes:
                if ligne.strip():
                    print(f"   • {ligne.strip()}")
            if len(details.split('\n')) > 3:
                print(f"   ... (+{len(details.split('\n')) - 3} lignes)")

        print(f"{'─'*70}")

    def afficher_progression_totale(self):
        """Affiche la progression totale."""
        duree_totale = time.time() - self.debut_total
        pourcent = (self.etape_actuelle / self.total_etapes) * 100

        print(f"\n{'='*70}")
        print(f"📊 PROGRESSION : {pourcent:.0f}% ({self.etape_actuelle}/{self.total_etapes} agents)")
        print(f"⏱️  Temps écoulé : {duree_totale:.1f}s")

        # Estimation temps restant
        if self.etape_actuelle > 0:
            temps_par_agent = duree_totale / self.etape_actuelle
            restant = temps_par_agent * (self.total_etapes - self.etape_actuelle)
            print(f"⏳ Temps estimé restant : {restant:.0f}s")

        print(f"{'='*70}\n")

    def _barre_progression(self, actuel: int, total: int, largeur: int = 40) -> str:
        """Génère une barre de progression ASCII."""
        rempli = int(largeur * actuel / total)
        vide = largeur - rempli
        pourcent = (actuel / total) * 100

        barre = "█" * rempli + "░" * vide
        return f"[{barre}] {pourcent:.0f}% ({actuel}/{total})"

    def terminer(self, succes: bool):
        """Termine le monitoring."""
        duree_totale = time.time() - self.debut_total

        print(f"\n{'='*70}")
        if succes:
            print("✅ PIPELINE TERMINÉ AVEC SUCCÈS")
        else:
            print("❌ PIPELINE TERMINÉ AVEC ERREURS")
        print(f"⏱️  Durée totale : {duree_totale:.1f}s ({duree_totale/60:.1f} minutes)")
        print(f"{'='*70}\n")


def executer_pipeline_avec_monitoring(appel_llm: AppelLLM) -> dict:
    """Exécute le pipeline avec monitoring détaillé."""

    moniteur = MoniteurAgents()
    moniteur.demarrer()

    resultats = {}

    # 1. ORCHESTRATEUR
    moniteur.demarrer_agent(1, "Orchestrateur", "Planification des étapes du pipeline")
    try:
        plan = orchestrateur.planifier(appel_llm)
        resultats['plan'] = plan
        moniteur.terminer_agent(
            "Orchestrateur",
            f"{len(plan.plan)} étapes planifiées",
            "\n".join([f"{i+1}. {etape.agent}" for i, etape in enumerate(plan.plan[:3])])
        )
    except Exception as e:
        print(f"❌ Erreur : {e}")
        moniteur.terminer(False)
        return None

    moniteur.afficher_progression_totale()

    # 2. ANALYSTE
    moniteur.demarrer_agent(2, "Analyste", "Analyse de l'instance et spécification technique")
    try:
        analyse = analyste.analyser_mission(appel_llm)
        resultats['analyse'] = analyse
        spec_preview = analyse.en_texte()[:200]
        moniteur.terminer_agent(
            "Analyste",
            f"Spécification : {len(analyse.en_texte())} caractères",
            spec_preview
        )
    except Exception as e:
        print(f"❌ Erreur : {e}")
        moniteur.terminer(False)
        return None

    moniteur.afficher_progression_totale()

    # 3. ARCHITECTE
    moniteur.demarrer_agent(3, "Architecte", "Conception du modèle CP-SAT")
    try:
        conception = architecte.concevoir_modele(appel_llm, analyse)
        resultats['conception'] = conception
        plan_preview = conception.en_texte()[:200]
        moniteur.terminer_agent(
            "Architecte",
            f"Plan technique : {len(conception.en_texte())} caractères",
            plan_preview
        )
    except Exception as e:
        print(f"❌ Erreur : {e}")
        moniteur.terminer(False)
        return None

    moniteur.afficher_progression_totale()

    # 4. DÉVELOPPEUR
    moniteur.demarrer_agent(4, "Développeur", "Génération du code Python selon le plan")
    try:
        brut = generer_code_depuis_plan(appel_llm, conception.en_texte())
        resultats['code_initial'] = brut.code_source
        lignes_code = brut.code_source.split('\n')
        moniteur.terminer_agent(
            "Développeur",
            f"Code généré : {len(brut.code_source)} caractères, {len(lignes_code)} lignes",
            "\n".join(lignes_code[:3])
        )
    except Exception as e:
        print(f"❌ Erreur : {e}")
        moniteur.terminer(False)
        return None

    moniteur.afficher_progression_totale()

    # 5. TESTEUR
    moniteur.demarrer_agent(5, "Testeur", "Génération des tests unitaires")
    try:
        tests = testeur.generer_tests(appel_llm, brut.code_source)
        resultats['tests'] = tests
        moniteur.terminer_agent(
            "Testeur",
            f"Tests générés : {len(tests.code_tests)} caractères",
            f"Fichier de tests complet créé"
        )
    except Exception as e:
        print(f"❌ Erreur : {e}")
        moniteur.terminer(False)
        return None

    moniteur.afficher_progression_totale()

    # 6. REVIEWER
    moniteur.demarrer_agent(6, "Reviewer", "Revue de code et détection de bugs")
    try:
        revue = reviewer.relire_code(appel_llm, brut.code_source)
        resultats['revue'] = revue

        if revue.approuve:
            moniteur.terminer_agent(
                "Reviewer",
                "✅ CODE APPROUVÉ",
                "Aucun problème détecté"
            )
        else:
            moniteur.terminer_agent(
                "Reviewer",
                "❌ CODE REJETÉ",
                f"Problèmes détectés :\n{revue.commentaires[:200]}"
            )
    except Exception as e:
        print(f"❌ Erreur : {e}")
        moniteur.terminer(False)
        return None

    moniteur.afficher_progression_totale()

    # 7. DEBUGGER (conditionnel)
    code_candidat = brut.code_source
    if not revue.approuve:
        moniteur.demarrer_agent(7, "Debugger", "Correction des bugs détectés")
        try:
            correction = debugger.corriger_code(appel_llm, code_candidat, revue.commentaires)
            code_candidat = correction.code_source
            resultats['code_corrige'] = code_candidat
            moniteur.terminer_agent(
                "Debugger",
                "Code corrigé généré",
                f"{len(correction.code_source)} caractères"
            )
        except Exception as e:
            print(f"❌ Erreur : {e}")
            moniteur.terminer(False)
            return None
    else:
        print(f"\n{'='*70}")
        print(f"⏭️  AGENT 7 : DEBUGGER - SKIP")
        print(f"{'='*70}")
        print("Code déjà approuvé, pas de correction nécessaire")
        print(f"{'─'*70}")

    resultats['code_final'] = code_candidat
    moniteur.afficher_progression_totale()

    # 8. VALIDATION (pas un agent, mais important à monitorer)
    moniteur.demarrer_agent(8, "Validation", "Validation statique + Exécution + Cascade")

    # Validation statique
    print("   🔍 Validation statique...")
    validation = valider_code_genere(code_candidat)
    resultats['validation_statique'] = validation

    if not validation.valide:
        print(f"   ❌ Validation statique échouée")
        moniteur.terminer_agent("Validation", "ÉCHEC - Validation statique", str(validation.violations))
        moniteur.terminer(False)
        return resultats

    print(f"   ✅ Validation statique OK")

    # Exécution
    print("   ⚙️  Exécution du code...")
    try:
        solveur = executer_code_genere(code_candidat)
        print(f"   ✅ Exécution réussie")
    except ErreurExecutionGeneree as erreur:
        print(f"   ❌ Erreur d'exécution : {erreur}")
        resultats['erreur_execution'] = str(erreur)
        moniteur.terminer_agent("Validation", "ÉCHEC - Erreur d'exécution", str(erreur))
        moniteur.terminer(False)
        return resultats

    # Cascade
    print("   🔄 Cascade de validation...")
    try:
        verdict = evaluer_cascade(solveur)
        resultats['verdict_cascade'] = verdict
        print(f"   ✅ Cascade terminée")
        moniteur.terminer_agent(
            "Validation",
            f"SUCCÈS - Verdict : {verdict}",
            "Code validé et prêt"
        )
    except Exception as erreur:
        print(f"   ❌ Erreur cascade : {erreur}")
        resultats['erreur_cascade'] = str(erreur)
        moniteur.terminer_agent("Validation", "ÉCHEC - Cascade", str(erreur))
        moniteur.terminer(False)
        return resultats

    moniteur.afficher_progression_totale()

    # 9. OPTIMISEUR (si validation OK)
    if verdict and verdict.reussi:
        moniteur.demarrer_agent(9, "Optimiseur", "Optimisation du code validé")
        try:
            optimisation = optimiseur.optimiser_code(appel_llm, code_candidat, str(verdict))
            resultats['optimisation'] = optimisation
            moniteur.terminer_agent(
                "Optimiseur",
                "Optimisation proposée",
                "Code optimisé disponible"
            )
        except Exception as e:
            print(f"⚠️  Erreur optimiseur (non bloquant) : {e}")
    else:
        print(f"\n{'='*70}")
        print(f"⏭️  AGENT 9 : OPTIMISEUR - SKIP")
        print(f"{'='*70}")
        print("Validation échouée, pas d'optimisation")
        print(f"{'─'*70}")

    moniteur.terminer(True)
    return resultats


def main():
    """Point d'entrée avec monitoring."""

    print("\n" + "🤖" * 35)
    print("  GÉNÉRATION AVEC MONITORING DÉTAILLÉ")
    print("🤖" * 35 + "\n")

    provider = os.getenv('PRISME_LLM_PROVIDER', 'mistral')
    print(f"⚙️  Configuration :")
    print(f"   Provider : {provider}")
    print(f"   Mode : Pipeline Multi-Agents avec monitoring")
    print()

    # Client LLM
    try:
        appel_llm = construire_appel_llm()
    except Exception as e:
        print(f"❌ Erreur configuration : {e}")
        sys.exit(1)

    # Exécution avec monitoring
    resultats = executer_pipeline_avec_monitoring(appel_llm)

    if not resultats:
        print("\n❌ Pipeline échoué - Aucun résultat")
        sys.exit(1)

    # Sauvegarde des résultats
    print("\n📁 Sauvegarde des résultats...")

    if 'code_final' in resultats:
        chemin = projet_root / "solveur_genere.py"
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(resultats['code_final'])
        print(f"   ✅ Code : {chemin}")

    if 'tests' in resultats:
        chemin = projet_root / "test_solveur_genere.py"
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(resultats['tests'].code_tests)
        print(f"   ✅ Tests : {chemin}")

    # Résumé final
    print("\n" + "="*70)
    print("  RÉSUMÉ FINAL")
    print("="*70)

    print(f"\n📊 Agents exécutés :")
    agents_executes = []
    if 'plan' in resultats: agents_executes.append("✅ Orchestrateur")
    if 'analyse' in resultats: agents_executes.append("✅ Analyste")
    if 'conception' in resultats: agents_executes.append("✅ Architecte")
    if 'code_initial' in resultats: agents_executes.append("✅ Développeur")
    if 'tests' in resultats: agents_executes.append("✅ Testeur")
    if 'revue' in resultats: agents_executes.append("✅ Reviewer")
    if 'code_corrige' in resultats: agents_executes.append("✅ Debugger")
    if 'verdict_cascade' in resultats: agents_executes.append("✅ Validation")
    if 'optimisation' in resultats: agents_executes.append("✅ Optimiseur")

    for agent in agents_executes:
        print(f"   {agent}")

    print(f"\n🎯 Résultat global :")
    if 'verdict_cascade' in resultats and resultats['verdict_cascade']:
        if resultats['verdict_cascade'].reussi:
            print("   ✅ SUCCÈS COMPLET")
        else:
            print("   ⚠️  SUCCÈS PARTIEL")
    else:
        print("   ❌ ÉCHEC")

    print()


if __name__ == "__main__":
    main()
