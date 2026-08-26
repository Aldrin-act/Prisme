"""Faux modèle partagé par les tests unitaires des agents (Étape 2 de la
migration LangChain, §5.6). N'implémente que la surface utilisée par les
agents (`with_structured_output(...).invoke(...)`, `bind_tools(...)`) — les
fakes de `langchain_core.language_models.fake_chat_models`
(`FakeMessagesListChatModel` etc.) n'implémentent pas `bind_tools`, donc
`with_structured_output` y lève `NotImplementedError` quel que soit `method=`
(vérifié : c'est la `BaseChatModel` de base qui l'exige, indépendamment du
fournisseur réel)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage


class _RunnableStructureFactice:
    def __init__(self, sortie: dict[str, Any]) -> None:
        self._sortie = sortie

    def invoke(self, messages: Any) -> dict[str, Any]:
        return self._sortie


class _ModeleAvecOutilsFactice:
    """Simule `modele.bind_tools(outils)` (voir
    `client_llm.invoquer_agent_avec_outils`) — renvoie toujours une réponse
    sans appel d'outil demandé, pour que les tests d'agents existants
    n'aient rien à simuler tant qu'ils ne testent pas spécifiquement la
    boucle d'outils elle-même."""

    def invoke(self, messages: Any) -> AIMessage:
        return AIMessage(content="")


class ModeleFactice:
    """Simule un `BaseChatModel` LangChain pour les tests d'agents — jamais
    de requête réseau, `with_structured_output(...)` renvoie directement
    `raw`/`parsed`/`parsing_error` fournis à la construction."""

    def __init__(
        self,
        raw_content: str,
        parsed: Any = None,
        parsing_error: Exception | None = None,
    ) -> None:
        self._raw_content = raw_content
        self._parsed = parsed
        self._parsing_error = parsing_error

    def with_structured_output(
        self, schema: type, include_raw: bool = True, method: str | None = None
    ) -> _RunnableStructureFactice:
        return _RunnableStructureFactice(
            {
                "raw": AIMessage(content=self._raw_content),
                "parsed": self._parsed,
                "parsing_error": self._parsing_error,
            }
        )

    def bind_tools(self, outils: Any) -> _ModeleAvecOutilsFactice:
        return _ModeleAvecOutilsFactice()
