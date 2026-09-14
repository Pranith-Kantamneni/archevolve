from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentTraceEntry, LLMClient
from ..memory.experience_memory import JsonExperienceMemory, ExperienceEntry


class ExperienceMemoryAgent(BaseAgent):
    """Agent responsible for maintaining long-term architectural experience memory.

    VERY IMPORTANT:
    Stores BOTH SUCCESSFUL and FAILED experiences.
    Before generating a new mutation, retrieves relevant previous successes AND failures
    to inform the evolution agent.

    Stored record structure:
    {
        architecture,
        application_type,
        requirements,
        generation,
        evaluation_scores,
        fitness,
        outcome: "success" | "failure",
        reason,
        weaknesses,
        changes_made,
        improvements,
        experience_used
    }
    """

    def __init__(
        self,
        persistence_path: str = "experience_memory.json",
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(
            name="Experience Memory Agent",
            role="Maintains dual successful and failed architectural evolution memory to guide progressive optimization",
            llm_client=llm_client,
        )
        self.memory = JsonExperienceMemory(persistence_path=persistence_path)

    def store_experience(
        self,
        architecture: str,
        application_type: str,
        requirements: str,
        generation: int,
        evaluation_scores: Dict[str, float],
        fitness: float,
        outcome: str,
        reason: str,
        weaknesses: List[str],
        changes_made: List[str],
        improvements: List[str],
        experience_used: Optional[List[str]] = None,
    ) -> Tuple[ExperienceEntry, AgentTraceEntry]:
        """Store a single evolution experience (either success or failure)."""
        entry = self.memory.add(
            architecture_name=architecture,
            generation=generation,
            objective_scores=evaluation_scores,
            fitness=fitness,
            modifications=changes_made,
            weaknesses=weaknesses,
            improvements=improvements,
            requirement_context={"application_type": application_type, "raw_input": requirements},
            outcome=outcome,
            reason=reason,
            changes_made=changes_made,
            experience_used=experience_used,
            application_type=application_type,
            requirements=requirements,
            architecture=architecture,
        )

        trace = AgentTraceEntry(
            agent=self.name,
            action="Store Experience",
            architecture=architecture,
            reason=f"Recorded {outcome.upper()} experience: {reason}",
            outcome=outcome,
            fitness=fitness,
            generation=generation,
            details={
                "outcome": outcome,
                "changes_made": changes_made,
                "improvements": improvements,
                "weaknesses": weaknesses,
                "scores": evaluation_scores,
            },
        )

        return entry, trace

    def retrieve_experiences(
        self,
        application_type: Optional[str] = None,
        weaknesses: Optional[List[str]] = None,
        limit: int = 3,
        generation: int = 0,
    ) -> Tuple[Dict[str, List[ExperienceEntry]], AgentTraceEntry]:
        """Retrieve relevant past successes AND failures before generating mutations."""
        res = self.memory.get_relevant_experiences(
            application_type=application_type,
            weaknesses=weaknesses,
            limit=limit,
        )

        success_count = len(res.get("successes", []))
        failure_count = len(res.get("failures", []))

        reason = f"Retrieved {success_count} prior success(es) and {failure_count} prior failure(s) for domain '{application_type or 'general'}'"

        trace = AgentTraceEntry(
            agent=self.name,
            action="Query Experience Memory",
            architecture="N/A",
            reason=reason,
            outcome="success",
            generation=generation,
            details={
                "success_reasons": [s.reason for s in res.get("successes", [])],
                "failure_reasons": [f.reason for f in res.get("failures", [])],
            },
        )

        return res, trace

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self.memory
