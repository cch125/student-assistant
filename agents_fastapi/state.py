from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Route = Literal["retrieve", "tool", "health", "reject"]


@dataclass
class AgentState:
    question: str
    messages: list[dict[str, str]] = field(default_factory=list)
    expanded_question: str = ""
    route: Route = "retrieve"
    route_reason: str = ""
    answer: str = ""
    ok: bool = True
    document_name: str = ""
    source_url: str = ""
    similarity: float = 0.0
    matches: list[dict[str, Any]] = field(default_factory=list)
    trace: list[Any] = field(default_factory=list)
    retrieved: list[dict[str, Any]] = field(default_factory=list)

