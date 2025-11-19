from dataclasses import dataclass, asdict
from typing import Any, Dict

from services.rag_service import RAGService


@dataclass
class AgentDecision:
    """Represents the routing result."""

    recommended_agent: str
    reasoning: str


class OrchestratorAgent:
    """
    Task router that decides which specialized agent should handle a request.

    At the moment only the RAG path is implemented, but the structure makes it
    straightforward to plug in the email, drive, or HR agents later.
    """

    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service

    def decide_agent(self, user_prompt: str) -> AgentDecision:
        # Placeholder heuristic — always use the knowledge base until the other agents are ready.
        return AgentDecision(
            recommended_agent="rag",
            reasoning="Specialized agents are not yet available. Defaulting to knowledge-base RAG.",
        )

    def handle_user_request(self, user_prompt: str) -> Dict[str, Any]:
        decision = self.decide_agent(user_prompt)
        if decision.recommended_agent != "rag":
            raise NotImplementedError(f"Agent '{decision.recommended_agent}' is not yet implemented.")

        rag_result = self.rag_service.answer(user_prompt)
        return {
            "decision": asdict(decision),
            "result": rag_result,
        }
