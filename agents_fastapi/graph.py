from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .state import AgentState

MIN_GROUNDED_SCORE = 0.2
MAX_RETRIEVAL_RETRIES = 2


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
    polish_answer: Callable[
        [str, str, list[dict[str, Any]], list[dict[str, str]]],
        tuple[str, str],
    ] = lambda _question, answer, _matches, _messages: (answer, "生成最终回答")


class GraphState(TypedDict):
    state: AgentState


class StudentAssistantGraph:
    """FastAPI 使用的真实 LangGraph 多智能体编排。"""

    def __init__(self, callbacks: AgentCallbacks):
        self.cb = callbacks
        graph = StateGraph(GraphState)
        graph.add_node("intent_agent", self.intent_agent)
        graph.add_node("router_agent", self.router_agent)
        graph.add_node("reject_agent", self.reject_agent)
        graph.add_node("tool_agent", self.tool_agent)
        graph.add_node("health_agent", self.health_agent)
        graph.add_node("study_place_agent", self.study_place_agent)
        graph.add_node("retriever_agent", self.retriever_agent)
        graph.add_node("quality_agent", self.quality_agent)
        graph.add_node("rewrite_agent", self.rewrite_agent)
        graph.add_node("reflection_agent", self.reflection_agent)
        graph.add_node("answer_agent", self.answer_agent)
        graph.add_edge(START, "intent_agent")
        graph.add_edge("intent_agent", "router_agent")
        graph.add_conditional_edges(
            "router_agent",
            self.route_after_router,
            {
                "reject": "reject_agent",
                "tool": "tool_agent",
                "health": "health_agent",
                "study": "study_place_agent",
                "retrieve": "retriever_agent",
            },
        )
        graph.add_edge("reject_agent", "reflection_agent")
        graph.add_edge("tool_agent", "reflection_agent")
        graph.add_edge("health_agent", "retriever_agent")
        graph.add_conditional_edges(
            "study_place_agent",
            lambda value: "quality" if value["state"].answer else "retrieve",
            {"quality": "quality_agent", "retrieve": "retriever_agent"},
        )
        graph.add_edge("retriever_agent", "quality_agent")
        graph.add_conditional_edges(
            "quality_agent",
            self.route_after_quality,
            {
                "pass": "reflection_agent",
                "retry": "rewrite_agent",
                "reject": "reflection_agent",
            },
        )
        graph.add_edge("rewrite_agent", "retriever_agent")
        graph.add_edge("reflection_agent", "answer_agent")
        graph.add_edge("answer_agent", END)
        self.compiled = graph.compile(checkpointer=MemorySaver())

    def run(self, state: AgentState, thread_id: str | None = None) -> AgentState:
        config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}
        return self.compiled.invoke({"state": state}, config=config)["state"]

    def intent_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        started = time.perf_counter()
        state.expanded_question, detail = self.cb.expand_intent(state.question)
        state.retrieval_query = state.expanded_question
        state.max_retries = MAX_RETRIEVAL_RETRIES
        state.trace.append(self.cb.trace("intent_agent", "success", detail, state.expanded_question, start=started))
        return value

    def router_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        started = time.perf_counter()
        state.route, state.route_reason = self.cb.route_question(state.expanded_question)
        status = "rejected" if state.route == "reject" else "success"
        state.trace.append(self.cb.trace("router_agent", status, state.route_reason, state.expanded_question, start=started))
        return value

    def route_after_router(self, value: GraphState) -> str:
        state = value["state"]
        if state.route == "retrieve" and self.cb.is_study_place_intent(state.expanded_question):
            return "study"
        return state.route

    def reject_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        state.ok = False
        state.answer = "这个问题涉及隐私、安全或未公开信息，我不能提供相关内容。"
        state.trace.append(self.cb.trace("reject_agent", "rejected", "安全规则拒答", state.expanded_question))
        return value

    def tool_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        pairs = re.findall(r"(\d+(?:\.\d+)?)\s*分?[，,、\s]*(\d+(?:\.\d+)?)\s*学分", state.question)
        if pairs:
            weighted = sum(float(score) * float(credit) for score, credit in pairs)
            credits = sum(float(credit) for _, credit in pairs)
            state.answer = f"按成绩×学分计算：总学分 {credits:g}，加权平均分 {weighted / credits:.2f}。"
        else:
            state.ok = False
            state.answer = "请按“高数 85分 4学分，英语 90分 3学分”的格式输入，我会计算加权平均分。"
        state.trace.append(self.cb.trace("tool_agent", "success" if pairs else "rejected", "执行加权平均分计算工具", state.expanded_question))
        return value

    def health_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        state.answer = self.cb.health_answer(state.question)
        state.expanded_question = f"{state.expanded_question} 暨南大学 校医 门诊 医务室 医保 公费医疗"
        state.trace.append(self.cb.trace("health_agent", "success", "使用医疗安全模板并补充校内服务检索词", state.expanded_question))
        return value

    def study_place_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        local = self.cb.local_study_answer()
        if local:
            state.answer = str(local["answer"])
            state.document_name = str(local["document_name"])
            state.source_url = str(local["source_url"])
            state.similarity = float(local["similarity"])
            state.matches = [{"document_name": state.document_name, "similarity": state.similarity, "snippet": str(local["content"])[:260]}]
            state.trace.append(self.cb.trace("study_place_agent", "success", "命中本地高可信图书馆资料", state.expanded_question, state.similarity))
        else:
            state.trace.append(self.cb.trace("study_place_agent", "error", "本地资料不存在，转入 RAGFlow 检索", state.expanded_question))
        return value

    def retriever_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        started = time.perf_counter()
        try:
            query = state.retrieval_query or state.expanded_question
            chunks = self.cb.ragflow_retrieve(query, self.cb.dataset_ids(state.route))
            state.retrieved = chunks
            top_score = float((chunks[0] or {}).get("similarity") or 0) if chunks else 0
            state.trace.append(self.cb.trace("retriever_agent", "success", f"第 {state.retry_count + 1} 轮召回 {len(chunks)} 个分块", query, top_score, started))
            if state.route != "health":
                state.ok, state.answer, state.document_name, state.source_url, state.similarity, state.matches = self.cb.make_grounded_answer(state.question, chunks)
            elif chunks:
                top = chunks[0]
                state.document_name = str(top.get("document_keyword") or top.get("document_name") or "")
                content = str(top.get("content") or top.get("content_with_weight") or "")
                state.source_url = self.cb.source_url(content)
                state.similarity = float(top.get("similarity") or 0)
                state.matches = [{"document_name": state.document_name, "similarity": state.similarity, "snippet": content[:260]}]
        except Exception as exc:
            state.retrieved = []
            state.trace.append(self.cb.trace("retriever_agent", "error", str(exc)[:220], state.retrieval_query, start=started))
            if state.route != "health":
                state.ok = False
                state.answer = "当前知识库检索失败。为避免误导，我不会猜测答案，请检查 RAGFlow 配置和运行状态。"
        return value

    @staticmethod
    def required_intent_terms(question: str) -> list[str]:
        groups = [
            ["请假"],
            ["学生证"],
            ["休学"],
            ["复学"],
            ["退学"],
            ["转专业"],
            ["辅修"],
            ["校巴", "班车"],
            ["图书馆", "开馆"],
            ["校园网"],
        ]
        return next((group for group in groups if any(term in question for term in group)), [])

    @staticmethod
    def question_bigrams(question: str) -> list[str]:
        ignored = {
            "暨南",
            "南大",
            "大学",
            "学生",
            "学校",
            "请问",
            "怎么",
            "怎样",
            "如何",
            "哪里",
            "什么",
            "办理",
            "申请",
            "相关",
            "流程",
            "材料",
            "入口",
            "部门",
            "电话",
            "时间",
            "下载",
            "审批",
            "表格",
            "服务",
        }
        terms: list[str] = []
        for segment in re.findall(r"[\u4e00-\u9fff]{2,}", question):
            terms.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        return [term for term in dict.fromkeys(terms) if term not in ignored][:24]

    def quality_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        started = time.perf_counter()
        issues: list[str] = []
        if state.route == "health":
            state.quality_status = "pass"
            state.quality_issues = []
            state.trace.append(self.cb.trace("quality_agent", "success", "医疗安全模板通过；知识库资料仅作服务入口补充", state.retrieval_query, state.similarity, started))
            return value

        if not state.ok:
            issues.append("回答状态未通过")
        if not state.retrieved and not state.matches:
            issues.append("没有召回知识分块")
        if state.similarity < MIN_GROUNDED_SCORE:
            issues.append(f"最高相似度 {state.similarity:.3f} 低于阈值 {MIN_GROUNDED_SCORE:.1f}")
        if not state.document_name:
            issues.append("缺少来源文档")

        evidence = " ".join(
            [
                state.document_name,
                state.answer,
                *[str(item.get("document_name", "")) + " " + str(item.get("snippet", "")) for item in state.matches],
            ]
        )
        required_terms = self.required_intent_terms(state.question)
        if required_terms and not any(term in evidence for term in required_terms):
            issues.append(f"召回内容未覆盖问题关键事项：{'/'.join(required_terms)}")
        elif not required_terms:
            lexical_terms = self.question_bigrams(state.question)
            if lexical_terms and not any(term in evidence for term in lexical_terms):
                issues.append("召回内容与原问题缺少有效关键词重合")

        state.quality_issues = issues
        if not issues:
            state.quality_status = "pass"
            status = "success"
            detail = "Harness 通过：分数、来源和关键事项均满足要求"
        elif state.retry_count < state.max_retries:
            state.quality_status = "retry"
            status = "retry"
            detail = f"Harness 要求重试：{'；'.join(issues)}"
        else:
            state.quality_status = "reject"
            state.ok = False
            state.answer = "经过多轮检索仍未找到足以支撑答案的可靠资料。为避免误导，我无法确认，请联系对应业务部门或查看学校官方通知。"
            state.document_name = ""
            state.source_url = ""
            state.similarity = 0.0
            state.matches = []
            state.retrieved = []
            status = "rejected"
            detail = f"达到最大重试次数，拒答：{'；'.join(issues)}"
        state.trace.append(self.cb.trace("quality_agent", status, detail, state.retrieval_query, state.similarity, started))
        return value

    def route_after_quality(self, value: GraphState) -> str:
        return value["state"].quality_status

    def rewrite_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        state.retry_count += 1
        q = state.question
        intent_queries = [
            (["请假"], "暨南大学 本科生请假申请表 下载服务 学籍相关文件 审批"),
            (["学生证"], "暨南大学 学生证 补办 办理流程 负责部门 材料"),
            (["休学"], "暨南大学 本科生休学 申请 办理部门 受理时间"),
            (["复学"], "暨南大学 本科生复学申请 办理流程 材料"),
            (["退学"], "暨南大学 学生退学申请 审核 签字 流程"),
            (["转专业"], "暨南大学 本科生转专业 申请表 转出学院 转入学院"),
            (["图书馆", "自习"], "暨南大学 图书馆 开馆时间 座位预约 空间预约"),
        ]
        precise = next((text for terms, text in intent_queries if any(term in q for term in terms)), "")
        if not precise:
            precise = f"{q} 暨南大学 官方通知 办理流程 负责部门 所需材料"
        if state.retry_count > 1:
            precise = f"{precise} 事项名称 下载入口 联系方式"
        state.retrieval_query = precise
        state.ok = True
        state.answer = ""
        state.document_name = ""
        state.source_url = ""
        state.similarity = 0.0
        state.matches = []
        state.retrieved = []
        state.trace.append(self.cb.trace("rewrite_agent", "success", f"第 {state.retry_count} 次查询改写", precise))
        return value

    def reflection_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        status = "success" if state.ok or state.route == "health" else "rejected"
        detail = f"答案已完成来源、相似度和拒答检查；检索重试 {state.retry_count} 次"
        if state.route == "health":
            detail = "医疗回答已通过安全边界检查，不替代诊断"
        state.trace.append(self.cb.trace("reflection_agent", status, detail, state.expanded_question, state.similarity))
        return value

    def answer_agent(self, value: GraphState) -> GraphState:
        state = value["state"]
        detail = "生成最终回答"
        if state.ok and state.route == "retrieve" and state.matches:
            state.answer, detail = self.cb.polish_answer(
                state.question,
                state.answer,
                state.matches,
                state.messages,
            )
        state.trace.append(self.cb.trace("answer_agent", "success", detail, state.expanded_question))
        return value
