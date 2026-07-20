"""Génération avec métriques complètes et export pour visualisation.

Métriques trackées :
- Durée par agent
- Coût estimé par agent (tokens × prix)
- Taille des outputs (caractères, lignes)
- Tokens utilisés (input/output) - estimation
- Statut (succès/échec/skip)
- Erreurs détectées

Export :
- JSON temps réel pour dashboard web
- Format compatible Grafana/Prometheus
"""

from __future__ import annotations

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

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


# Coûts estimés par provider ($/1M tokens)
COUTS_PROVIDERS = {
    'mistral': {'input': 3.00, 'output': 15.00},     # Mistral Large
    'anthropic': {'input': 3.00, 'output': 15.00},   # Claude Sonnet 4.5
    'openai': {'input': 30.00, 'output': 60.00},     # GPT-4
}


@dataclass
class MetriqueAgent:
    """Métriques pour un agent."""
    nom: str
    numero: int
    statut: str  # "success", "error", "skip"
    debut: float
    fin: float
    duree_secondes: float

    # Tokens (estimation)
    tokens_input: int
    tokens_output: int
    tokens_total: int

    # Coût (estimation)
    cout_usd: float

    # Output
    taille_output_chars: int
    taille_output_lignes: int

    # Erreur (si applicable)
    erreur: Optional[str] = None


@dataclass
class MetriquesPipeline:
    """Métriques globales du pipeline."""
    run_id: str
    timestamp: str
    provider: str

    # Durée
    debut: float
    fin: Optional[float]
    duree_totale_secondes: Optional[float]

    # Agents
    agents: list[MetriqueAgent]
    nb_agents_executes: int
    nb_agents_reussis: int
    nb_agents_echec: int
    nb_agents_skip: int

    # Tokens totaux
    tokens_input_total: int
    tokens_output_total: int
    tokens_total: int

    # Coût total
    cout_total_usd: float

    # Résultat final
    succes: bool
    erreur_finale: Optional[str]


class CollecteurMetriques:
    """Collecte et exporte les métriques."""

    def __init__(self, provider: str):
        self.provider = provider
        self.couts = COUTS_PROVIDERS.get(provider, COUTS_PROVIDERS['mistral'])

        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debut = time.time()
        self.agents: list[MetriqueAgent] = []

        self.chemin_metriques = projet_root / "metriques" / f"run_{self.run_id}.json"
        self.chemin_temps_reel = projet_root / "metriques" / "temps_reel.json"

        # Créer dossier métriques
        self.chemin_metriques.parent.mkdir(exist_ok=True)

    def estimer_tokens(self, texte: str) -> int:
        """Estime le nombre de tokens (1 token ≈ 4 caractères)."""
        return len(texte) // 4

    def calculer_cout(self, tokens_input: int, tokens_output: int) -> float:
        """Calcule le coût en USD."""
        cout_input = (tokens_input / 1_000_000) * self.couts['input']
        cout_output = (tokens_output / 1_000_000) * self.couts['output']
        return cout_input + cout_output

    def demarrer_agent(self, numero: int, nom: str, input_texte: str = "") -> dict:
        """Démarre le tracking d'un agent."""
        tokens_input = self.estimer_tokens(input_texte)

        return {
            'nom': nom,
            'numero': numero,
            'debut': time.time(),
            'tokens_input': tokens_input,
        }

    def terminer_agent(
        self,
        contexte: dict,
        statut: str,
        output_texte: str = "",
        erreur: Optional[str] = None
    ):
        """Termine le tracking d'un agent."""
        fin = time.time()
        tokens_output = self.estimer_tokens(output_texte)
        tokens_total = contexte['tokens_input'] + tokens_output
        cout = self.calculer_cout(contexte['tokens_input'], tokens_output)

        metrique = MetriqueAgent(
            nom=contexte['nom'],
            numero=contexte['numero'],
            statut=statut,
            debut=contexte['debut'],
            fin=fin,
            duree_secondes=fin - contexte['debut'],
            tokens_input=contexte['tokens_input'],
            tokens_output=tokens_output,
            tokens_total=tokens_total,
            cout_usd=cout,
            taille_output_chars=len(output_texte),
            taille_output_lignes=len(output_texte.split('\n')),
            erreur=erreur,
        )

        self.agents.append(metrique)
        self._exporter_temps_reel()

        return metrique

    def finaliser(self, succes: bool, erreur_finale: Optional[str] = None) -> MetriquesPipeline:
        """Finalise et exporte les métriques."""
        fin = time.time()

        # Calculs globaux
        nb_reussis = sum(1 for a in self.agents if a.statut == "success")
        nb_echec = sum(1 for a in self.agents if a.statut == "error")
        nb_skip = sum(1 for a in self.agents if a.statut == "skip")

        tokens_input_total = sum(a.tokens_input for a in self.agents)
        tokens_output_total = sum(a.tokens_output for a in self.agents)
        cout_total = sum(a.cout_usd for a in self.agents)

        pipeline = MetriquesPipeline(
            run_id=self.run_id,
            timestamp=datetime.now().isoformat(),
            provider=self.provider,
            debut=self.debut,
            fin=fin,
            duree_totale_secondes=fin - self.debut,
            agents=self.agents,
            nb_agents_executes=len(self.agents),
            nb_agents_reussis=nb_reussis,
            nb_agents_echec=nb_echec,
            nb_agents_skip=nb_skip,
            tokens_input_total=tokens_input_total,
            tokens_output_total=tokens_output_total,
            tokens_total=tokens_input_total + tokens_output_total,
            cout_total_usd=cout_total,
            succes=succes,
            erreur_finale=erreur_finale,
        )

        self._exporter_final(pipeline)
        self._exporter_grafana(pipeline)

        return pipeline

    def _exporter_temps_reel(self):
        """Exporte l'état actuel pour dashboard temps réel."""
        donnees = {
            'run_id': self.run_id,
            'timestamp': datetime.now().isoformat(),
            'en_cours': True,
            'agents': [asdict(a) for a in self.agents],
            'progression': {
                'actuel': len(self.agents),
                'total': 9,
                'pourcentage': (len(self.agents) / 9) * 100,
            },
            'cout_actuel_usd': sum(a.cout_usd for a in self.agents),
            'tokens_actuels': sum(a.tokens_total for a in self.agents),
        }

        with open(self.chemin_temps_reel, 'w', encoding='utf-8') as f:
            json.dump(donnees, f, indent=2)

    def _exporter_final(self, pipeline: MetriquesPipeline):
        """Exporte les métriques finales."""
        with open(self.chemin_metriques, 'w', encoding='utf-8') as f:
            json.dump(asdict(pipeline), f, indent=2)

    def _exporter_grafana(self, pipeline: MetriquesPipeline):
        """Exporte au format Prometheus/Grafana."""
        chemin = projet_root / "metriques" / "grafana_metrics.prom"

        lines = [
            "# Métriques PRISME - Format Prometheus",
            f"# Run ID: {pipeline.run_id}",
            f"# Timestamp: {pipeline.timestamp}",
            "",
            f"prisme_pipeline_duration_seconds {pipeline.duree_totale_secondes}",
            f"prisme_pipeline_cost_usd {pipeline.cout_total_usd}",
            f"prisme_pipeline_tokens_total {pipeline.tokens_total}",
            f"prisme_pipeline_success {1 if pipeline.succes else 0}",
            f"prisme_agents_executed {pipeline.nb_agents_executes}",
            f"prisme_agents_success {pipeline.nb_agents_reussis}",
            f"prisme_agents_failed {pipeline.nb_agents_echec}",
            "",
        ]

        # Métriques par agent
        for agent in pipeline.agents:
            lines.append(f'prisme_agent_duration_seconds{{agent="{agent.nom}"}} {agent.duree_secondes}')
            lines.append(f'prisme_agent_cost_usd{{agent="{agent.nom}"}} {agent.cout_usd}')
            lines.append(f'prisme_agent_tokens{{agent="{agent.nom}"}} {agent.tokens_total}')

        with open(chemin, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def executer_avec_metriques(appel_llm: AppelLLM, provider: str) -> MetriquesPipeline:
    """Exécute le pipeline avec collecte de métriques."""

    collecteur = CollecteurMetriques(provider)

    print("\n" + "📊" * 35)
    print("  GÉNÉRATION AVEC MÉTRIQUES COMPLÈTES")
    print("📊" * 35 + "\n")

    try:
        # 1. Orchestrateur
        print("🤖 [1/9] Orchestrateur...")
        ctx = collecteur.demarrer_agent(1, "Orchestrateur")
        plan = orchestrateur.planifier(appel_llm)
        output = "\n".join([str(e) for e in plan.plan])
        m = collecteur.terminer_agent(ctx, "success", output)
        print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f} | {m.tokens_total:,} tokens")

        # 2. Analyste
        print("🤖 [2/9] Analyste...")
        ctx = collecteur.demarrer_agent(2, "Analyste")
        analyse = analyste.analyser_mission(appel_llm)
        m = collecteur.terminer_agent(ctx, "success", analyse.en_texte())
        print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f} | {m.tokens_total:,} tokens")

        # 3. Architecte
        print("🤖 [3/9] Architecte...")
        ctx = collecteur.demarrer_agent(3, "Architecte", analyse.en_texte())
        conception = architecte.concevoir_modele(appel_llm, analyse)
        m = collecteur.terminer_agent(ctx, "success", conception.en_texte())
        print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f} | {m.tokens_total:,} tokens")

        # 4. Développeur
        print("🤖 [4/9] Développeur...")
        ctx = collecteur.demarrer_agent(4, "Développeur", conception.en_texte())
        brut = generer_code_depuis_plan(appel_llm, conception.en_texte())
        m = collecteur.terminer_agent(ctx, "success", brut.code_source)
        print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f} | {m.tokens_total:,} tokens | {len(brut.code_source.split('\\n'))} lignes")

        # 5. Testeur
        print("🤖 [5/9] Testeur...")
        ctx = collecteur.demarrer_agent(5, "Testeur", brut.code_source)
        tests = testeur.generer_tests(appel_llm, brut.code_source)
        m = collecteur.terminer_agent(ctx, "success", tests.code_tests)
        print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f} | {m.tokens_total:,} tokens")

        # 6. Reviewer
        print("🤖 [6/9] Reviewer...")
        ctx = collecteur.demarrer_agent(6, "Reviewer", brut.code_source)
        revue = reviewer.relire_code(appel_llm, brut.code_source)
        m = collecteur.terminer_agent(ctx, "success", str(revue.commentaires))
        print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f} | Approuvé: {revue.approuve}")

        # 7. Debugger (conditionnel)
        code_final = brut.code_source
        if not revue.approuve:
            print("🤖 [7/9] Debugger...")
            ctx = collecteur.demarrer_agent(7, "Debugger", brut.code_source + revue.commentaires)
            correction = debugger.corriger_code(appel_llm, brut.code_source, revue.commentaires)
            code_final = correction.code_source
            m = collecteur.terminer_agent(ctx, "success", code_final)
            print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f}")
        else:
            print("🤖 [7/9] Debugger... ⏭️  SKIP")
            collecteur.terminer_agent(
                {'nom': 'Debugger', 'numero': 7, 'debut': time.time(), 'tokens_input': 0},
                "skip"
            )

        # 8. Validation
        print("🤖 [8/9] Validation...")
        ctx_start = time.time()
        validation = valider_code_genere(code_final)

        if not validation.valide:
            collecteur.terminer_agent(
                {'nom': 'Validation', 'numero': 8, 'debut': ctx_start, 'tokens_input': 0},
                "error",
                erreur="Validation statique échouée"
            )
            pipeline = collecteur.finaliser(False, "Validation statique échouée")
            return pipeline

        try:
            solveur = executer_code_genere(code_final)
            verdict = evaluer_cascade(solveur)

            collecteur.terminer_agent(
                {'nom': 'Validation', 'numero': 8, 'debut': ctx_start, 'tokens_input': 0},
                "success",
                str(verdict)
            )
            print(f"   ✅ Validation OK")

        except Exception as e:
            collecteur.terminer_agent(
                {'nom': 'Validation', 'numero': 8, 'debut': ctx_start, 'tokens_input': 0},
                "error",
                erreur=str(e)
            )
            pipeline = collecteur.finaliser(False, str(e))

            # Sauvegarder quand même le code
            with open(projet_root / "solveur_genere.py", "w") as f:
                f.write(code_final)
            with open(projet_root / "test_solveur_genere.py", "w") as f:
                f.write(tests.code_tests)

            return pipeline

        # 9. Optimiseur (si succès)
        if verdict and verdict.reussi:
            print("🤖 [9/9] Optimiseur...")
            ctx = collecteur.demarrer_agent(9, "Optimiseur", code_final)
            optimisation = optimiseur.optimiser_code(appel_llm, code_final, str(verdict))
            m = collecteur.terminer_agent(ctx, "success", "Optimisation proposée")
            print(f"   ✅ {m.duree_secondes:.1f}s | ${m.cout_usd:.4f}")
        else:
            print("🤖 [9/9] Optimiseur... ⏭️  SKIP")
            collecteur.terminer_agent(
                {'nom': 'Optimiseur', 'numero': 9, 'debut': time.time(), 'tokens_input': 0},
                "skip"
            )

        # Sauvegarder
        with open(projet_root / "solveur_genere.py", "w") as f:
            f.write(code_final)
        with open(projet_root / "test_solveur_genere.py", "w") as f:
            f.write(tests.code_tests)

        pipeline = collecteur.finaliser(True)
        return pipeline

    except Exception as e:
        pipeline = collecteur.finaliser(False, str(e))
        return pipeline


def afficher_resume(pipeline: MetriquesPipeline):
    """Affiche un résumé des métriques."""
    print("\n" + "="*70)
    print("  RÉSUMÉ DES MÉTRIQUES")
    print("="*70)

    print(f"\n⏱️  Durée totale : {pipeline.duree_totale_secondes:.1f}s ({pipeline.duree_totale_secondes/60:.1f} min)")
    print(f"💰 Coût total : ${pipeline.cout_total_usd:.4f}")
    print(f"🔢 Tokens total : {pipeline.tokens_total:,}")
    print(f"   - Input : {pipeline.tokens_input_total:,}")
    print(f"   - Output : {pipeline.tokens_output_total:,}")

    print(f"\n📊 Agents :")
    print(f"   ✅ Réussis : {pipeline.nb_agents_reussis}")
    print(f"   ❌ Échecs : {pipeline.nb_agents_echec}")
    print(f"   ⏭️  Skip : {pipeline.nb_agents_skip}")

    print(f"\n🎯 Résultat : {'✅ SUCCÈS' if pipeline.succes else '❌ ÉCHEC'}")

    print(f"\n📁 Fichiers générés :")
    print(f"   • Métriques complètes : {projet_root}/metriques/run_{pipeline.run_id}.json")
    print(f"   • Temps réel : {projet_root}/metriques/temps_reel.json")
    print(f"   • Format Grafana : {projet_root}/metriques/grafana_metrics.prom")

    print(f"\n📈 Top 3 agents les plus chers :")
    agents_tries = sorted(pipeline.agents, key=lambda a: a.cout_usd, reverse=True)[:3]
    for i, agent in enumerate(agents_tries, 1):
        print(f"   {i}. {agent.nom} : ${agent.cout_usd:.4f} ({agent.duree_secondes:.1f}s)")

    print()


def main():
    provider = os.getenv('PRISME_LLM_PROVIDER', 'mistral')
    appel_llm = construire_appel_llm()

    pipeline = executer_avec_metriques(appel_llm, provider)
    afficher_resume(pipeline)


if __name__ == "__main__":
    main()
