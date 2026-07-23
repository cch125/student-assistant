export type StudentRoute = "retrieve" | "tool" | "image" | "health" | "reject";

export type StudentAgentDecision = {
  route: StudentRoute;
  reason: string;
};

export type AgentMessage = { role: "system" | "user"; content: string };

export type AgentTrace = {
  node: string;
  status: "success" | "retry" | "rejected" | "error";
  attempt: number;
  query: string;
  score?: number;
  detail: string;
  durationMs: number;
};

export type WeightedAverageResult = {
  weightedAverage: number;
  totalCredits: number;
  courseCount: number;
};

const HEALTH_TERMS = [
  "感冒", "发烧", "发热", "咳嗽", "头痛", "头疼", "肚子痛", "腹痛", "拉肚子",
  "过敏", "校医", "校医院", "医务室", "门诊", "急诊", "医保", "医疗",
  "公费医疗", "看病", "生病", "不舒服", "发炎", "扭伤", "受伤", "流感"
];

const REJECT_TERMS = [
  "账号密码", "验证码", "身份证号码", "身份证号", "私人手机", "家庭住址",
  "未公开", "尚未公开", "保证录取", "预测录取"
];

export function routeStudentQuestion(question: string, hasImage = false): StudentAgentDecision {
  const normalized = question.toLowerCase().replace(/\s+/g, "");
  if (hasImage) {
    return { route: "image", reason: "用户上传了图片，需要先由视觉识别智能体提取可检索信息" };
  }
  if (HEALTH_TERMS.some(term => normalized.includes(term))) {
    return { route: "health", reason: "问题属于健康或校内医疗服务，需要安全分流并检索校医室、门诊、医保或公费医疗信息" };
  }
  if (/吃什么药|用药剂量|药吃多少|帮我诊断/.test(normalized)) {
    return { route: "health", reason: "问题涉及健康风险，只能做安全提醒和校内医疗服务引导，不能诊断或开药" };
  }
  if (REJECT_TERMS.some(term => normalized.includes(term))) {
    return { route: "reject", reason: "问题涉及隐私、安全、未公开或无法保证的信息" };
  }
  if (/(gpa|绩点|加权平均|平均分|学分).*(算|计算|多少)|怎么算.*(gpa|绩点|平均分)/i.test(question)) {
    return { route: "tool", reason: "问题属于成绩、绩点或学分计算" };
  }
  return { route: "retrieve", reason: "问题需要检索学生事务知识库" };
}

function llmConfig() {
  const apiKey = process.env.LLM_API_KEY || process.env.SILICONFLOW_API_KEY || process.env.VLM_API_KEY || "";
  const baseUrl = (process.env.LLM_BASE_URL || process.env.SILICONFLOW_API_BASE || process.env.VLM_BASE_URL || "https://api.siliconflow.cn/v1").replace(/\/$/, "");
  const model = process.env.LLM_MODEL || process.env.ANALYZER_MODEL || process.env.TEXT_MODEL || "Qwen/Qwen2.5-32B-Instruct";
  return { apiKey, baseUrl, model };
}

async function callLLM(messages: AgentMessage[], maxTokens = 600, temperature = 0) {
  const { apiKey, baseUrl, model } = llmConfig();
  if (!apiKey || /replace-with/i.test(apiKey)) throw new Error("LLM API Key 未配置");
  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages, temperature, max_tokens: maxTokens }),
    signal: AbortSignal.timeout(45000)
  });
  if (!response.ok) throw new Error(`LLM 调用失败：${response.status}`);
  const payload = await response.json();
  return String(payload?.choices?.[0]?.message?.content || "").trim();
}

function parseJsonObject(text: string) {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return undefined;
  try {
    return JSON.parse(match[0]) as Record<string, unknown>;
  } catch {
    return undefined;
  }
}

export async function llmRouterAgent(question: string, hasImage = false): Promise<StudentAgentDecision & { usedLLM: boolean }> {
  const fallback = routeStudentQuestion(question, hasImage);
  try {
    const raw = await callLLM([
      { role: "system", content: "你是暨南大学学生助手的 Router Agent。只输出 JSON，不要解释。" },
      {
        role: "user",
        content: `把学生问题分到 retrieve/tool/image/health/reject 之一。
- retrieve：学校办事、通知、政策、文档下载、流程查询
- tool：GPA、绩点、学分、加权平均等计算
- image：用户上传图片，需要先识别
- health：感冒、发烧、校医、门诊、医保、公费医疗、看病等健康或校内医疗服务问题；只能做安全分流和校内服务检索，不能诊断或开药
- reject：隐私、账号密码、未公开信息、校外无关问题

用户是否上传图片：${hasImage}
问题：${question}
输出格式：{"route":"retrieve","reason":"一句话原因"}`
      }
    ], 120, 0);
    const parsed = parseJsonObject(raw);
    const route = String(parsed?.route || fallback.route) as StudentRoute;
    if (!["retrieve", "tool", "image", "health", "reject"].includes(route)) return { ...fallback, usedLLM: false };
    return { route, reason: String(parsed?.reason || fallback.reason), usedLLM: true };
  } catch {
    return { ...fallback, usedLLM: false };
  }
}

export function extractScoreCredits(question: string) {
  const courses: { score: number; credits: number }[] = [];
  const pattern = /(\d+(?:\.\d+)?)\s*(?:分)?[^\d]{0,12}?(\d+(?:\.\d+)?)\s*(?:学分|分学分)/g;
  for (const match of question.matchAll(pattern)) {
    const score = Number(match[1]);
    const credits = Number(match[2]);
    if (Number.isFinite(score) && Number.isFinite(credits) && score >= 0 && score <= 100 && credits > 0) {
      courses.push({ score, credits });
    }
  }
  return courses;
}

export function computeWeightedAverage(courses: { score: number; credits: number }[]): WeightedAverageResult | undefined {
  const totalCredits = courses.reduce((sum, item) => sum + item.credits, 0);
  if (!courses.length || totalCredits <= 0) return undefined;
  const total = courses.reduce((sum, item) => sum + item.score * item.credits, 0);
  return {
    weightedAverage: Math.round((total / totalCredits) * 100) / 100,
    totalCredits,
    courseCount: courses.length
  };
}

export function answerWeightedAverage(question: string) {
  const courses = extractScoreCredits(question);
  const result = computeWeightedAverage(courses);
  if (!result) {
    return "我可以帮你计算加权平均分。请按“高数 85 分 4 学分，英语 90 分 3 学分”这样的格式输入。";
  }
  return `根据你输入的 ${result.courseCount} 门课计算，加权平均分为 ${result.weightedAverage}，总学分为 ${result.totalCredits}。此结果仅根据你输入的数据计算，不代表学校官方成绩认定。`;
}

export async function llmAnalyzerAgent(input: {
  question: string;
  chunks: { content?: string; content_with_weight?: string; document_keyword?: string; document_name?: string; similarity?: number }[];
  toolOutput?: string;
}) {
  const references = input.chunks.slice(0, 5).map((chunk, index) => {
    const content = String(chunk.content || chunk.content_with_weight || "").slice(0, 1600);
    const source = chunk.document_keyword || chunk.document_name || `资料${index + 1}`;
    return `【资料${index + 1}】来源：${source}\n${content}`;
  }).join("\n\n");
  return callLLM([
    { role: "system", content: "你是暨南大学学生事务助手的 Analyzer Agent。必须只根据资料和工具结果回答；没有依据就明确说知识库未收录，不要编造。回答要简洁，并标注来源。" },
    { role: "user", content: `学生问题：${input.question}\n\n工具结果：${input.toolOutput || "无"}\n\n参考资料：\n${references || "无"}\n\n请输出给学生的最终草稿。` }
  ], 900, 0.2);
}

export async function llmReflectionAgent(input: {
  question: string;
  answer: string;
  chunks: { content?: string; content_with_weight?: string; document_keyword?: string; document_name?: string; similarity?: number }[];
}) {
  try {
    const sources = input.chunks.slice(0, 5).map((chunk, index) => chunk.document_keyword || chunk.document_name || `资料${index + 1}`).join("、") || "无";
    const raw = await callLLM([
      { role: "system", content: "你是暨南大学学生助手的 Reflection Agent。检查答案是否可交付，只输出 JSON。" },
      {
        role: "user",
        content: `检查标准：1 有来源或明确说明无资料；2 回答了学生问题；3 没有编造；4 没有泄露隐私或给出危险建议。

学生问题：${input.question}
可用来源：${sources}
答案：${input.answer}

输出格式：{"ok":true,"reason":"一句话原因","rewritten_query":"如果不通过，给出更好的检索词"}`
      }
    ], 260, 0);
    const parsed = parseJsonObject(raw);
    return {
      ok: parsed?.ok === true || String(parsed?.ok).toLowerCase() === "true",
      reason: String(parsed?.reason || "LLM 反思完成"),
      rewrittenQuery: parsed?.rewritten_query ? String(parsed.rewritten_query) : undefined,
      usedLLM: true
    };
  } catch {
    return { ok: true, reason: "Reflection Agent 未配置 LLM，回退为规则质检通过", usedLLM: false };
  }
}
