from __future__ import annotations

import abc
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentTraceEntry(BaseModel):
    """Structured entry representing an action taken by an agent in the evolution trace."""
    agent: str
    action: str
    architecture: str = ""
    reason: str = ""
    outcome: str = ""  # e.g., "success", "failure", "selected", "rejected", "evaluated", "mutated", "generated", "finalized"
    fitness: Optional[float] = None
    generation: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: time.strftime("%H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "action": self.action,
            "architecture": self.architecture,
            "reason": self.reason,
            "outcome": self.outcome,
            "fitness": round(self.fitness, 2) if self.fitness is not None else None,
            "generation": self.generation,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class AgentMessage(BaseModel):
    """Inter-agent message for clear communication between specialized agents."""
    sender: str
    receiver: str
    topic: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: time.strftime("%H:%M:%S"))


class LLMClient:
    """Common LLM client interface for deterministic and LLM-assisted agent operation.

    Deterministic (default) mode needs no keys and never calls the network.
    LLM-assisted mode speaks the OpenAI-compatible ``/chat/completions`` API
    (works with OpenAI, Azure OpenAI, and any OpenAI-compatible gateway by
    overriding ``ARCHEVOLVE_LLM_BASE_URL``).  Every call is wrapped so any
    failure silently falls back to deterministic rule logic.
    """

    def __init__(self, use_llm: bool = False, model: Optional[str] = None):
        import os as _os

        self.use_llm = use_llm
        self.model = model or _os.environ.get("ARCHEVOLVE_LLM_MODEL", "gpt-4o")
        self.api_key = _os.environ.get("ARCHEVOLVE_LLM_API_KEY", "")
        self.base_url = _os.environ.get(
            "ARCHEVOLVE_LLM_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")

    def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Complete a prompt. Returns "" on any failure to trigger rule logic."""
        if not self.use_llm or not self.api_key:
            return ""
        try:
            import json as _json
            import urllib.request as _req

            body = _json.dumps({
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt or "You are a software-architecture expert."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 800,
            }).encode("utf-8")
            request = _req.Request(
                self.base_url + "/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with _req.urlopen(request, timeout=30) as resp:
                payload = _json.loads(resp.read().decode("utf-8"))
            choices = payload.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                return (content or "").strip()
        except Exception:
            pass
        return ""


class BaseAgent(abc.ABC):
    """Abstract base class for all specialized ARCHEVOLVE agents."""

    def __init__(self, name: str, role: str, llm_client: Optional[LLMClient] = None):
        self.name = name
        self.role = role
        self.llm_client = llm_client or LLMClient()
        self.inbox: List[AgentMessage] = []
        self.outbox: List[AgentMessage] = []

    def receive_message(self, message: AgentMessage) -> None:
        """Receive a message from another agent."""
        self.inbox.append(message)

    def send_message(self, receiver: str, topic: str, payload: Dict[str, Any]) -> AgentMessage:
        """Send a message to another agent."""
        msg = AgentMessage(sender=self.name, receiver=receiver, topic=topic, payload=payload)
        self.outbox.append(msg)
        return msg

    @abc.abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent's primary task."""
        raise NotImplementedError
