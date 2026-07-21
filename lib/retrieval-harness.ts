import { Annotation, END, START, StateGraph } from "@langchain/langgraph";

export type RetrievalChunk = {
  content?: string;
  content_with_weight?: string;
  document_keyword?: string;
  document_name?: string;
  similarity?: number;
};

export type RetrievalResult = {
  chunks: RetrievalChunk[];
  source: "service_card" | "ragflow";
};

export type HarnessTrace = {
  node: "guard_input" | "retrieve_knowledge" | "quality_check" | "rewrite_query" | "generate_answer" | "reject";
  status: "success" | "retry" | "rejected" | "error";
  attempt: number;
  query: string;
  score?: number;
  detail: string;
  durationMs: number;
};

type Decision = "pass" | "retry" | "reject";
type RunRetrieval = (query: string, attempt: number) => Promise<RetrievalResult>;

const GraphState = Annotation.Root({
  originalQuestion: Annotation<string>(),
  query: Annotation<string>(),
  attempt: Annotation<number>(),
  maxRetries: Annotation<number>(),
  chunks: Annotation<RetrievalChunk[]>(),
  source: Annotation<RetrievalResult["source"]>(),
  topScore: Annotation<number>(),
  decision: Annotation<Decision>(),
  reason: Annotation<string>(),
  retrievalError: Annotation<string>(),
  trace: Annotation<HarnessTrace[]>({
    reducer: (current, update) => current.concat(update),
    default: () => []
  })
});

function contentOf(chunk?: RetrievalChunk) {
  return String(chunk?.content || chunk?.content_with_weight || "");
}

function hasTrustedSource(chunks: RetrievalChunk[]) {
  return chunks.some(chunk => /https?:\/\/(?:[^/]+\.)?jnu\.edu\.cn(?:\/|\s|$)/i.test(contentOf(chunk)));
}

function rewriteQuestion(question: string, attempt: number) {
  const normalized = question
    .replace(/^(请问|你好|老师好)[，,：:\s]*/g, "")
    .replace(/(麻烦|帮我|我想知道|想了解|请告诉我)/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return attempt === 1
    ? `${normalized} 暨南大学 官方办理 事项名称`
    : `${normalized} 暨南大学 官方来源 办理入口 下载材料`;
}

function guardReason(question: string) {
  const normalized = question.toLowerCase().replace(/\s+/g, "");
  const rules = [
    { phrases: ["账号密码", "教务系统密码", "验证码", "破解密码"], reason: "不能查询或推测账号密码与验证码" },
    { phrases: ["身份证号码", "身份证号", "家庭住址", "私人手机", "隐私信息"], reason: "不能查询或提供他人个人隐私" },
    { phrases: ["吃什么药", "用药剂量", "药吃多少", "帮我诊断"], reason: "不能进行医疗诊断或提供具体用药建议" },
    { phrases: ["一定能被录取", "保证录取", "预测录取", "录取概率"], reason: "不能保证或预测个人录取结果" },
    { phrases: ["尚未公开", "未公开的", "还没发布", "未发布的"], reason: "不能推测尚未公开的信息" }
  ];
  return rules.find(rule => rule.phrases.some(phrase => normalized.includes(phrase)))?.reason || "";
}

export async function runRetrievalHarness(question: string, retrieve: RunRetrieval, maxRetries = 2) {
  const guardNode = async (state: typeof GraphState.State) => {
    const started = Date.now();
    const reason = guardReason(state.originalQuestion);
    return {
      decision: reason ? "reject" as const : "pass" as const,
      reason,
      trace: [{
        node: "guard_input" as const,
        status: reason ? "rejected" as const : "success" as const,
        attempt: 0,
        query: state.originalQuestion,
        detail: reason || "输入安全检查通过",
        durationMs: Date.now() - started
      }]
    };
  };

  const retrieveNode = async (state: typeof GraphState.State) => {
    const started = Date.now();
    try {
      const result = await retrieve(state.query, state.attempt);
      const topScore = Number(result.chunks[0]?.similarity || 0);
      return {
        chunks: result.chunks,
        source: result.source,
        topScore,
        retrievalError: "",
        trace: [{
          node: "retrieve_knowledge" as const,
          status: "success" as const,
          attempt: state.attempt,
          query: state.query,
          score: topScore,
          detail: `召回 ${result.chunks.length} 个分块`,
          durationMs: Date.now() - started
        }]
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "检索工具调用失败";
      return {
        chunks: [],
        topScore: 0,
        retrievalError: message,
        trace: [{
          node: "retrieve_knowledge" as const,
          status: "error" as const,
          attempt: state.attempt,
          query: state.query,
          score: 0,
          detail: message,
          durationMs: Date.now() - started
        }]
      };
    }
  };

  const qualityNode = async (state: typeof GraphState.State) => {
    const started = Date.now();
    const topContent = contentOf(state.chunks[0]);
    let decision: Decision = "pass";
    let reason = "分数、内容和官方来源均通过校验";
    if (state.retrievalError) {
      decision = state.attempt < state.maxRetries ? "retry" : "reject";
      reason = "检索工具调用失败";
    } else if (!state.chunks.length || state.topScore < 0.2) {
      decision = state.attempt < state.maxRetries ? "retry" : "reject";
      reason = "最高相似度低于 0.2";
    } else if (topContent.replace(/\s+/g, "").length < 30) {
      decision = state.attempt < state.maxRetries ? "retry" : "reject";
      reason = "召回内容不足以支撑回答";
    } else if (!hasTrustedSource(state.chunks)) {
      decision = state.attempt < state.maxRetries ? "retry" : "reject";
      reason = "召回结果缺少暨南大学官方来源";
    }
    return {
      decision,
      reason,
      trace: [{
        node: "quality_check" as const,
        status: decision === "pass" ? "success" as const : decision === "retry" ? "retry" as const : "rejected" as const,
        attempt: state.attempt,
        query: state.query,
        score: state.topScore,
        detail: reason,
        durationMs: Date.now() - started
      }]
    };
  };

  const rewriteNode = async (state: typeof GraphState.State) => {
    const started = Date.now();
    const attempt = state.attempt + 1;
    const query = rewriteQuestion(state.originalQuestion, attempt);
    return {
      attempt,
      query,
      trace: [{
        node: "rewrite_query" as const,
        status: "retry" as const,
        attempt,
        query,
        detail: `第 ${attempt} 次受控改写`,
        durationMs: Date.now() - started
      }]
    };
  };

  const answerNode = async (state: typeof GraphState.State) => ({
    trace: [{
      node: "generate_answer" as const,
      status: "success" as const,
      attempt: state.attempt,
      query: state.query,
      score: state.topScore,
      detail: "使用通过质检的知识库原文生成回答",
      durationMs: 0
    }]
  });

  const rejectNode = async (state: typeof GraphState.State) => ({
    trace: [{
      node: "reject" as const,
      status: "rejected" as const,
      attempt: state.attempt,
      query: state.query,
      score: state.topScore,
      detail: `停止执行：${state.reason}`,
      durationMs: 0
    }]
  });

  const graph = new StateGraph(GraphState)
    .addNode("guard_input", guardNode)
    .addNode("retrieve_knowledge", retrieveNode)
    .addNode("quality_check", qualityNode)
    .addNode("rewrite_query", rewriteNode)
    .addNode("generate_answer", answerNode)
    .addNode("reject", rejectNode)
    .addEdge(START, "guard_input")
    .addConditionalEdges("guard_input", state => state.decision, {
      pass: "retrieve_knowledge",
      reject: "reject"
    })
    .addEdge("retrieve_knowledge", "quality_check")
    .addConditionalEdges("quality_check", state => state.decision, {
      pass: "generate_answer",
      retry: "rewrite_query",
      reject: "reject"
    })
    .addEdge("rewrite_query", "retrieve_knowledge")
    .addEdge("generate_answer", END)
    .addEdge("reject", END)
    .compile();

  const result = await graph.invoke({
    originalQuestion: question,
    query: question,
    attempt: 0,
    maxRetries,
    chunks: [],
    source: "ragflow",
    topScore: 0,
    decision: "retry",
    reason: "",
    retrievalError: "",
    trace: []
  }, { recursionLimit: 12 });

  return {
    ok: result.decision === "pass",
    chunks: result.chunks,
    topScore: result.topScore,
    finalQuery: result.query,
    retries: result.attempt,
    reason: result.reason,
    trace: result.trace
  };
}
