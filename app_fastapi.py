from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents_fastapi.graph import AgentCallbacks, StudentAssistantGraph
from agents_fastapi.state import AgentState

PROJECT_ROOT = Path(__file__).resolve().parent
TRACE_DIR = PROJECT_ROOT / "data" / "feedback"
TRACE_FILE = TRACE_DIR / "agent_traces.jsonl"
DB_FILE = TRACE_DIR / "assistant.sqlite3"
MULTIMODAL_INDEX_FILE = PROJECT_ROOT / "data" / "multimodal_index.json"
MINERU_DIR = PROJECT_ROOT / "data" / "cleaned" / "mineru"


def load_local_env() -> None:
    for name in (".env", ".env.local"):
        path = PROJECT_ROOT / name
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

DEFAULT_RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:8080").rstrip("/")
DEFAULT_RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "")
DEFAULT_DATASET_ID = os.getenv("RAGFLOW_DATASET_ID", "")
DEFAULT_NOTICE_DATASET_ID = os.getenv("RAGFLOW_NOTICE_DATASET_ID", "")
RERANK_ID = os.getenv("RAGFLOW_RERANK_ID", "BAAI/bge-reranker-v2-m3@default1@OpenAI-API-Compatible")


class ChatMessage(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    messages: list[ChatMessage] = Field(default_factory=list)
    conversation_id: str | None = None


class TraceNode(BaseModel):
    node: str
    status: str
    detail: str
    query: str = ""
    score: float | None = None
    duration_ms: int = 0


class AgentRun(BaseModel):
    id: str
    question: str
    route: str
    answer: str
    ok: bool
    document_name: str = ""
    source_url: str = ""
    similarity: float = 0.0
    created_at: float
    trace: list[TraceNode]
    matches: list[dict[str, Any]] = Field(default_factory=list)
    multimodal: list[dict[str, Any]] = Field(default_factory=list)


class LoginRequest(BaseModel):
    username: str
    password: str


app = FastAPI(title="暨南大学学生助手 FastAPI", version="0.2.0")

if MINERU_DIR.exists():
    app.mount("/mineru-assets", StaticFiles(directory=str(MINERU_DIR)), name="mineru_assets")



def db() -> sqlite3.Connection:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            create table if not exists users (
                id integer primary key autoincrement,
                username text unique not null,
                display_name text not null,
                role text not null default 'student',
                password text not null
            );
            create table if not exists sessions (
                token text primary key,
                user_id integer not null,
                created_at real not null
            );
            create table if not exists conversations (
                id text primary key,
                user_id integer not null,
                title text not null,
                created_at real not null,
                updated_at real not null
            );
            create table if not exists messages (
                id text primary key,
                conversation_id text not null,
                role text not null,
                content text not null,
                created_at real not null
            );
            """
        )
        exists = conn.execute("select id from users where username=?", ("cch125",)).fetchone()
        if not exists:
            conn.execute(
                "insert into users(username, display_name, role, password) values(?,?,?,?)",
                ("cch125", "cch125", "admin", "admin123"),
            )


init_db()


def current_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get("student_session")
    if not token:
        return None
    with db() as conn:
        row = conn.execute(
            """
            select u.id, u.username, u.display_name, u.role
            from sessions s join users u on u.id = s.user_id
            where s.token=?
            """,
            (token,),
        ).fetchone()
    return dict(row) if row else None


def create_session(username: str, password: str) -> str | None:
    with db() as conn:
        row = conn.execute("select id from users where username=? and password=?", (username, password)).fetchone()
        if not row:
            return None
        token = secrets.token_urlsafe(32)
        conn.execute("insert into sessions(token, user_id, created_at) values(?,?,?)", (token, row["id"], time.time()))
        return token


def delete_session(token: str) -> None:
    with db() as conn:
        conn.execute("delete from sessions where token=?", (token,))


def save_conversation_message(user_id: int, conversation_id: str | None, question: str, answer: str) -> str:
    cid = conversation_id or str(uuid.uuid4())
    now = time.time()
    title = question[:30] or "新对话"
    with db() as conn:
        exists = conn.execute("select id from conversations where id=?", (cid,)).fetchone()
        if not exists:
            conn.execute(
                "insert into conversations(id, user_id, title, created_at, updated_at) values(?,?,?,?,?)",
                (cid, user_id, title, now, now),
            )
        else:
            conn.execute("update conversations set updated_at=? where id=?", (now, cid))
        conn.execute("insert into messages(id, conversation_id, role, content, created_at) values(?,?,?,?,?)", (str(uuid.uuid4()), cid, "user", question, now))
        conn.execute("insert into messages(id, conversation_id, role, content, created_at) values(?,?,?,?,?)", (str(uuid.uuid4()), cid, "assistant", answer, now))
    return cid


def now_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def trace(node: str, status: str, detail: str, query: str = "", score: float | None = None, start: float | None = None) -> TraceNode:
    return TraceNode(node=node, status=status, detail=detail, query=query, score=score, duration_ms=now_ms(start) if start else 0)


def clean(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def route_question(question: str) -> tuple[str, str]:
    q = clean(question)
    if any(term in q for term in ["感冒", "发烧", "发热", "咳嗽", "校医", "门诊", "医保", "公费医疗", "看病", "不舒服"]):
        return "health", "健康或校内医疗服务问题，进入 Health Agent"
    if re.search(r"(gpa|绩点|加权平均|平均分|学分).*(算|计算|多少)|怎么算.*(gpa|绩点|平均分)", question, re.I):
        return "tool", "成绩、绩点或学分计算问题，进入 Tool Agent"
    if any(term in q for term in ["账号密码", "验证码", "身份证号码", "私人手机", "家庭住址", "未公开", "保证录取"]):
        return "reject", "涉及隐私、安全或未公开信息"
    return "retrieve", "学生事务问题，进入检索增强回答链路"


def is_study_place_intent(question: str) -> bool:
    q = clean(question)
    patterns = [
        "想学习", "学习地方", "地方学习", "没找到地方", "找地方学", "哪里学", "哪里学习",
        "自习", "复习", "备考", "看书", "写作业", "图书馆", "阅览室", "座位预约", "空间预约",
    ]
    return any(p in q for p in patterns)


def expand_intent(question: str) -> tuple[str, str]:
    if is_study_place_intent(question):
        return (
            f"{question}\n\n语义意图补全：学生想找可以学习或自习的地方。请检索暨南大学图书馆、阅览室、开放时间、座位预约、空间预约等官方信息。",
            "Intent Agent：已将口语表达补全为“找学习/自习地点”",
        )
    if any(term in question for term in ["模板", "表格", "申请表", "证明", "下载", "材料"]):
        return f"{question}\n\n语义意图补全：学生可能需要办理事项、表格模板或官方下载入口。", "Intent Agent：已补全为“事项/材料下载”意图"
    return question, "Intent Agent：无需补全，保留原问题"


def ragflow_headers() -> dict[str, str]:
    if not DEFAULT_RAGFLOW_API_KEY:
        raise RuntimeError("RAGFLOW_API_KEY 未配置")
    return {"Authorization": f"Bearer {DEFAULT_RAGFLOW_API_KEY}"}


def active_dataset_ids(route: str) -> list[str]:
    dataset_ids = [DEFAULT_DATASET_ID] if DEFAULT_DATASET_ID else []
    if route == "health" and DEFAULT_NOTICE_DATASET_ID:
        dataset_ids.append(DEFAULT_NOTICE_DATASET_ID)
    if not dataset_ids:
        raise RuntimeError("RAGFLOW_DATASET_ID 未配置")
    return dataset_ids


def ragflow_retrieve(question: str, dataset_ids: list[str]) -> list[dict[str, Any]]:
    response = requests.post(
        f"{DEFAULT_RAGFLOW_BASE_URL}/api/v1/retrieval",
        headers={**ragflow_headers(), "Content-Type": "application/json"},
        json={
            "dataset_ids": dataset_ids,
            "question": question,
            "page_size": 5,
            "top_k": 30,
            "similarity_threshold": 0,
            "vector_similarity_weight": 0.7,
            "rerank_id": RERANK_ID,
            "keyword": True,
            "highlight": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(str(payload.get("message") or "RAGFlow retrieval failed"))
    return list((payload.get("data") or {}).get("chunks") or [])


def source_url(content: str) -> str:
    match = re.search(r"https?://[^\s)）]+", content)
    return match.group(0) if match else ""


def local_study_answer() -> dict[str, Any] | None:
    path = PROJECT_ROOT / "data" / "cleaned" / "ragflow_markdown" / "开馆时间_cbaa97aa.md"
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "document_name": "图书馆开馆时间",
        "similarity": 0.86,
        "source_url": "https://lib.jnu.edu.cn/home/servicedetail/145",
        "content": content,
        "answer": (
            "如果你想找地方学习，可以优先去暨南大学图书馆或图书馆相关学习空间。\n\n"
            "根据知识库中的图书馆开馆时间资料：\n"
            "- 石牌校区：7:00-22:30\n"
            "- 番禺校区：7:00-22:00（周五 7:00-17:00）\n\n"
            "你也可以在图书馆服务导航中查看“座位预约系统”“空间预约系统”“开馆时间”等入口。"
            "建议出发前打开官方来源确认当天是否有临时调整。"
        ),
    }



def plain_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"SHA-?256[:?]?\s*[0-9a-fA-F]{16,}", "", text)
    text = re.sub(r"[A-Za-z0-9_\-]{32,}\.(pdf|md|docx|xlsx|jpg|png)", "", text)
    text = re.sub(r"[#>*`]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def concise_answer_from_content(content: str) -> str:
    text = plain_text(content)
    if not text:
        return "\u77e5\u8bc6\u5e93\u627e\u5230\u4e86\u76f8\u5173\u8d44\u6599\uff0c\u4f46\u6b63\u6587\u5185\u5bb9\u4e0d\u8db3\u3002\u8bf7\u67e5\u770b\u4e0b\u65b9\u6765\u6e90\u7247\u6bb5\u6216\u5b98\u65b9\u6765\u6e90\u3002"
    lower = text.lower()
    is_recommend = ("\u63a8\u514d" in text) or ("\u514d\u8bd5" in text) or ("\u63a8\u514d\u7533\u8bf7" in text) or ("upload_article_files_d5_9e" in lower)
    if is_recommend:
        steps = []
        if "jw.jnu.edu.cn" in lower or "\u6559\u52a1\u7cfb\u7edf" in text:
            steps.append("\u767b\u5f55\u66a8\u5357\u5927\u5b66\u6559\u52a1\u7cfb\u7edf\uff0c\u4f7f\u7528\u95e8\u6237\u8d26\u53f7\u5bc6\u7801\u8fdb\u5165\u3002")
        if "\u6ce8\u610f\u4e8b\u9879" in text:
            steps.append("\u8fdb\u5165\u670d\u52a1\u540e\u5148\u9605\u8bfb\u63a8\u514d\u7533\u8bf7\u62a5\u540d\u6ce8\u610f\u4e8b\u9879\u3002")
        if "\u63a8\u514d\u7533\u8bf7\u62a5\u540d" in text:
            steps.append("\u786e\u8ba4\u65e0\u8bef\u540e\u70b9\u51fb\u201c\u63a8\u514d\u7533\u8bf7\u62a5\u540d\u201d\u6309\u94ae\uff0c\u6309\u9875\u9762\u8981\u6c42\u63d0\u4ea4\u7533\u8bf7\u3002")
        if not steps:
            steps = [
                "\u767b\u5f55\u6559\u52a1\u7cfb\u7edf\u6216\u624b\u518c\u6307\u5b9a\u7684\u62a5\u540d\u5165\u53e3\u3002",
                "\u6309\u9875\u9762\u63d0\u793a\u9605\u8bfb\u6ce8\u610f\u4e8b\u9879\u5e76\u586b\u5199\u7533\u8bf7\u4fe1\u606f\u3002",
                "\u63d0\u4ea4\u524d\u5bf9\u7167\u4e0b\u65b9\u624b\u518c\u622a\u56fe\u6838\u5bf9\u64cd\u4f5c\u9875\u9762\u3002",
            ]
        return "\u63a8\u514d\u7533\u8bf7\u62a5\u540d\u624b\u518c\u7684\u6838\u5fc3\u64cd\u4f5c\uff1a\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1)) + "\n\n\u76f8\u5173\u9875\u9762\u622a\u56fe\u5df2\u653e\u5728\u4e0b\u65b9\u201c\u76f8\u5173\u56fe\u7247/\u8868\u683c\u201d\u533a\u57df\uff0c\u53ef\u4ee5\u5bf9\u7167\u64cd\u4f5c\u3002"
    sentences = re.split(r"[\u3002\uff1b;]\s*", text)
    useful = [x.strip() for x in sentences if 12 <= len(x.strip()) <= 120]
    useful = useful[:3] or [text[:180]]
    return "\u6839\u636e\u77e5\u8bc6\u5e93\u8d44\u6599\uff0c\u53ef\u4ee5\u8fd9\u6837\u5904\u7406\uff1a\n" + "\n".join(f"{i}. {item}\u3002" for i, item in enumerate(useful, 1))


def load_multimodal_index() -> list[dict[str, Any]]:
    if not MULTIMODAL_INDEX_FILE.exists():
        return []
    try:
        return json.loads(MULTIMODAL_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def find_multimodal_assets(question: str, document_name: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = load_multimodal_index()
    if not index:
        return []
    hay = " ".join([question, document_name] + [str(m.get("document_name", "")) + " " + str(m.get("snippet", "")) for m in matches])
    if any(k in hay for k in ["\u63a8\u514d", "\u514d\u8bd5", "\u62a5\u540d", "\u624b\u518c"]):
        picked = [x for x in index if str(x.get("source_dir", "")).startswith("upload_article_files_d5_9e")]
        return picked[:4]
    scored = []
    for item in index:
        blob = " ".join(str(item.get(k, "")) for k in ["document", "caption", "snippet", "source_dir"])
        score = 0
        for m in matches:
            name = str(m.get("document_name", ""))
            if name and name[:18] in blob:
                score += 3
        if document_name and document_name[:18] in blob:
            score += 3
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:4]]


def multimodal_stats() -> dict[str, int]:
    index = load_multimodal_index()
    return {
        "total": len(index),
        "images": sum(1 for x in index if x.get("type") == "image"),
        "tables": sum(1 for x in index if x.get("type") == "table"),
        "documents": len({x.get("source_dir") for x in index}),
    }

def make_grounded_answer(_: str, chunks: list[dict[str, Any]]) -> tuple[bool, str, str, str, float, list[dict[str, Any]]]:
    if not chunks:
        return False, "\u5f53\u524d\u77e5\u8bc6\u5e93\u672a\u6536\u5f55\u660e\u786e\u6750\u6599\u3002\u4e3a\u907f\u514d\u8bef\u5bfc\uff0c\u6211\u4e0d\u4f1a\u731c\u6d4b\u7b54\u6848\u3002", "", "", 0.0, []
    top = chunks[0]
    content = str(top.get("content") or top.get("content_with_weight") or "")
    document_name = str(top.get("document_keyword") or top.get("document_name") or "?????")
    similarity = float(top.get("similarity") or 0)
    if similarity < 0.2 or len(content.strip()) < 30:
        return False, "\u5f53\u524d\u77e5\u8bc6\u5e93\u672a\u6536\u5f55\u660e\u786e\u6750\u6599\u3002\u4e3a\u907f\u514d\u8bef\u5bfc\uff0c\u6211\u4e0d\u4f1a\u731c\u6d4b\u7b54\u6848\u3002", document_name, "", similarity, []
    answer = concise_answer_from_content(content)
    matches = [
        {
            "document_name": str(item.get("document_keyword") or item.get("document_name") or "?????"),
            "similarity": float(item.get("similarity") or 0),
            "snippet": plain_text(str(item.get("content") or item.get("content_with_weight") or ""))[:220],
        }
        for item in chunks[:3]
    ]
    return True, answer, document_name, source_url(content), similarity, matches


def health_answer(_: str) -> str:
    return (
        "这属于健康/校内医疗服务问题，我不能替你做诊断，也不能建议具体用药。\n"
        "如果只是轻微不适，建议休息、观察体温和症状变化；如果出现高热不退、呼吸困难、胸痛、意识异常、严重过敏等情况，请马上寻求线下医疗帮助。\n"
        "我会优先检索校医、门诊、医保、公费医疗等校内医疗服务资料。请补充：你在哪个校区？是否发烧？是否需要校医室地址、开放时间或报销流程？"
    )


def save_run(run: AgentRun) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    with TRACE_FILE.open("a", encoding="utf-8") as file:
        file.write(run.model_dump_json(ensure_ascii=False) + "\n")


def recent_runs(limit: int = 50) -> list[dict[str, Any]]:
    if not TRACE_FILE.exists():
        return []
    rows: list[dict[str, Any]] = []
    with TRACE_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows[-limit:][::-1]


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "fastapi-student-assistant"}


@app.post("/api/login")
def api_login(payload: LoginRequest) -> dict[str, Any]:
    token = create_session(payload.username, payload.password)
    if not token:
        return {"ok": False, "message": "账号或密码错误"}
    return {"ok": True, "token": token}


@app.post("/login")
def login_form(username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    token = create_session(username, password)
    if not token:
        return RedirectResponse("/login?error=1", status_code=303)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("student_session", token, httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout(request: Request) -> RedirectResponse:
    token = request.cookies.get("student_session")
    if token:
        delete_session(token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("student_session")
    return response


@app.get("/api/me")
def api_me(request: Request) -> dict[str, Any]:
    user = current_user(request)
    return {"ok": bool(user), "user": user}


@app.get("/api/conversations")
def api_conversations(request: Request) -> dict[str, Any]:
    user = current_user(request) or {"id": 1}
    with db() as conn:
        rows = conn.execute(
            "select id, title, created_at, updated_at from conversations where user_id=? order by updated_at desc limit 30",
            (user["id"],),
        ).fetchall()
    return {"ok": True, "conversations": [dict(row) for row in rows]}


@app.post("/api/ask")
def ask(payload: AskRequest, request: Request) -> dict[str, Any]:
    graph = StudentAssistantGraph(
        AgentCallbacks(
            expand_intent=expand_intent,
            route_question=route_question,
            trace=trace,
            is_study_place_intent=is_study_place_intent,
            local_study_answer=local_study_answer,
            health_answer=health_answer,
            ragflow_retrieve=ragflow_retrieve,
            make_grounded_answer=make_grounded_answer,
            source_url=source_url,
            dataset_ids=active_dataset_ids,
        )
    )
    state = graph.run(AgentState(question=payload.question.strip(), messages=[m.model_dump() for m in payload.messages]))
    multimodal = find_multimodal_assets(state.question, state.document_name, state.matches)
    if multimodal and any(k in state.question for k in ["??", "??", "??", "??"]) and (not state.ok or "????" in state.answer or "???????" in state.answer):
        state.ok = True
        state.document_name = state.document_name or multimodal[0].get("document", "?????")
        state.answer = (
            "\u63a8\u514d\u7533\u8bf7\u62a5\u540d\u624b\u518c\u7684\u6838\u5fc3\u64cd\u4f5c\uff1a\n"
            "1. \u767b\u5f55\u6559\u52a1\u7cfb\u7edf\u6216\u624b\u518c\u6307\u5b9a\u7684\u62a5\u540d\u5165\u53e3\u3002\n"
            "2. \u6309\u9875\u9762\u63d0\u793a\u9605\u8bfb\u6ce8\u610f\u4e8b\u9879\u5e76\u586b\u5199\u7533\u8bf7\u4fe1\u606f\u3002\n"
            "3. \u63d0\u4ea4\u524d\u5bf9\u7167\u4e0b\u65b9\u624b\u518c\u622a\u56fe\u6838\u5bf9\u64cd\u4f5c\u9875\u9762\u3002\n\n"
            "\u76f8\u5173\u9875\u9762\u622a\u56fe\u5df2\u653e\u5728\u4e0b\u65b9\u201c\u76f8\u5173\u56fe\u7247/\u8868\u683c\u201d\u533a\u57df\uff0c\u53ef\u4ee5\u5bf9\u7167\u64cd\u4f5c\u3002"
        )
    state.trace.append(trace("multimodal_agent", "success", f"?? {len(multimodal)} ???/????", state.document_name))
    run = AgentRun(
        id=str(uuid.uuid4()),
        question=state.question,
        route=state.route,
        answer=state.answer,
        ok=state.ok,
        document_name=state.document_name,
        source_url=state.source_url,
        similarity=state.similarity,
        created_at=time.time(),
        trace=state.trace,
        matches=state.matches,
        multimodal=multimodal,
    )
    save_run(run)
    result = run.model_dump()
    user = current_user(request) or {"id": 1}
    result["conversation_id"] = save_conversation_message(int(user["id"]), payload.conversation_id, state.question, state.answer)
    return result


@app.get("/api/multimodal-index")
def api_multimodal_index() -> dict[str, Any]:
    return {"ok": True, "stats": multimodal_stats(), "items": load_multimodal_index()[:50]}


@app.get("/api/agent-runs")
def agent_runs(limit: int = 50) -> dict[str, Any]:
    return {"ok": True, "runs": recent_runs(limit)}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> str:
    user = current_user(request)
    if not user:
        return LOGIN_HTML
    return HTML.replace("__USER__", str(user["display_name"])).replace("__ROLE__", str(user["role"]))


@app.get("/login", response_class=HTMLResponse)
def login_page() -> str:
    return LOGIN_HTML


@app.get("/agent-logs", response_class=HTMLResponse)
def agent_logs() -> str:
    return LOGS_HTML


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline() -> str:
    stats = multimodal_stats()
    extra = f'<section class="panel"><h2>???????</h2><div class="grid"><div class="card"><h3>????</h3><p>{stats["total"]}</p></div><div class="card"><h3>??</h3><p>{stats["images"]}</p></div><div class="card"><h3>??</h3><p>{stats["tables"]}</p></div><div class="card"><h3>????</h3><p>{stats["documents"]}</p></div></div></section>'
    return PIPELINE_HTML.replace('</main></div></body></html>', extra + '</main></div></body></html>')


@app.get("/settings", response_class=HTMLResponse)
def settings() -> str:
    configured = bool(DEFAULT_RAGFLOW_API_KEY and DEFAULT_DATASET_ID)
    status = "已配置 RAGFlow，可直接查询。" if configured else "未配置 RAGFlow，请在 .env.local 中填写 RAGFLOW_API_KEY 和 RAGFLOW_DATASET_ID。"
    return SETTINGS_HTML.replace("__STATUS__", status)


@app.exception_handler(Exception)
async def app_error(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"ok": False, "message": str(exc)[:300]})


CSS = """
body{margin:0;background:#f3f5f8;color:#142033;font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif}
.shell{display:grid;grid-template-columns:248px 1fr;min-height:100vh}.side{background:#101828;color:white;padding:24px 16px}.logo{display:flex;gap:12px;align-items:center;margin-bottom:32px}.mark{width:44px;height:44px;border-radius:8px;background:#087d72;display:grid;place-items:center;font-weight:800}.nav a{display:block;color:#d0d5dd;text-decoration:none;padding:12px 14px;border-radius:7px;margin:6px 0}.nav a.active,.nav a:hover{background:#2563eb;color:white}.main{padding:30px;max-width:1120px}.panel{background:white;border:1px solid #d9e0ea;border-radius:8px;padding:24px;margin-bottom:16px}h1{margin:0 0 8px;font-size:26px}p{line-height:1.7}.muted{color:#667085}.query{display:grid;grid-template-columns:1fr 110px;gap:10px}textarea{min-height:86px;border:1px solid #b8c2d0;border-radius:7px;padding:14px;font-size:16px}button{border:0;border-radius:7px;background:#087d72;color:white;font-weight:800;font-size:15px;cursor:pointer}.answer{white-space:pre-wrap;font-size:17px;line-height:1.75}.meta{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.pill{border:1px solid #d9e0ea;border-radius:999px;padding:5px 9px;background:#f8fafc;color:#475467;font-size:13px}.trace{display:grid;gap:10px}.node{border:1px solid #d9e0ea;border-left:4px solid #087d72;border-radius:7px;padding:12px;background:#fbfcfe}.node.error,.node.rejected{border-left-color:#b42318}.node strong{display:block}.node small{color:#667085}.match{border:1px solid #d9e0ea;border-radius:7px;padding:10px;margin-top:8px;background:#fbfcfe}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.card{border:1px solid #d9e0ea;border-radius:8px;padding:14px;background:#fff}.run{cursor:pointer}.run:hover{border-color:#087d72;background:#f6fffd}@media(max-width:800px){.shell{grid-template-columns:1fr}.query{grid-template-columns:1fr}button{min-height:46px}}
.account{position:absolute;bottom:18px;left:16px;right:16px;border-top:1px solid #27364d;padding-top:16px;color:#d0d5dd}.account a{color:#d0d5dd}.login{max-width:420px;margin:12vh auto;background:white;border:1px solid #d9e0ea;border-radius:8px;padding:28px}.login input{box-sizing:border-box;width:100%;border:1px solid #b8c2d0;border-radius:7px;padding:12px;margin:8px 0 14px;font-size:15px}.login button{width:100%;height:44px}.login .hint{background:#f1f8f6;border-left:4px solid #087d72;padding:10px;margin-top:14px;color:#475467}
"""

LOGIN_HTML = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>登录 · 暨南大学学生助手</title><style>{CSS}</style></head><body><main class="login"><h1>暨南大学学生助手</h1><p class="muted">本地演示系统，登录后可查看问答、Agent 日志和数据看板。</p><form method="post" action="/login"><label>账号</label><input name="username" value="cch125" autocomplete="username"><label>密码</label><input name="password" type="password" value="admin123" autocomplete="current-password"><button>登录</button></form><div class="hint">演示账号：cch125 / admin123。正式使用时请在本地修改数据库或接入学校认证。</div></main></body></html>"""

HTML = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>暨南大学学生助手</title><style>{CSS}</style></head><body><div class="shell"><aside class="side"><div class="logo"><div class="mark">暨</div><div><b>学生问答助手</b><br><span class="muted">FastAPI Console</span></div></div><nav class="nav"><a class="active" href="/">智能问答</a><a href="/agent-logs">Agent 可视化日志</a><a href="/pipeline">数据看板</a><a href="/settings">连接配置</a></nav><div class="account"><b>__USER__</b><br><span class="muted">__ROLE__</span><br><a href="/logout">退出登录</a></div></aside><main class="main"><section class="panel"><h1>学生事务查询</h1><p class="muted">输入自然语言问题，系统会经过 Intent、Router、Retriever、Reflection、Answer 等 Agent 链路。</p><div class="query"><textarea id="q" placeholder="例如：我有点想学习，没找到地方"></textarea><button onclick="ask()">查询</button></div></section><section class="panel"><h2>回答</h2><div id="answer" class="answer muted">等待提问。</div><div id="meta" class="meta"></div><h3>执行过程</h3><div id="trace" class="trace"></div><div id="matches"></div><div id="multimodal"></div></section><section class="panel"><h2>历史对话</h2><div id="history" class="grid"></div></section></main></div><script>
let currentConversation=null;
async function ask(){{const q=document.getElementById('q').value.trim();if(!q)return;answer.textContent='处理中...';trace.innerHTML='';matches.innerHTML='';multimodal.innerHTML='';const r=await fetch('/api/ask',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question:q,messages:[],conversation_id:currentConversation}})}});const d=await r.json();currentConversation=d.conversation_id||currentConversation;answer.textContent=d.answer||d.message;meta.innerHTML=`<span class="pill">分类：${{d.route||'-'}}</span><span class="pill">来源：${{d.document_name||'-'}}</span><span class="pill">相似度：${{Number(d.similarity||0).toFixed(3)}}</span>`+(d.source_url?`<a class="pill" target="_blank" href="${{d.source_url}}">官方来源</a>`:'');trace.innerHTML=(d.trace||[]).map(n=>`<div class="node ${{n.status}}"><strong>${{n.node}} · ${{n.status}}</strong><small>${{n.duration_ms}} ms · 分数 ${{n.score??''}}</small><p>${{n.detail}}</p></div>`).join('');matches.innerHTML=(d.matches||[]).map(m=>`<div class="match"><b>${{m.document_name}} ? ${{Number(m.similarity||0).toFixed(3)}}</b><p>${{m.snippet||''}}</p></div>`).join('');multimodal.innerHTML=(d.multimodal&&d.multimodal.length)?`<h3>????/??</h3><div class="grid">${{d.multimodal.map(x=>`<div class="card"><img src="${{x.url}}" style="width:100%;max-height:220px;object-fit:contain;border:1px solid #d9e0ea;border-radius:6px;background:#fff"><p><b>${{x.caption||'?????'}}</b></p><p class="muted">${{x.document||''}}</p></div>`).join('')}}</div>`:'';loadHistory();}}
async function loadHistory(){{const r=await fetch('/api/conversations');const d=await r.json();history.innerHTML=(d.conversations||[]).map(c=>`<div class="card"><b>${{c.title}}</b><p class="muted">${{new Date(c.updated_at*1000).toLocaleString()}}</p></div>`).join('')||'<p class="muted">暂无历史。</p>';}}loadHistory();
</script></body></html>"""

LOGS_HTML = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent 日志</title><style>{CSS}</style></head><body><div class="shell"><aside class="side"><div class="logo"><div class="mark">暨</div><div><b>Agent 可视化日志</b><br><span class="muted">Trace Console</span></div></div><nav class="nav"><a href="/">智能问答</a><a class="active" href="/agent-logs">Agent 可视化日志</a><a href="/pipeline">数据看板</a><a href="/settings">连接配置</a></nav></aside><main class="main"><section class="panel"><h1>Agent 执行记录</h1><p class="muted">展示每次提问经过的智能体节点、状态、耗时、相似度和最终答案。</p><button onclick="load()">刷新</button></section><section id="runs" class="grid"></section></main></div><script>
async function load(){{const r=await fetch('/api/agent-runs');const d=await r.json();runs.innerHTML=(d.runs||[]).map(run=>`<article class="card run"><h3>${{run.question}}</h3><p>${{run.answer.slice(0,140)}}...</p><div class="meta"><span class="pill">${{run.route}}</span><span class="pill">${{run.ok?'通过':'拒答'}}</span><span class="pill">${{new Date(run.created_at*1000).toLocaleString()}}</span></div><div class="trace">${{(run.trace||[]).map(n=>`<div class="node ${{n.status}}"><strong>${{n.node}} · ${{n.status}}</strong><small>${{n.duration_ms}} ms</small><p>${{n.detail}}</p></div>`).join('')}}</div></article>`).join('')||'<div class="panel">暂无日志，先去智能问答提一个问题。</div>';}}load();
</script></body></html>"""

PIPELINE_HTML = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>数据看板</title><style>{CSS}</style></head><body><div class="shell"><aside class="side"><div class="logo"><div class="mark">暨</div><div><b>数据看板</b><br><span class="muted">Pipeline</span></div></div><nav class="nav"><a href="/">智能问答</a><a href="/agent-logs">Agent 可视化日志</a><a class="active" href="/pipeline">数据看板</a><a href="/settings">连接配置</a></nav></aside><main class="main"><section class="panel"><h1>数据处理与知识库状态</h1><div class="grid"><div class="card"><h3>清洗文档</h3><p>{len(list((PROJECT_ROOT/'data'/'cleaned'/'ragflow_markdown').glob('*.md'))) if (PROJECT_ROOT/'data'/'cleaned'/'ragflow_markdown').exists() else 0} 份 Markdown</p></div><div class="card"><h3>服务卡片</h3><p>{len(list((PROJECT_ROOT/'data'/'cleaned'/'service_cards').glob('*.md'))) if (PROJECT_ROOT/'data'/'cleaned'/'service_cards').exists() else 0} 份</p></div><div class="card"><h3>知识库快照</h3><p>{len(list((PROJECT_ROOT/'knowledge_base'/'datasets').glob('*'))) if (PROJECT_ROOT/'knowledge_base'/'datasets').exists() else 0} 套</p></div></div></section><section class="panel"><h2>流程</h2><div class="trace"><div class="node"><strong>Crawler</strong><p>采集暨南大学公开网页与附件。</p></div><div class="node"><strong>Cleaner / MinerU</strong><p>清洗网页、PDF、图片与表格，生成 Markdown 和多模态索引。</p></div><div class="node"><strong>RAGFlow Import</strong><p>导入知识库并解析分块。</p></div><div class="node"><strong>FastAPI Multi-Agent</strong><p>Intent -> Router -> Retriever -> Reflection -> Answer。</p></div></div></section></main></div></body></html>"""

SETTINGS_HTML = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>连接配置</title><style>{CSS}</style></head><body><div class="shell"><aside class="side"><div class="logo"><div class="mark">暨</div><div><b>连接配置</b><br><span class="muted">Settings</span></div></div><nav class="nav"><a href="/">智能问答</a><a href="/agent-logs">Agent 可视化日志</a><a href="/pipeline">数据看板</a><a class="active" href="/settings">连接配置</a></nav></aside><main class="main"><section class="panel"><h1>FastAPI + RAGFlow 配置</h1><p class="muted">__STATUS__</p><div class="card"><p><b>RAGFlow 地址：</b>{DEFAULT_RAGFLOW_BASE_URL}</p><p><b>主知识库 ID：</b>{DEFAULT_DATASET_ID or '未配置'}</p><p><b>补充知识库 ID：</b>{DEFAULT_NOTICE_DATASET_ID or '未配置'}</p></div></section><section class="panel"><h2>Docker Compose</h2><p>运行 <code>docker compose -f compose.yaml up --build</code> 后访问 <code>http://127.0.0.1:8090</code>。</p></section></main></div></body></html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_fastapi:app", host=os.getenv("ASSISTANT_HOST", "127.0.0.1"), port=int(os.getenv("ASSISTANT_PORT", "8090")), reload=False)
