from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents_fastapi.graph import AgentCallbacks, StudentAssistantGraph
from agents_fastapi.state import AgentState
import app_fastapi as app


def build_graph() -> StudentAssistantGraph:
    return StudentAssistantGraph(
        AgentCallbacks(
            expand_intent=app.expand_intent,
            route_question=app.route_question,
            trace=app.trace,
            is_study_place_intent=app.is_study_place_intent,
            local_study_answer=app.local_study_answer,
            health_answer=app.health_answer,
            ragflow_retrieve=app.ragflow_retrieve,
            make_grounded_answer=app.make_grounded_answer,
            source_url=app.source_url,
            dataset_ids=app.active_dataset_ids,
        )
    )


def main() -> None:
    graph = build_graph()
    study = graph.run(AgentState(question="我有点想学习，没找到地方"))
    assert study.ok
    assert study.document_name == "图书馆开馆时间"
    assert any(node.node == "study_place_agent" for node in study.trace)

    health = graph.run(AgentState(question="感冒了怎么办"))
    assert health.route == "health"
    assert "不能替你做诊断" in health.answer
    assert any(node.node == "health_agent" for node in health.trace)

    print("fastapi smoke tests passed")


if __name__ == "__main__":
    main()
