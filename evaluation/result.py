"""Single shared evaluator result type.

Historically each evaluator module defined its own identical ``EvaluatorResult``
class (5 copies).  They are now unified here; the per-module names remain
importable as aliases for backwards compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scoring import apply_ceiling, grade_for


class EvaluatorResult:
    """Result from an architecture evaluator (0-97 heuristic scale)."""

    def __init__(
        self,
        score: float,
        reasoning: str = "",
        strengths: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        reason: Optional[str] = None,
        breakdown: Optional[Dict[str, float]] = None,
        max_breakdown: Optional[Dict[str, float]] = None,
        grade: Optional[str] = None,
    ):
        self.score = apply_ceiling(score)
        self.reason = reason if reason is not None else reasoning
        self.reasoning = self.reason  # backwards-compatibility alias
        self.strengths = list(strengths or [])
        self.weaknesses = list(weaknesses or [])
        self.breakdown = dict(breakdown or {})
        self.max_breakdown = dict(max_breakdown or {})
        self.grade = grade or grade_for(self.score)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "grade": self.grade,
            "reason": self.reason,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "breakdown": dict(self.breakdown),
        }

    def __str__(self) -> str:
        return f"Score: {self.score:.1f} ({self.grade}) - {self.reason}"
