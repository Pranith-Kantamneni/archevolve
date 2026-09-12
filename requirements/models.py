from __future__ import annotations
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any


class ParsedRequirement(BaseModel):
    """Structured parsed representation of a software requirement."""

    # Functional requirements
    functional: List[str] = Field(default_factory=list, description="Functional requirements")

    # Non-functional requirements
    non_functional: List[str] = Field(default_factory=list, description="Non-functional requirements")

    # Expected users/load
    expected_users: Optional[int] = Field(default=None, ge=0, description="Expected number of concurrent users")

    # Performance requirements
    max_latency_ms: Optional[float] = Field(default=None, ge=0, description="Maximum acceptable latency in milliseconds")
    throughput_req: Optional[str] = Field(default=None, description="Throughput requirements")

    # Availability requirements
    availability_percentage: Optional[float] = Field(
        default=None, ge=0, le=100, description="Availability percentage (e.g., 99.9)"
    )

    # Security requirements
    security_level: Optional[str] = Field(
        default=None, description="Security level (e.g., 'high', 'medium', 'low')"
    )
    data_encryption_required: bool = Field(
        default=False, description="Whether data encryption is required"
    )
    authentication_required: bool = Field(
        default=True, description="Whether authentication is required"
    )

    # Scalability requirements
    scalability_type: Optional[str] = Field(
        default=None, description="Type of scalability (e.g., 'horizontal', 'vertical')"
    )
    max_concurrent_streams: Optional[int] = Field(
        default=None, ge=0, description="Maximum concurrent streams/requests"
    )

    # Cost constraints
    max_monthly_cost: Optional[float] = Field(
        default=None, ge=0, description="Maximum monthly cost in USD"
    )
    cost_sensitive: bool = Field(
        default=False, description="Whether cost is a primary concern"
    )

    # Technology constraints
    preferred_technologies: List[str] = Field(
        default_factory=list, description="Explicitly mentioned preferred technologies"
    )
    constrained_technologies: List[str] = Field(
        default_factory=list, description="Explicitly constrained/avoided technologies"
    )

    # Other constraints
    compliance_requirements: List[str] = Field(
        default_factory=list, description="Compliance requirements (e.g., GDPR, HIPAA)"
    )
    deployment_environment: Optional[str] = Field(
        default=None, description="Deployment environment (e.g., 'cloud', 'on-premise', 'edge')"
    )

    # Raw input for reference
    raw_input: str = Field(description="Original raw requirement text")

    @validator("raw_input")
    def raw_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("raw_input must not be empty")
        return v

    def __str__(self) -> str:
        return self.raw_input


class RequirementParser:
    """Parses natural-language software requirements into structured models."""

    def parse(self, raw_requirement: str) -> ParsedRequirement:
        """Parse a natural-language requirement string into a structured ParsedRequirement."""
        text = raw_requirement.strip()

        # Extract structured elements using deterministic rules
        parsed = ParsedRequirement(raw_input=text)

        self._extract_functional_requirements(text, parsed)
        self._extract_non_functional_requirements(text, parsed)
        self._extract_user_load(text, parsed)
        self._extract_performance_requirements(text, parsed)
        self._extract_availability_requirements(text, parsed)
        self._extract_security_requirements(text, parsed)
        self._extract_scalability_requirements(text, parsed)
        self._extract_cost_constraints(text, parsed)
        self._extract_technology_constraints(text, parsed)
        self._extract_compliance_requirements(text, parsed)
        self._extract_deployment_environment(text, parsed)

        return parsed

    # --- Extraction methods ---

    def _extract_functional_requirements(self, text: str, parsed: ParsedRequirement) -> None:
        keywords = ["e-commerce", "platform", "user management", "payment", "authentication", "api", "database"]
        text_lower = text.lower()
        found = [kw for kw in keywords if kw in text_lower]
        if found:
            parsed.functional = found
        elif not parsed.functional:
            # Default: if no functional keywords matched but text exists
            parsed.functional = ["general software system"]

    def _extract_non_functional_requirements(self, text: str, parsed: ParsedRequirement) -> None:
        # Capture any remaining non-functional aspects not already categorized
        text_lower = text.lower()
        nf_keywords = ["high availability", "low latency", "secure", "scalable", "fault tolerant"]
        found = [kw for kw in nf_keywords if kw in text_lower]
        if found:
            parsed.non_functional = found

    def _extract_user_load(self, text: str, parsed: ParsedRequirement) -> None:
        import re

        # Patterns like "10,000 concurrent users" or "10000 users"
        patterns = [
            r"(\d{1,3}(?:,\d{3})*)\s*concurrent\s*users",
            r"(\d{1,3}(?:,\d{3})*)\s*users",
            r"(\d+(?:\.\d+)?)\s*k\s*concurrent",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = int(match.group(1).replace(",", ""))
                parsed.expected_users = value
                break

    def _extract_performance_requirements(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        # Look for latency specifications
        if "low latency" in text_lower or "latency" in text_lower:
            parsed.max_latency_ms = 200  # default assumption for "low latency"
        # Look for specific ms values
        import re
        match = re.search(r"(\d+)\s*ms", text_lower)
        if match and not parsed.max_latency_ms:
            parsed.max_latency_ms = float(match.group(1))

    def _extract_availability_requirements(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        if "high availability" in text_lower or "availability" in text_lower:
            parsed.availability_percentage = 99.9

    def _extract_security_requirements(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        if "secure" in text_lower or "security" in text_lower:
            parsed.security_level = "high"
            parsed.data_encryption_required = True
            parsed.authentication_required = True

    def _extract_scalability_requirements(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        if "scalable" in text_lower or "scale" in text_lower:
            parsed.scalability_type = "horizontal"
            # Look for traffic spike mentions
            if "traffic spikes" in text_lower or "spike" in text_lower:
                parsed.max_concurrent_streams = 10000

    def _extract_cost_constraints(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        if "reasonable" in text_lower or "cost" in text_lower or "budget" in text_lower:
            parsed.cost_sensitive = True
            # Try to extract a max cost value
            import re
            match = re.search(r"\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:USD|dollars?|budget)", text_lower)
            if match:
                parsed.max_monthly_cost = float(match.group(1))

    def _extract_technology_constraints(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        tech_keywords = ["postgresql", "mysql", "mongodb", "redis", "docker", "kubernetes", "aws", "gcp", "azure"]
        found = [kw for kw in tech_keywords if kw in text_lower]
        if found:
            parsed.preferred_technologies = found

    def _extract_compliance_requirements(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        compliance = ["gdpr", "hipaa", "pci-dss", "sox"]
        found = [kw for kw in compliance if kw in text_lower]
        if found:
            parsed.compliance_requirements = found

    def _extract_deployment_environment(self, text: str, parsed: ParsedRequirement) -> None:
        text_lower = text.lower()
        if "cloud" in text_lower:
            parsed.deployment_environment = "cloud"
        elif "on-premise" in text_lower or "on-prem" in text_lower:
            parsed.deployment_environment = "on-premise"