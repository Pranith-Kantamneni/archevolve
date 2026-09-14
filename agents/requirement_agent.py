from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

from .base import BaseAgent, AgentTraceEntry, LLMClient
from ..requirements import parse_requirement, ParsedRequirement
from ..requirements.constraints import apply_constraints_to_parsed


class StructuredRequirements(BaseModel):
    """Structured requirement specification produced by Requirement Analysis Agent."""
    raw_input: str
    application_type: str = ""
    functional: list[str] = Field(default_factory=list)
    non_functional: list[str] = Field(default_factory=list)
    expected_users: Optional[int] = None
    max_latency_ms: Optional[int] = None
    availability_percentage: Optional[float] = None
    security_level: Optional[str] = None
    data_encryption_required: bool = False
    authentication_required: bool = False
    scalability_type: Optional[str] = None
    max_concurrent_streams: Optional[int] = None
    cost_sensitive: bool = False
    compliance_requirements: list[str] = Field(default_factory=list)
    deployment_environment: Optional[str] = None
    preferred_technologies: list[str] = Field(default_factory=list)
    max_monthly_cost: Optional[float] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    derived_goals: list[str] = Field(default_factory=list)


class RequirementAnalysisAgent(BaseAgent):
    """Agent responsible for analyzing natural language requirements and constraints.

    Defined Input:
        - raw_requirement: Natural language description of the target system.
        - application_type: Application domain (e.g., 'E-commerce platform', 'Chat app').
        - constraints: User-specified constraints (budget, cloud provider, compliance, DB).

    Defined Output:
        - StructuredRequirements object with extracted functional/non-functional criteria and domain context.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(
            name="Requirement Analysis Agent",
            role="Extracts structured system requirements, architectural constraints, and operational goals",
            llm_client=llm_client,
        )

    def run(
        self,
        raw_requirement: str,
        application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Tuple[StructuredRequirements, AgentTraceEntry]:
        """Analyze requirements and produce structured specifications."""
        parsed: ParsedRequirement = parse_requirement(raw_requirement)
        parsed = apply_constraints_to_parsed(parsed, constraints or {})

        app_type = (application_type or "").strip()
        goals = []
        if parsed.expected_users and parsed.expected_users >= 10000:
            goals.append(f"High-concurrency support ({parsed.expected_users:,} users)")
        if parsed.cost_sensitive:
            goals.append("Strict infrastructure cost efficiency")
        if parsed.security_level == "high":
            goals.append("High-assurance security posture & encryption")
        if parsed.availability_percentage and parsed.availability_percentage >= 99.9:
            goals.append(f"High availability ({parsed.availability_percentage}%)")
        if parsed.max_latency_ms and parsed.max_latency_ms <= 100:
            goals.append(f"Low-latency response SLA (<= {parsed.max_latency_ms}ms)")

        structured = StructuredRequirements(
            raw_input=raw_requirement,
            application_type=app_type,
            functional=list(parsed.functional),
            non_functional=list(parsed.non_functional),
            expected_users=parsed.expected_users,
            max_latency_ms=parsed.max_latency_ms,
            availability_percentage=parsed.availability_percentage,
            security_level=parsed.security_level,
            data_encryption_required=parsed.data_encryption_required,
            authentication_required=parsed.authentication_required,
            scalability_type=parsed.scalability_type,
            max_concurrent_streams=parsed.max_concurrent_streams,
            cost_sensitive=parsed.cost_sensitive,
            compliance_requirements=list(parsed.compliance_requirements),
            deployment_environment=parsed.deployment_environment,
            preferred_technologies=list(parsed.preferred_technologies),
            max_monthly_cost=parsed.max_monthly_cost,
            constraints=dict(constraints or {}),
            derived_goals=goals,
        )

        reason = (
            f"Parsed {app_type or 'generic'} requirements: users={parsed.expected_users or 'default'}, "
            f"security={parsed.security_level}, cost_sensitive={parsed.cost_sensitive}, "
            f"availability={parsed.availability_percentage}%"
        )
        if constraints:
            reason += f" with {len(constraints)} constraint(s)"

        trace = AgentTraceEntry(
            agent=self.name,
            action="Analyze Requirements",
            architecture="N/A",
            reason=reason,
            outcome="success",
            generation=0,
            details={
                "application_type": app_type,
                "goals": goals,
                "constraints": constraints or {},
            },
        )

        return structured, trace
