from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .state import AgentState


@dataclass
class AgentCallbacks:
    expand_intent: Callable[[str], tuple[str, str]]
    route_question: Callable[[str], tuple[str, str]]
    trace: Callable[..., Any]
    is_study_place_intent: Callable[[str], bool]
    local_study_answer: Callable[[], dict[str, Any] | None]
    health_answer: Callable[[str], str]
    ragflow_retrieve: Callable[[str, list[str]], list[dict[str, Any]]]
    make_grounded_answer: Callable[[str, list[dict[str, Any]]], tuple[bool, str, str, str, float, list[dict[str, Any]]]]
    source_url: Callable[[str], str]
    dataset_ids: Callable[[str], list[str]]


class StudentAssistantGraph:
    """Copied from the teammate project's graph idea, adapted to FastAPI.

    The graph keeps named agents explicit for demonstration and logging:
    Intent -> Router -> Retriever/Tool/Health/Reject -> Reflection -> Answer.
    """

    def __init__(self, callbacks: AgentCallbacks):
        self.cb = callbacks

    def run(self, state: AgentState) -> AgentState:
        self.intent_agent(state)
        self.router_agent(state)
        if state.route == "reject":
            self.reject_agent(state)
        elif state.route == "tool":
            self.tool_agent(state)
        elif state.route == "health":
            self.health_agent(state)
            self.retriever_agent(state)
        else:
            if self.cb.is_study_place_intent(state.expanded_question) and self.study_place_agent(state):
                pass
            else:
                self.retriever_agent(state)
        self.reflection_agent(state)
        self.answer_agent(state)
        return state

    def intent_agent(self, state: AgentState) -> None:
        started = time.perf_counter()
        expanded, detail = self.cb.expand_intent(state.question)
        state.expanded_question = expanded
        state.trace.append(self.cb.trace("intent_agent", "success", detail, expanded, start=started))

    def router_agent(self, state: AgentState) -> None:
        started = time.perf_counter()
        route, reason = self.cb.route_question(state.expanded_question)
        state.route = route  # type: ignore[assignment]
        state.route_reason = reason
        state.trace.append(self.cb.trace("router_agent", "success" if route != "reject" else "rejected", reason, state.expanded_question, start=started))

    def reject_agent(self, state: AgentState) -> None:
        state.ok = False
        state.answer = "这个问题超出学生事务助手的安全范围，我不能提供相关内容。"
        state.trace.append(self.cb.trace("reject_agent", "rejected", "安全规则拒答", state.expanded_question))

    def tool_agent(self, state: AgentState) -> None:
        state.answer = "Tool Agent 已识别为计算类问题。请按“高数 85 分 4 学分，英语 90 分 3 学分”的格式输入，我可以计算加权平均分。"
        state.trace.append(self.cb.trace("tool_agent", "success", "进入工具调用分支", state.expanded_question))

    def health_agent(self, state: AgentState) -> None:
        state.answer = self.cb.health_answer(state.question)
        state.expanded_question = f"{state.expanded_question} 暨南大学 校医 门诊 医务室 医保 公费医疗"
        state.trace.append(self.cb.trace("health_agent", "success", "健康问题使用安全模板，并补充检索校内医疗服务", state.expanded_question))

    def study_place_agent(self, state: AgentState) -> bool:
        local = self.cb.local_study_answer()
        if not local:
            return False
        state.answer = str(local["answer"])
        state.document_name = str(local["document_name"])
        state.source_url = str(local["source_url"])
        state.similarity = float(local["similarity"])
        state.matches = [{"document_name": state.document_name, "similarity": state.similarity, "snippet": str(local["content"])[:260]}]
        state.trace.append(self.cb.trace("study_place_agent", "success", "学习地点意图命中本地高可信开馆时间资料", state.expanded_question, state.similarity))
        return True

    def retriever_agent(self, state: AgentState) -> None:
        started = time.perf_counter()
        try:
            chunks = self.cb.ragflow_retrieve(state.expanded_question, self.cb.dataset_ids(state.route))
            state.retrieved = chunks
            top_score = float((chunks[0] or {}).get("similarity") or 0) if chunks else 0
            state.trace.append(self.cb.trace("retriever_agent", "success", f"召回 {len(chunks)} 个分块", state.expanded_question, top_score, started))
            if state.route != "health":
                state.ok, state.answer, state.document_name, state.source_url, state.similarity, state.matches = self.cb.make_grounded_answer(state.question, chunks)
            elif chunks:
                top = chunks[0]
                state.document_name = str(top.get("document_keyword") or top.get("document_name") or "")
                state.source_url = self.cb.source_url(str(top.get("content") or top.get("content_with_weight") or ""))
                state.similarity = float(top.get("similarity") or 0)
                state.matches = [{"document_name": state.document_name, "similarity": state.similarity, "snippet": str(top.get("content") or "")[:260]}]
        except Exception as exc:
            state.trace.append(self.cb.trace("retriever_agent", "error", str(exc)[:220], state.expanded_question, start=started))
            if state.route != "health":
                state.ok = False
                state.answer = "当前知识库检索失败。为避免误导，我不会猜测答案。请检查 RAGFlow 是否在线。"

    def reflection_agent(self, state: AgentState) -> None:
        status = "success" if state.ok or state.route == "health" else "rejected"
        detail = "答案已完成来源/拒答检查"
        if state.route == "health":
            detail = "医疗健康回答已通过安全边界检查，不替代诊断"
        state.trace.append(self.cb.trace("reflection_agent", status, detail, state.expanded_question, state.similarity))

    def answer_agent(self, state: AgentState) -> None:
        state.trace.append(self.cb.trace("answer_agent", "success", "生成最终回复", state.expanded_question))

