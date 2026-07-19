from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "raw" / "manifest.jsonl"
CATEGORIES_PATH = ROOT / "config" / "categories.json"
CLEAN_DIR = ROOT / "data" / "cleaned"
MARKDOWN_DIR = CLEAN_DIR / "ragflow_markdown"
DOCUMENTS_PATH = CLEAN_DIR / "documents.jsonl"


def compact_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_html(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "form", "nav"]):
        tag.decompose()

    title = ""
    for selector in ["h1", "h2", "h3", ".title", "#title"]:
        tag = soup.select_one(selector)
        if tag and tag.get_text(strip=True):
            title = tag.get_text(" ", strip=True)
            break
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    raw_text = soup.get_text("\n", strip=True)
    date_match = re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)", raw_text)
    date = date_match.group(1) if date_match else ""
    return title, date, compact_text(raw_text)


def classify(title: str, text: str, category_hint: str, attachments: list[str], categories: dict[str, list[str]]) -> list[str]:
    attachment_names = "\n".join(Path(urlparse(url).path).name for url in attachments)
    core_hints = {"学籍表格", "办事指南", "新生表格", "学生事务"}
    body_sample = text[:1200] if category_hint in core_hints else ""
    haystack = f"{title}\n{attachment_names}\n{body_sample}"
    matches: list[str] = []
    for category, keywords in categories.items():
        if category == "其他":
            continue
        if any(keyword in haystack for keyword in keywords):
            matches.append(category)
    if not matches and category_hint in {"学籍表格", "办事指南", "新生表格", "学生事务"}:
        matches.append(category_hint)
    return matches or ["其他"]


def is_student_service_record(record: dict) -> bool:
    important_hints = {"学籍表格", "办事指南", "新生表格", "学生事务"}
    if record.get("category_hint") in important_hints:
        return True
    if any(category != "其他" for category in record.get("categories", [])):
        return True
    if record.get("attachments") and record.get("category_hint") in important_hints:
        return True
    return False


def slugify(text: str, fallback: str) -> str:
    text = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", text).strip("_")
    return (text[:70] or fallback).strip("_")


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")
    records = []
    for line in MANIFEST_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def write_markdown(record: dict) -> str:
    title = record["title"] or "未命名页面"
    parsed = urlparse(record["source_url"])
    digest = hashlib.sha1(record["source_url"].encode("utf-8")).hexdigest()[:8]
    filename = f"{slugify(title, parsed.netloc)}_{digest}.md"
    target = MARKDOWN_DIR / filename
    attachments = record.get("attachments", [])
    attachment_block = "\n".join(f"- {url}" for url in attachments) if attachments else "无"
    body = f"""# {title}

来源：{record["source_url"]}

部门：{record.get("department", "")}

日期：{record.get("date", "")}

分类：{", ".join(record.get("categories", []))}

## 附件

{attachment_block}

## 正文

{record["text"]}
"""
    target.write_text(body, encoding="utf-8")
    return str(target.relative_to(ROOT))


def main() -> None:
    categories = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in MARKDOWN_DIR.glob("*.md"):
        old_file.unlink()

    cleaned = []
    for item in load_manifest():
        if item.get("kind") != "page" or not item.get("local_path"):
            continue
        html_path = ROOT / item["local_path"]
        if not html_path.exists():
            continue
        title, date, text = clean_html(html_path.read_text(encoding="utf-8", errors="ignore"))
        if len(text) < 80:
            continue
        record = {
            "source_url": item["url"],
            "title": title or item.get("title", ""),
            "date": date,
            "department": item.get("department", ""),
            "category_hint": item.get("category_hint", ""),
            "categories": classify(title, text, item.get("category_hint", ""), item.get("attachments", []), categories),
            "attachments": item.get("attachments", []),
            "text": text,
        }
        if not is_student_service_record(record):
            continue
        record["ragflow_markdown_path"] = write_markdown(record)
        cleaned.append(record)

    with DOCUMENTS_PATH.open("w", encoding="utf-8") as output:
        for record in cleaned:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Cleaned {len(cleaned)} pages. Output: {DOCUMENTS_PATH}")


if __name__ == "__main__":
    main()
