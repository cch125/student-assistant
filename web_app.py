from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "ragflow"))

from core_services import ask_core_service
from visualize_pipeline import build_coverage_report, build_dashboard


HOST = "127.0.0.1"
PORT = 8090

HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>暨南大学学生助手</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d9e0ea;
      --brand: #0f6f64;
      --brand-dark: #09544b;
      --accent: #b42318;
      --soft: #ecfdf3;
      --shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .topbar {
      max-width: 980px;
      margin: 0 auto;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .mark {
      width: 38px;
      height: 38px;
      border-radius: 8px;
      background: var(--brand);
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 800;
      flex: 0 0 auto;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      font-weight: 700;
    }
    .status {
      font-size: 13px;
      color: var(--brand-dark);
      background: var(--soft);
      border: 1px solid #b7ebc6;
      padding: 7px 10px;
      border-radius: 999px;
      white-space: nowrap;
    }
    main {
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 24px 40px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 260px;
      gap: 16px;
    }
    .workspace, .side {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .workspace { padding: 22px; }
    .side { padding: 16px; align-self: start; }
    .label {
      display: block;
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 10px;
    }
    .ask-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 112px;
      gap: 10px;
      align-items: stretch;
    }
    input {
      width: 100%;
      border: 1px solid #b8c2d0;
      border-radius: 6px;
      padding: 13px 14px;
      font-size: 16px;
      color: var(--text);
      background: #fff;
      outline: none;
    }
    input:focus {
      border-color: var(--brand);
      box-shadow: 0 0 0 3px rgba(15, 111, 100, 0.14);
    }
    button {
      border: 0;
      border-radius: 6px;
      background: var(--brand);
      color: #fff;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--brand-dark); }
    button:disabled { opacity: .65; cursor: wait; }
    .answer {
      margin-top: 20px;
      border-top: 1px solid var(--line);
      padding-top: 20px;
    }
    .answer h2, .side h2 {
      margin: 0 0 12px;
      font-size: 16px;
    }
    .answer-text {
      font-size: 18px;
      line-height: 1.7;
      margin: 0 0 16px;
    }
    .meta {
      display: none;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
    }
    .meta a {
      color: var(--brand-dark);
      overflow-wrap: anywhere;
    }
    .chips {
      display: grid;
      gap: 8px;
      margin-bottom: 16px;
    }
    .chip {
      border: 1px solid #c8d2df;
      background: #fff;
      color: var(--text);
      padding: 9px 10px;
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
    }
    .matches {
      margin-top: 18px;
      display: grid;
      gap: 10px;
    }
    .match {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 11px 12px;
      background: #fbfcfe;
      font-size: 13px;
      color: var(--muted);
    }
    .match strong {
      display: block;
      color: var(--text);
      font-size: 14px;
      margin-bottom: 4px;
    }
    .empty {
      color: var(--muted);
      line-height: 1.7;
      margin: 0;
    }
    .error { color: var(--accent); }
    .guardrail {
      margin-top: 12px;
      padding: 10px 12px;
      border: 1px solid #fecdca;
      border-radius: 6px;
      background: #fff6f5;
      color: #912018;
      font-size: 14px;
      line-height: 1.6;
    }
    .primary-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 14px;
      border-radius: 6px;
      background: var(--brand);
      color: #fff;
      font-weight: 700;
      text-decoration: none;
      margin-bottom: 12px;
    }
    .primary-link:hover { background: var(--brand-dark); text-decoration: none; }
    .action-links { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .action-links .primary-link { margin-bottom: 0; }
    .source-link {
      display: inline-flex;
      align-items: center;
      min-height: 40px;
      padding: 0 14px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--brand-dark);
      font-weight: 700;
    }
    .mini-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 13px;
    }
    .mini-meta span {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      background: #fff;
    }
    .result-count {
      margin-left: 8px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 500;
    }
    .related-results {
      margin-top: 18px;
      border-top: 1px solid var(--line);
    }
    .related-results h3 {
      margin: 16px 0 4px;
      font-size: 16px;
    }
    .related-item {
      padding: 14px 0;
      border-bottom: 1px solid var(--line);
    }
    .related-item:last-child { border-bottom: 0; }
    .related-item h4 { margin: 0 0 6px; font-size: 16px; }
    .related-item p { margin: 0 0 9px; color: var(--text); line-height: 1.65; }
    .related-meta { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
    .related-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .related-actions a {
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--brand-dark);
      font-size: 13px;
      font-weight: 700;
    }
    details {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      margin-top: 10px;
    }
    summary {
      cursor: pointer;
      padding: 12px;
      font-weight: 700;
      color: var(--text);
    }
    .guide-card {
      margin: 0;
      border: 1px solid var(--line);
      border-width: 1px 0 0;
      border-radius: 0;
      background: #fbfcfe;
      overflow: hidden;
    }
    .guide-head {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 8px;
      border-radius: 999px;
      background: #eef7f5;
      color: var(--brand-dark);
      font-size: 13px;
      font-weight: 700;
    }
    .guide-body {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0;
    }
    .guide-field {
      padding: 12px;
      border-bottom: 1px solid var(--line);
      min-width: 0;
    }
    .guide-field:nth-child(odd) {
      border-right: 1px solid var(--line);
    }
    .guide-field strong {
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 5px;
    }
    .guide-field span {
      display: block;
      line-height: 1.6;
      overflow-wrap: anywhere;
    }
    .guide-list {
      grid-column: 1 / -1;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }
    .guide-list strong {
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 7px;
    }
    .guide-list ol, .guide-list ul {
      margin: 0;
      padding-left: 20px;
      line-height: 1.75;
    }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; padding: 18px 14px 30px; }
      .topbar { padding: 14px; align-items: flex-start; flex-direction: column; }
      .ask-row { grid-template-columns: 1fr; }
      button { min-height: 46px; }
      .guide-body { grid-template-columns: 1fr; }
      .guide-field:nth-child(odd) { border-right: 0; }
    }
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div class="brand">
        <div class="mark">暨</div>
        <h1>暨南大学学生助手</h1>
      </div>
      <div class="status">核心服务卡片知识库</div>
    </div>
  </header>
  <main>
    <section class="workspace">
      <label class="label" for="question">输入学生办事问题</label>
      <div class="ask-row">
        <input id="question" autocomplete="off" value="本科生请假申请表在哪里下载？" />
        <button id="askBtn">查询</button>
      </div>
      <div class="answer" id="answer">
        <p class="empty">可查询请假申请表、转专业申请表、成绩单和在学证明、新生入学资格申请表等第一批服务材料。</p>
      </div>
    </section>
    <aside class="side">
      <h2>推荐问题</h2>
      <div class="chips" id="examples">
        <span class="chip">本科生请假申请表在哪里下载？</span>
        <span class="chip">转专业申请表在哪里？</span>
        <span class="chip">成绩单和在学证明怎么打印？</span>
        <span class="chip">学生证遗失怎么补办？</span>
        <span class="chip">新生保留入学资格申请表在哪里下载？</span>
      </div>
      <p class="empty">答案会优先保留知识库原文里的来源链接，避免模型改错网址或日期。</p>
    </aside>
  </main>
  <script>
    const input = document.querySelector("#question");
    const button = document.querySelector("#askBtn");
    const answer = document.querySelector("#answer");

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
      }[char]));
    }

    function render(data) {
      const guide = data.guide || {};
      const downloads = (data.downloads || []).map(item => `
        <a class="primary-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">直接下载：${escapeHtml(item.name)}</a>
      `).join("");
      const sourceIsDownload = (data.downloads || []).some(item => item.url === data.source_url);
      const source = data.source_url && !sourceIsDownload
        ? `<a class="source-link" href="${escapeHtml(data.source_url)}" target="_blank" rel="noreferrer">查看官方说明</a>`
        : "";
      const actions = downloads || source ? `<div class="action-links">${downloads}${source}</div>` : "";
      const miniMeta = data.ok ? `
        <div class="mini-meta">
          ${guide.service_type ? `<span>${escapeHtml(guide.service_type)}</span>` : ""}
          ${guide.department ? `<span>${escapeHtml(guide.department)}</span>` : ""}
          ${guide.materials ? `<span>${escapeHtml(guide.materials)}</span>` : ""}
        </div>
      ` : "";
      const relatedMatches = (data.matches || []).filter(item =>
        item.document_name &&
        item.document_name !== data.document_name &&
        Number(item.similarity || 0) >= Number(data.threshold || 0)
      );
      const relatedItems = relatedMatches.map(item => {
        const itemDownloads = (item.downloads || []).map(download => `
          <a href="${escapeHtml(download.url)}" target="_blank" rel="noreferrer">直接下载：${escapeHtml(download.name)}</a>
        `).join("");
        const itemSource = item.source_url
          ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">查看官方说明</a>`
          : "";
        return `
          <article class="related-item">
            <h4>${escapeHtml((item.document_name || "相关结果").replace(/\.md$/i, ""))}</h4>
            <div class="related-meta">相关度 ${Number(item.similarity || 0).toFixed(3)}</div>
            <p>${escapeHtml(item.answer || item.snippet || "")}</p>
            <div class="related-actions">${itemDownloads}${itemSource}</div>
          </article>
        `;
      }).join("");
      const relatedResults = data.ok && relatedItems ? `
        <section class="related-results">
          <h3>其他相关结果</h3>
          ${relatedItems}
        </section>
      ` : "";
      const visibleResultCount = data.ok ? 1 + relatedMatches.length : 0;
      const matches = (data.matches || []).map(item => `
        <div class="match">
          <strong>${escapeHtml(item.document_name || "未命名文档")} · 相似度 ${Number(item.similarity || 0).toFixed(3)}</strong>
          <div>${escapeHtml(item.snippet || item.answer || "")}</div>
        </div>
      `).join("");
      const guardrail = data.ok ? "" : `
        <div class="guardrail">
          未提供答案的问题已记录为待补充数据。当前最低可信相似度阈值：${Number(data.threshold || 0).toFixed(2)}
        </div>
      `;
      const steps = (guide.steps || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const notes = (guide.notes || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      const guideCard = data.ok ? `
        <details>
          <summary>查看办事细节</summary>
          <div class="guide-card">
            <div class="guide-body">
              <div class="guide-field"><strong>适用对象</strong><span>${escapeHtml(guide.audience || "当前知识库暂未收录")}</span></div>
              <div class="guide-field"><strong>办理入口</strong><span>${escapeHtml(guide.entrance || "当前知识库暂未收录")}</span></div>
              <div class="guide-field"><strong>所需材料</strong><span>${escapeHtml(guide.materials || "当前知识库暂未收录")}</span></div>
              <div class="guide-field"><strong>负责部门</strong><span>${escapeHtml(guide.department || "当前知识库暂未收录")}</span></div>
              <div class="guide-list"><strong>办理步骤</strong><ol>${steps || "<li>当前知识库暂未收录具体流程，请以来源页面为准。</li>"}</ol></div>
              <div class="guide-list"><strong>注意事项</strong><ul>${notes || "<li>当前知识库暂未收录具体注意事项，请以来源页面为准。</li>"}</ul></div>
              <div class="guide-list"><strong>检索依据</strong><div>命中文档：${escapeHtml(data.document_name || "无")} · 相似度 ${Number(data.similarity || 0).toFixed(3)}</div></div>
            </div>
          </div>
        </details>
      ` : "";
      const matchDetails = data.ok && matches ? `
        <details>
          <summary>查看匹配片段</summary>
          <div class="matches">${matches}</div>
        </details>
      ` : "";
      answer.innerHTML = `
        <h2>回答${visibleResultCount > 1 ? `<span class="result-count">找到 ${visibleResultCount} 个相关结果</span>` : ""}</h2>
        <p class="answer-text ${data.ok ? "" : "error"}">${escapeHtml(data.answer)}</p>
        ${guardrail}
        ${actions}
        ${miniMeta}
        ${relatedResults}
        ${guideCard}
        ${matchDetails}
      `;
    }

    async function ask() {
      const question = input.value.trim();
      if (!question) {
        input.focus();
        return;
      }
      button.disabled = true;
      button.textContent = "查询中";
      answer.innerHTML = `<p class="empty">正在检索知识库...</p>`;
      try {
        const response = await fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question })
        });
        const data = await response.json();
        render(data);
      } catch (error) {
        answer.innerHTML = `<p class="empty error">查询失败，请确认 Docker 和 RAGFlow 正在运行。</p>`;
      } finally {
        button.disabled = false;
        button.textContent = "查询";
      }
    }

    button.addEventListener("click", ask);
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") ask();
    });
    document.querySelector("#examples").addEventListener("click", event => {
      if (!event.target.classList.contains("chip")) return;
      input.value = event.target.textContent;
      ask();
    });
  </script>
</body>
</html>
"""


class StudentAssistantHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/coverage":
            self.send_json(build_coverage_report())
            return
        if path == "/pipeline":
            body = build_dashboard().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/ask":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            question = str(payload.get("question", ""))
            result = ask_core_service(question)
        except Exception as exc:
            self.send_json(
                {
                    "ok": False,
                    "answer": f"查询失败：{exc}",
                    "source_url": "",
                    "document_name": "",
                    "similarity": 0,
                    "matches": [],
                },
                status=500,
            )
            return
        self.send_json(result)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), StudentAssistantHandler)
    print(f"Student assistant is running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
