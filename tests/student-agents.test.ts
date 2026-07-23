import assert from "node:assert/strict";
import test from "node:test";
import { answerWeightedAverage, computeWeightedAverage, routeStudentQuestion } from "../lib/student-agents.ts";

test("routes normal school affairs questions to retrieval", () => {
  const decision = routeStudentQuestion("本科生请假申请表在哪里下载？");
  assert.equal(decision.route, "retrieve");
});

test("routes health questions to health agent", () => {
  const decision = routeStudentQuestion("感冒了怎么办");
  assert.equal(decision.route, "health");
});

test("routes score calculation questions to tool agent", () => {
  const decision = routeStudentQuestion("高数85分4学分，英语90分3学分，帮我算加权平均分");
  assert.equal(decision.route, "tool");
});

test("computes weighted average", () => {
  const result = computeWeightedAverage([{ score: 85, credits: 4 }, { score: 90, credits: 3 }]);
  assert.deepEqual(result, { weightedAverage: 87.14, totalCredits: 7, courseCount: 2 });
});

test("tool answer includes disclaimer", () => {
  const answer = answerWeightedAverage("高数85分4学分，英语90分3学分");
  assert.match(answer, /87\.14/);
  assert.match(answer, /不代表学校官方成绩认定/);
});
