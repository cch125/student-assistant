from __future__ import annotations

import os
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from ragflow_auth import get_api_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAGFLOW_SDK = PROJECT_ROOT.parent / "ragflow" / "sdk" / "python"

BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:8080")
DATASET_NAME = os.getenv("RAGFLOW_CORE_DATASET_NAME", "暨南大学学生助手-核心服务卡片")
MIN_ACCEPT_SIMILARITY = float(os.getenv("MIN_ACCEPT_SIMILARITY", "0.24"))
UNANSWERED_LOG = PROJECT_ROOT / "data" / "feedback" / "unanswered_questions.jsonl"
SERVICE_CARD_DIR = PROJECT_ROOT / "data" / "cleaned" / "service_cards"
LOCAL_KEYWORD_SIMILARITY = MIN_ACCEPT_SIMILARITY + 0.05


def pick_field(content: str, field: str) -> str:
    pattern = rf"{re.escape(field)}：(.+?)(?:\n\n|\r\n\r\n|$)"
    match = re.search(pattern, content, flags=re.S)
    if not match:
        return ""
    return " ".join(match.group(1).split())


def pick_block(content: str, field: str) -> list[str]:
    pattern = rf"^{re.escape(field)}：\s*\n(.+?)(?:\n\n\S+：|\Z)"
    match = re.search(pattern, content, flags=re.S | re.M)
    if not match:
        return []
    lines = []
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\d+\.\s*", "", line)
        line = re.sub(r"^-\s*", "", line)
        if line:
            lines.append(line)
    return lines


def local_card_content(document_name: str, fallback: str) -> str:
    if document_name:
        path = SERVICE_CARD_DIR / document_name
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    return fallback


def guide_from_content(content: str) -> dict[str, Any]:
    return {
        "category": pick_field(content, "类别"),
        "service_type": pick_field(content, "事项类型"),
        "department": pick_field(content, "负责部门"),
        "audience": pick_field(content, "适用对象"),
        "entrance": pick_field(content, "办理入口"),
        "materials": pick_field(content, "所需材料"),
        "steps": pick_block(content, "办理步骤"),
        "notes": pick_block(content, "注意事项"),
    }


def match_from_content(document_name: str, content: str, similarity: float) -> dict[str, Any]:
    return {
        "document_name": document_name,
        "similarity": similarity,
        "answer": pick_field(content, "直接回答"),
        "source_url": pick_field(content, "来源链接"),
        "guide": guide_from_content(content),
        "snippet": " ".join(content.split())[:300],
    }


def local_keyword_fallback(question: str) -> dict[str, Any] | None:
    question_text = question.lower()
    best: tuple[int, Path, str] | None = None
    for path in SERVICE_CARD_DIR.glob("*.md"):
        content = path.read_text(encoding="utf-8", errors="replace")
        keywords = [
            keyword.strip().lower()
            for keyword in pick_field(content, "关键词").replace("，", ",").split(",")
            if keyword.strip()
        ]
        title = path.stem.lower()
        score = 0
        if title and title in question_text:
            score += 3
        for keyword in keywords:
            if len(keyword) >= 2 and keyword in question_text:
                score += 2 if len(keyword) >= 4 else 1
        if score >= 2 and (best is None or score > best[0]):
            best = (score, path, content)
    if best is None:
        return None
    return match_from_content(best[1].name, best[2], LOCAL_KEYWORD_SIMILARITY)


def load_ragflow():
    if str(RAGFLOW_SDK) not in sys.path:
        sys.path.insert(0, str(RAGFLOW_SDK))
    from ragflow_sdk import RAGFlow

    return RAGFlow(api_key=get_api_key(), base_url=BASE_URL)


def log_unanswered(question: str, reason: str, matches: list[dict[str, Any]]) -> None:
    UNANSWERED_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "reason": reason,
        "top_matches": [
            {
                "document_name": item.get("document_name", ""),
                "similarity": item.get("similarity", 0),
                "answer": item.get("answer", ""),
                "source_url": item.get("source_url", ""),
            }
            for item in matches[:3]
        ],
    }
    with UNANSWERED_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def ask_core_service(question: str) -> dict[str, Any]:
    question = question.strip()
    if not question:
        return {
            "ok": False,
            "answer": "请输入一个问题。",
            "source_url": "",
            "document_name": "",
            "similarity": 0,
            "matches": [],
            "guide": {},
            "threshold": MIN_ACCEPT_SIMILARITY,
        }

    rag = load_ragflow()
    dataset = rag.list_datasets(name=DATASET_NAME)[0]
    chunks = rag.retrieve(
        dataset_ids=[dataset.id],
        question=question,
        page_size=3,
        similarity_threshold=0.01,
        vector_similarity_weight=0.1,
        top_k=20,
        keyword=True,
    )

    matches = []
    for chunk in chunks[:3]:
        content = getattr(chunk, "content", "") or ""
        document_name = getattr(chunk, "document_name", "")
        full_content = local_card_content(document_name, content)
        matches.append(match_from_content(document_name, full_content, float(getattr(chunk, "similarity", 0) or 0)))

    keyword_match = local_keyword_fallback(question)
    if keyword_match:
        for item in matches:
            if item["document_name"] == keyword_match["document_name"]:
                item["similarity"] = max(item["similarity"], keyword_match["similarity"])
                break
        else:
            matches.append(keyword_match)

    if not matches or not matches[0]["answer"]:
        log_unanswered(question, "no_direct_answer", matches)
        return {
            "ok": False,
            "answer": "当前知识库未收录明确材料。",
            "source_url": "",
            "document_name": "",
            "similarity": 0,
            "matches": matches,
            "guide": {},
            "threshold": MIN_ACCEPT_SIMILARITY,
        }

    best = max(matches, key=lambda item: item["similarity"])
    if best["similarity"] < MIN_ACCEPT_SIMILARITY:
        log_unanswered(question, "low_similarity", matches)
        return {
            "ok": False,
            "answer": "当前知识库未收录明确材料。为避免误导学生，我不会根据不相关资料猜测答案。",
            "source_url": "",
            "document_name": best["document_name"],
            "similarity": best["similarity"],
            "matches": matches,
            "guide": best.get("guide", {}),
            "reason": "low_similarity",
            "threshold": MIN_ACCEPT_SIMILARITY,
        }

    return {
        "ok": True,
        "answer": best["answer"],
        "source_url": best["source_url"],
        "document_name": best["document_name"],
        "similarity": best["similarity"],
        "matches": matches,
        "guide": best.get("guide", {}),
        "reason": "answered",
        "threshold": MIN_ACCEPT_SIMILARITY,
    }
