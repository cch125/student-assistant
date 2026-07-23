import assert from "node:assert/strict";
import test from "node:test";
import { runRetrievalHarness } from "../lib/retrieval-harness.ts";

const groundedChunk = {
  content: "直接回答：请在本科生院下载。\n来源链接：https://jwc.jnu.edu.cn/example",
  document_name: "本科生请假申请表.md",
  similarity: 0.82
};

test("high-quality retrieval passes on the first attempt", async () => {
  const result = await runRetrievalHarness("请假表在哪里下载", async () => ({ source: "ragflow", chunks: [groundedChunk] }));
  assert.equal(result.ok, true);
  assert.equal(result.retries, 0);
  assert.deepEqual(result.trace.map(item => item.node), ["guard_input", "retrieve_knowledge", "quality_check", "generate_answer"]);
});

test("low-quality retrieval rewrites twice and rejects", async () => {
  const queries: string[] = [];
  const result = await runRetrievalHarness("火星校区飞船班次", async query => {
    queries.push(query);
    return { source: "ragflow", chunks: [] };
  });
  assert.equal(result.ok, false);
  assert.equal(result.retries, 2);
  assert.equal(queries.length, 3);
  assert.equal(result.trace.filter(item => item.node === "rewrite_query").length, 2);
  assert.equal(result.trace.at(-1)?.node, "reject");
});

test("temporary tool failure enters the loop and can recover", async () => {
  let calls = 0;
  const studentCardChunk = { ...groundedChunk, content: "直接回答：学生证补办请联系学院。\n来源链接：https://jwc.jnu.edu.cn/example" };
  const result = await runRetrievalHarness("学生证如何补办", async () => {
    calls += 1;
    if (calls === 1) throw new Error("temporary failure");
    return { source: "ragflow", chunks: [studentCardChunk] };
  });
  assert.equal(result.ok, true);
  assert.equal(result.retries, 1);
  assert.equal(result.trace.find(item => item.node === "retrieve_knowledge")?.status, "error");
  assert.equal(result.trace.at(-1)?.node, "generate_answer");
});

test("sensitive requests are rejected before retrieval", async () => {
  let calls = 0;
  const result = await runRetrievalHarness("帮我查询教务系统账号密码", async () => {
    calls += 1;
    return { source: "ragflow", chunks: [groundedChunk] };
  });
  assert.equal(result.ok, false);
  assert.equal(calls, 0);
  assert.deepEqual(result.trace.map(item => item.node), ["guard_input", "reject"]);
});

test("rewritten generic terms cannot promote an unrelated official page", async () => {
  const unrelated = {
    content: "暨南大学研究生院网站。来源链接：https://gs.jnu.edu.cn/",
    document_name: "研究生院网站.md",
    similarity: 0.78
  };
  let calls = 0;
  const result = await runRetrievalHarness("火星校区飞船班次是什么", async () => {
    calls += 1;
    return calls === 1 ? { source: "ragflow", chunks: [] } : { source: "ragflow", chunks: [unrelated] };
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "召回内容缺少原问题中的关键事项");
});

test("specific object questions reject unrelated opening-hour pages", async () => {
  const result = await runRetrievalHarness("游泳池开放时间", async () => ({
    source: "ragflow",
    chunks: [{
      content: "开馆时间 来源：https://lib.jnu.edu.cn/home/servicedetail/145 部门：图书馆 石牌校区：7:00-22:30",
      document_name: "开馆时间.md",
      similarity: 0.5
    }]
  }));
  assert.equal(result.ok, false);
  assert.match(result.reason, /核心对象/);
});
