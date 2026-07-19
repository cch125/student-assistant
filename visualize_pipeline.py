from __future__ import annotations

import html
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
RAW_MANIFEST = PROJECT_ROOT / "data" / "raw" / "manifest.jsonl"
CLEANED_DOCS = PROJECT_ROOT / "data" / "cleaned" / "documents.jsonl"
RAGFLOW_MARKDOWN_DIR = PROJECT_ROOT / "data" / "cleaned" / "ragflow_markdown"
SERVICE_CARD_DIR = PROJECT_ROOT / "data" / "cleaned" / "service_cards"
OUTPUT_HTML = PROJECT_ROOT / "outputs" / "pipeline_dashboard.html"
UNANSWERED_LOG = PROJECT_ROOT / "data" / "feedback" / "unanswered_questions.jsonl"
RAGFLOW_KB_NAMES = ["暨南大学学生助手-第一阶段", "暨南大学学生助手-核心服务卡片"]

MOJIBAKE_MARKERS = [
    "å",
    "æ",
    "ç",
    "è",
    "é",
    "ã€",
    "ã",
    "Â",
    "ï¼",
    "â€”",
    "â€œ",
    "â€",
    "¤",
    "œ",
]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"_parse_error": line[:200]})
    return rows


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def task_status(value: object) -> str:
    return {
        "0": "未开始",
        "1": "处理中",
        "2": "已取消",
        "3": "完成",
        "4": "失败",
        "5": "已计划",
    }.get(str(value).upper(), str(value))


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def parse_service_card(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")

    def field(name: str) -> str:
        match = re.search(rf"^{re.escape(name)}：(.+)$", text, flags=re.M)
        return match.group(1).strip() if match else ""

    title_match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    return {
        "file": path.name,
        "path": rel(path),
        "title": title_match.group(1).strip() if title_match else path.stem,
        "category": field("类别"),
        "service_type": field("事项类型"),
        "department": field("负责部门"),
        "audience": field("适用对象"),
        "entrance": field("办理入口"),
        "materials": field("所需材料"),
        "answer": field("直接回答"),
        "source_url": field("来源链接"),
        "keywords": field("关键词"),
        "length": len(text),
    }


def text_quality(text: str) -> dict:
    length = max(len(text), 1)
    bad = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    replacement_chars = text.count("�")
    return {
        "length": len(text),
        "mojibake_hits": bad + replacement_chars,
        "mojibake_rate": (bad + replacement_chars) / length,
    }


def load_ragflow_status() -> list[dict]:
    script = r"""
import os, pymysql, json
names = ["暨南大学学生助手-第一阶段", "暨南大学学生助手-核心服务卡片"]
conn = pymysql.connect(
    host=os.getenv('MYSQL_HOST'),
    port=int(os.getenv('MYSQL_PORT', '3306')),
    user='root',
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DBNAME'),
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
)
cur = conn.cursor()
items = []
for name in names:
    cur.execute("select id,name,doc_num,token_num,chunk_num,status from knowledgebase where name=%s", (name,))
    kb = cur.fetchone()
    if not kb:
        continue
    cur.execute(
        "select id,name,run,progress,progress_msg,chunk_num,token_num,suffix from document where kb_id=%s order by create_time desc",
        (kb["id"],),
    )
    kb["documents"] = cur.fetchall()
    items.append(kb)
print(json.dumps(items, ensure_ascii=False))
"""
    temp_path = Path(tempfile.gettempdir()) / "ragflow_status_for_dashboard.py"
    temp_path.write_text(script, encoding="utf-8")
    try:
        subprocess.run(
            ["docker", "cp", str(temp_path), "docker-ragflow-cpu-1:/tmp/ragflow_status_for_dashboard.py"],
            check=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            ["docker", "exec", "docker-ragflow-cpu-1", "python", "/tmp/ragflow_status_for_dashboard.py"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return json.loads(result.stdout.strip() or "[]")
    except Exception as exc:
        return [{"error": str(exc)}]


def build_dashboard() -> str:
    project_version = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "dev"
    raw_rows = read_jsonl(RAW_MANIFEST)
    cleaned_rows = read_jsonl(CLEANED_DOCS)
    markdown_files = sorted(RAGFLOW_MARKDOWN_DIR.glob("*.md")) if RAGFLOW_MARKDOWN_DIR.exists() else []
    service_cards = [parse_service_card(path) for path in sorted(SERVICE_CARD_DIR.glob("*.md"))] if SERVICE_CARD_DIR.exists() else []
    ragflow_status = load_ragflow_status()
    unanswered_rows = read_jsonl(UNANSWERED_LOG)

    raw_pages = [row for row in raw_rows if row.get("kind") == "page"]
    raw_attachments = [row for row in raw_rows if row.get("kind") == "attachment"]
    departments = Counter(row.get("department") or "未标注" for row in cleaned_rows)
    category_counter: Counter[str] = Counter()
    for row in cleaned_rows:
        for category in row.get("categories") or []:
            category_counter[category] += 1

    cleaned_quality = []
    for row in cleaned_rows:
        quality = text_quality(row.get("text", ""))
        cleaned_quality.append({**row, **quality})
    quality_issues = [row for row in cleaned_quality if row["mojibake_hits"] > 0]

    step_cards = [
        ("1", "公开网页采集", len(raw_pages), "保存学校官网 HTML 原文和来源元数据"),
        ("2", "附件下载", len(raw_attachments), "保存 PDF、Word、Excel 等公开附件"),
        ("3", "清洗结构化文档", len(cleaned_rows), "抽取标题、部门、日期、类别、正文、来源"),
        ("4", "RAGFlow Markdown", len(markdown_files), "转成可导入知识库的 Markdown"),
        ("5", "核心服务卡片", len(service_cards), "整理为稳定问答使用的高频事项卡片"),
        ("6", "质量问题提示", len(quality_issues), "标记疑似乱码或需要人工复核的清洗结果"),
    ]

    service_rows = "\n".join(
        f"""
        <tr>
          <td><a href="../{esc(card['path'])}" target="_blank">{esc(card['title'])}</a></td>
          <td>{esc(card['category'])}</td>
          <td>{esc(card['service_type'])}</td>
          <td>{esc(card['department'])}</td>
          <td>{esc(card['entrance'])}</td>
          <td>{esc(card['materials'])}</td>
          <td>{esc(card['answer'])}</td>
          <td><a href="{esc(card['source_url'])}" target="_blank">{esc(card['source_url'])}</a></td>
        </tr>
        """
        for card in service_cards
    )

    cleaned_rows_html = "\n".join(
        f"""
        <tr>
          <td>{esc(row.get('title'))}</td>
          <td>{esc(row.get('department'))}</td>
          <td>{esc(row.get('category_hint'))}</td>
          <td>{esc(', '.join(row.get('categories') or []))}</td>
          <td>{esc(row.get('date'))}</td>
          <td><a href="{esc(row.get('source_url'))}" target="_blank">来源</a></td>
          <td>{row['length']}</td>
          <td class="{ 'warn' if row['mojibake_hits'] else 'ok' }">{row['mojibake_hits']}</td>
        </tr>
        """
        for row in cleaned_quality[:80]
    )

    raw_rows_html = "\n".join(
        f"""
        <tr>
          <td>{esc(row.get('seed_name') or row.get('title'))}</td>
          <td>{esc(row.get('department'))}</td>
          <td>{esc(row.get('category_hint'))}</td>
          <td>{esc(row.get('depth'))}</td>
          <td><a href="{esc(row.get('url'))}" target="_blank">{esc(row.get('url'))}</a></td>
          <td>{esc(row.get('local_path'))}</td>
        </tr>
        """
        for row in raw_pages[:80]
    )

    department_items = "\n".join(
        f"<div class=\"bar\"><span>{esc(name)}</span><strong style=\"width:{max(8, count * 18)}px\">{count}</strong></div>"
        for name, count in departments.most_common()
    )
    category_items = "\n".join(
        f"<div class=\"bar accent\"><span>{esc(name)}</span><strong style=\"width:{max(8, count * 18)}px\">{count}</strong></div>"
        for name, count in category_counter.most_common()
    )
    steps_html = "\n".join(
        f"""
        <article class="step">
          <div class="num">{esc(num)}</div>
          <h3>{esc(title)}</h3>
          <b>{count}</b>
          <p>{esc(desc)}</p>
        </article>
        """
        for num, title, count, desc in step_cards
    )

    worst_quality_html = "\n".join(
        f"""
        <li>
          <strong>{esc(row.get('title'))}</strong>
          <span>{esc(row.get('source_url'))}</span>
          <em>疑似乱码命中 {row['mojibake_hits']} 次</em>
        </li>
        """
        for row in sorted(quality_issues, key=lambda item: item["mojibake_hits"], reverse=True)[:8]
    ) or "<li><strong>未发现明显乱码</strong><span>当前清洗文本质量正常</span></li>"

    ragflow_cards = []
    ragflow_doc_rows = []
    for kb in ragflow_status:
        if kb.get("error"):
            ragflow_cards.append(
                f"""
                <article class="ragflow-card error-card">
                  <h3>RAGFlow 状态读取失败</h3>
                  <p>{esc(kb['error'])}</p>
                </article>
                """
            )
            continue
        documents = kb.get("documents", [])
        completed = sum(1 for doc in documents if task_status(doc.get("run")) == "完成")
        failed = sum(1 for doc in documents if task_status(doc.get("run")) == "失败")
        processing = max(len(documents) - completed - failed, 0)
        files_url = f"http://localhost:8080/dataset/files/{kb['id']}"
        logs_url = f"http://localhost:8080/dataset/logs/{kb['id']}"
        ragflow_cards.append(
            f"""
            <article class="ragflow-card">
              <h3>{esc(kb['name'])}</h3>
              <div class="metric-row"><span>知识库 ID</span><code>{esc(kb['id'])}</code></div>
              <div class="metric-grid">
                <b>{esc(kb['doc_num'])}<small>文档</small></b>
                <b>{esc(kb['chunk_num'])}<small>分块</small></b>
                <b>{esc(kb['token_num'])}<small>Token</small></b>
              </div>
              <div class="parse-summary">
                <span class="done">成功 {completed}</span>
                <span>处理中 {processing}</span>
                <span class="failed">失败 {failed}</span>
              </div>
              <div class="link-row">
                <a href="{files_url}" target="_blank">打开 RAGFlow 文件列表</a>
                <a href="{logs_url}" target="_blank">打开 RAGFlow 日志</a>
              </div>
            </article>
            """
        )
        for doc in kb.get("documents", [])[:80]:
            run_status = task_status(doc.get("run"))
            ragflow_doc_rows.append(
                f"""
                <tr>
                  <td>{esc(kb['name'])}</td>
                  <td>{esc(doc.get('name'))}</td>
                  <td class="{ 'ok' if run_status == '完成' else 'warn' }">{esc(run_status)}</td>
                  <td>{esc(doc.get('progress'))}</td>
                  <td>{esc(doc.get('chunk_num'))}</td>
                  <td>{esc(doc.get('token_num'))}</td>
                  <td>{esc(doc.get('suffix'))}</td>
                </tr>
                """
            )

    ragflow_cards_html = "\n".join(ragflow_cards) or "<p class=\"note\">未读取到 RAGFlow 知识库状态。</p>"
    ragflow_doc_rows_html = "\n".join(ragflow_doc_rows)
    unanswered_html = "\n".join(
        f"""
        <tr>
          <td>{esc(row.get('time'))}</td>
          <td>{esc(row.get('question'))}</td>
          <td>{esc(row.get('reason'))}</td>
          <td>{esc((row.get('top_matches') or [{}])[0].get('document_name', ''))}</td>
          <td>{esc((row.get('top_matches') or [{}])[0].get('similarity', ''))}</td>
        </tr>
        """
        for row in unanswered_rows[-50:]
    ) or "<tr><td colspan=\"5\">暂无未收录问题</td></tr>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>暨南大学学生助手 · 数据流程可视化</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --panel: #ffffff;
      --text: #182230;
      --muted: #667085;
      --line: #d6dde7;
      --brand: #0f6f64;
      --brand-2: #245b9b;
      --warn: #b54708;
      --ok: #067647;
      --shadow: 0 12px 32px rgba(16, 24, 40, .09);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 22px 28px;
    }}
    header h1 {{ margin: 0 0 6px; font-size: 24px; }}
    header p {{ margin: 0; color: var(--muted); }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 24px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
      padding: 20px;
    }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    .steps {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
    }}
    .step {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 148px;
      background: #fbfcfe;
    }}
    .num {{
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: var(--brand);
      color: #fff;
      font-weight: 800;
    }}
    .step h3 {{ margin: 12px 0 6px; font-size: 15px; }}
    .step b {{ display: block; font-size: 28px; color: var(--brand); }}
    .step p {{ margin: 6px 0 0; color: var(--muted); font-size: 13px; line-height: 1.55; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .bar {{
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 10px;
      align-items: center;
      margin: 8px 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .bar strong {{
      display: inline-block;
      min-width: 34px;
      max-width: 100%;
      background: var(--brand);
      color: #fff;
      padding: 4px 8px;
      border-radius: 4px;
      text-align: right;
    }}
    .bar.accent strong {{ background: var(--brand-2); }}
    .scroll {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 920px; }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      line-height: 1.55;
    }}
    th {{ background: #f8fafc; color: #475467; position: sticky; top: 0; }}
    a {{ color: var(--brand-2); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .ok {{ color: var(--ok); font-weight: 700; }}
    .warn {{ color: var(--warn); font-weight: 700; }}
    .quality-list {{ margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }}
    .quality-list li {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .quality-list strong, .quality-list span, .quality-list em {{ display: block; }}
    .quality-list span {{ color: var(--muted); font-size: 13px; overflow-wrap: anywhere; margin-top: 4px; }}
    .quality-list em {{ color: var(--warn); font-style: normal; margin-top: 6px; font-size: 13px; }}
    .note {{ color: var(--muted); line-height: 1.7; margin: 0 0 14px; }}
    .ragflow-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .ragflow-card {{ border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: #fbfcfe; }}
    .ragflow-card h3 {{ margin: 0 0 12px; font-size: 16px; }}
    .metric-row {{ display: grid; gap: 4px; margin-bottom: 12px; color: var(--muted); font-size: 13px; }}
    .parse-summary {{ display: flex; gap: 12px; margin: 12px 0; color: var(--muted); font-size: 13px; }}
    .parse-summary .done {{ color: #087f5b; }}
    .parse-summary .failed {{ color: #c92a2a; }}
    code {{ font-family: Consolas, monospace; color: var(--text); overflow-wrap: anywhere; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px; }}
    .metric-grid b {{ background: #eef7f5; color: var(--brand); border-radius: 6px; padding: 10px; font-size: 24px; }}
    .metric-grid small {{ display: block; color: var(--muted); font-size: 12px; font-weight: 500; margin-top: 2px; }}
    .link-row {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .link-row a {{ border: 1px solid #bad7d2; border-radius: 6px; padding: 8px 10px; background: #fff; }}
    .error-card {{ border-color: #fecdca; background: #fff6f5; }}
    @media (max-width: 980px) {{
      main {{ padding: 14px; }}
      .steps, .grid, .ragflow-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>暨南大学学生助手 · 数据流程可视化</h1>
    <p>版本 v{esc(project_version)} · 从官网采集到 RAGFlow 服务卡片，每一步的输入、输出和质量检查都在这里。</p>
  </header>
  <main>
    <section>
      <h2>流程总览</h2>
      <div class="steps">{steps_html}</div>
    </section>

    <section class="grid">
      <div>
        <h2>清洗结果按部门分布</h2>
        {department_items}
      </div>
      <div>
        <h2>清洗结果按事项类别分布</h2>
        {category_items}
      </div>
    </section>

    <section>
      <h2>RAGFlow 导入状态</h2>
      <p class="note"><strong>知识库内容以这里的文档数、分块数和解析状态为准。</strong> RAGFlow 的“日志”页主要记录数据管道任务；本项目通过 API 直接上传和解析，因此日志页可能为空，这不表示知识库为空。不要打开 URL 里带 `undefined` 的页面，下面按钮会带真实知识库 ID。</p>
      <div class="ragflow-grid">{ragflow_cards_html}</div>
    </section>

    <section>
      <h2>RAGFlow 文档解析状态</h2>
      <div class="scroll">
        <table>
          <thead><tr><th>知识库</th><th>文档</th><th>解析状态</th><th>进度</th><th>分块</th><th>Token</th><th>类型</th></tr></thead>
          <tbody>{ragflow_doc_rows_html}</tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>未收录问题反馈</h2>
      <p class="note">当问题没有可靠命中时，系统会拒答并记录在这里，作为下一轮补充数据和服务卡片的依据。</p>
      <div class="scroll">
        <table>
          <thead><tr><th>时间</th><th>问题</th><th>拒答原因</th><th>最接近文档</th><th>相似度</th></tr></thead>
          <tbody>{unanswered_html}</tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>核心服务卡片</h2>
      <p class="note">这是当前问答网页优先使用的高质量数据层，链接和日期直接从卡片原文抽取，避免模型改错。</p>
      <div class="scroll">
        <table>
          <thead><tr><th>事项</th><th>类别</th><th>事项类型</th><th>负责部门</th><th>办理入口</th><th>所需材料</th><th>直接回答</th><th>来源链接</th></tr></thead>
          <tbody>{service_rows}</tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>清洗质量提示</h2>
      <p class="note">疑似乱码越多，越需要回到网页解析和编码识别步骤复核。第一阶段服务卡片已人工整理为干净中文，但通用清洗文本仍有进一步优化空间。</p>
      <ul class="quality-list">{worst_quality_html}</ul>
    </section>

    <section>
      <h2>清洗后的结构化文档</h2>
      <div class="scroll">
        <table>
          <thead><tr><th>标题</th><th>部门</th><th>栏目</th><th>自动类别</th><th>日期</th><th>来源</th><th>文本长度</th><th>乱码命中</th></tr></thead>
          <tbody>{cleaned_rows_html}</tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>原始采集页面</h2>
      <div class="scroll">
        <table>
          <thead><tr><th>种子/标题</th><th>部门</th><th>栏目</th><th>深度</th><th>来源 URL</th><th>本地 HTML</th></tr></thead>
          <tbody>{raw_rows_html}</tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>"""


def main() -> None:
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(build_dashboard(), encoding="utf-8")
    print(f"Dashboard written to: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
