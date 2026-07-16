"""agent_comprehension — mapping ERP → T-R-C-O assisté par LLM (§5.4 bis).

Chemin **secondaire**, pour un ERP sans adaptateur écrit à la main dédié.
`adapters/erp_reference/` et `adapters/greensig/` restent le chemin par
défaut, déterministe et gratuit (§6, Couche 1 de la note de cadrage) — cet
agent ne les remplace pas, il comble le trou quand aucun `translator.py`
n'existe encore pour un ERP donné. Voir `agent.py` pour le détail de la
garantie : le même garde-fou déterministe (§6.7, `InstanceTRCO`) que pour
tout autre payload T-R-C-O reste l'unique arbitre de ce que produit l'agent.
"""

from .agent import ResultatComprehension, comprendre_donnees_erp

__all__ = ["ResultatComprehension", "comprendre_donnees_erp"]
