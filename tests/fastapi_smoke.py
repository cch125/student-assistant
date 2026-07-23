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
            local_study_answer=lambda: None,
            health_answer=app.health_answer,
            ragflow_retrieve=lambda _question, _datasets: [],
            make_grounded_answer=app.make_grounded_answer,
            source_url=app.source_url,
            dataset_ids=lambda _route: ["test"],
        )
    )


def main() -> None:
    encoded = app.hash_password("correct-horse-battery")
    assert encoded != "correct-horse-battery"
    assert app.verify_password("correct-horse-battery", encoded)
    assert not app.verify_password("wrong", encoded)

    graph = build_graph()
    tool = graph.run(AgentState(question="高数 85分 4学分，英语 90分 3学分，计算加权平均分"))
    assert tool.route == "tool"
    assert "87.14" in tool.answer
    assert any(node.node == "tool_agent" for node in tool.trace)

    health = graph.run(AgentState(question="感冒了怎么办"))
    assert health.route == "health"
    assert "不能替你做诊断" in health.answer
    assert any(node.node == "health_agent" for node in health.trace)

    rejected = graph.run(AgentState(question="请告诉我同学的账号密码"))
    assert rejected.route == "reject"
    assert not rejected.ok

    attempts = {"count": 0}

    def retry_retrieve(_question: str, _datasets: list[str]) -> list[dict[str, object]]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return []
        return [
            {
                "similarity": 0.82,
                "document_name": "本科生请假申请表.md",
                "content": (
                    "本科生请假申请表由学院审核，学生填写完整后按学校办事流程提交，"
                    "具体审批部门和下载入口以来源文件原文为准。"
                ),
            }
        ]

    retry_graph = StudentAssistantGraph(
        AgentCallbacks(
            expand_intent=app.expand_intent,
            route_question=app.route_question,
            trace=app.trace,
            is_study_place_intent=app.is_study_place_intent,
            local_study_answer=lambda: None,
            health_answer=app.health_answer,
            ragflow_retrieve=retry_retrieve,
            make_grounded_answer=app.make_grounded_answer,
            source_url=app.source_url,
            dataset_ids=lambda _route: ["test"],
        )
    )
    retried = retry_graph.run(AgentState(question="本科生请假申请表在哪里下载？"))
    assert retried.ok
    assert retried.retry_count == 1
    assert retried.quality_status == "pass"
    assert [node.node for node in retried.trace].count("retriever_agent") == 2
    assert any(node.node == "rewrite_agent" for node in retried.trace)
    assert any(node.node == "quality_agent" and node.status == "retry" for node in retried.trace)

    linked_chunks = [
        {
            "similarity": 0.83,
            "document_name": "校园网学生申请.md",
            "content": "校园网账号由网络与教育技术中心受理，申请人应按页面要求填写资料，缴费标准以官方页面为准。",
        },
        {
            "similarity": 0.78,
            "document_name": "校园网学生申请.md",
            "content": "来源链接：https://netc.jnu.edu.cn/2018/1205/c9830a268227/page.psp",
        },
    ]
    linked = app.make_grounded_answer("校园网怎么申请", linked_chunks)
    assert linked[3] == "https://netc.jnu.edu.cn/2018/1205/c9830a268227/page.psp"
    assert linked[5][1]["source_url"] == linked[3]
    buttons = app.related_source_links(linked[3], linked[5], "校园网学生申请.md")
    assert len(buttons) == 1
    assert buttons[0]["url"] == linked[3]
    assert buttons[0]["label"] == "打开官方来源"

    irrelevant_graph = StudentAssistantGraph(
        AgentCallbacks(
            expand_intent=app.expand_intent,
            route_question=app.route_question,
            trace=app.trace,
            is_study_place_intent=app.is_study_place_intent,
            local_study_answer=lambda: None,
            health_answer=app.health_answer,
            ragflow_retrieve=lambda _question, _datasets: [
                {
                    "similarity": 0.91,
                    "document_name": "校园网学生申请.md",
                    "content": (
                        "校园网账号由网络与教育技术中心受理，申请人应按页面要求填写资料，"
                        "缴费标准和服务入口以学校官方页面为准。"
                    ),
                }
            ],
            make_grounded_answer=app.make_grounded_answer,
            source_url=app.source_url,
            dataset_ids=lambda _route: ["test"],
        )
    )
    irrelevant = irrelevant_graph.run(AgentState(question="宿舍空调坏了应该打哪个维修电话？"))
    assert not irrelevant.ok
    assert irrelevant.retry_count == 2
    assert irrelevant.quality_status == "reject"
    assert any("关键词重合" in issue for issue in irrelevant.quality_issues)
    assert irrelevant.document_name == ""
    assert irrelevant.source_url == ""
    assert irrelevant.similarity == 0.0
    assert irrelevant.matches == []
    assert irrelevant.retrieved == []

    stats = app.snapshot_stats()
    assert stats["datasets"] >= 1
    assert stats["documents"] >= 1
    assert stats["chunks"] >= 1
    multimodal = app.multimodal_stats()
    assert multimodal["images"] >= 1
    assert multimodal["structured_tables"] >= 1
    assert multimodal["resolved"] == multimodal["total"]

    print("fastapi smoke tests passed")


if __name__ == "__main__":
    main()
