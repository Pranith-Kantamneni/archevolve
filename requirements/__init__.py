from __future__ import annotations

from .models import ParsedRequirement, RequirementParser


requirement_parser = RequirementParser()


def parse_requirement(raw: str) -> ParsedRequirement:
    """Convenience function to parse a requirement."""
    return requirement_parser.parse(raw)