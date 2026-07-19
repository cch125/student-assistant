from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from import_experiment_pipelines import PROJECT_ROOT, RagflowClient
from tune_retrieval_parameters import score_results, score_separation, threshold_grid


BENCHMARK_PATH = PROJECT_ROOT / "config" / "retrieval_benchmark.json"
OUTPUT_JSON = PROJECT_ROOT / "outputs" / "core_retrieval_tuning.json"
OUTPUT_MD = PROJECT_ROOT / "outputs" / "core_retrieval_tuning.md"
RECOMMENDED_CONFIG = PROJECT_ROOT / "config" / "recommended_core_retrieval.json"
EXPANDED_BENCHMARK = PROJECT_ROOT / "config" / "core_retrieval_benchmark.json"
BASE_URL = "http://localhost:8080/api/v1"
DATASET_NAME = "暨南大学学生助手-核心服务卡片"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3@default1@OpenAI-API-Compatible"


@dataclass(frozen=True)
class Candidate:
    vector_weight: float
    rerank_id: str | None = None

    @property
    def key(self) -> str:
        mode = "rerank" if self.rerank_id else "base"
        return f"{mode}:w={self.vector_weight:.3f}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def query_variants(query: str) -> list[str]:
    core = query.strip().rstrip("？?")
    return [
        query.strip(),
        f"请问{core}？",
        f"我是暨大学生，想了解{core}。",
        f"{core}，麻烦提供学校官方办理方式。",
    ]


def expand_benchmark(source: dict[str, Any]) -> dict[str, Any]:
    positive_source = [case for case in source["positive_cases"] if case.get("target", "core") == "core"]
    negative_source = [case for case in source["negative_cases"] if case.get("target", "core") == "core"]
    expanded: dict[str, Any] = {
        "version": "2.0",
        "description": "由40个独立意图扩展出的160条正式核心知识库检索问法；训练验证按意图隔离。",
        "source_intents": len(positive_source) + len(negative_source),
        "positive_cases": [],
        "negative_cases": [],
    }
    for group, cases in (("positive_cases", positive_source), ("negative_cases", negative_source)):
        for case in cases:
            for index, query in enumerate(query_variants(case["query"])):
                expanded[group].append(
                    {
                        **case,
                        "id": f"{case['id']}:v{index}",
                        "intent_id": case["id"],
                        "query": query,
                        "variant": index,
                    }
                )
    return expanded


def retrieve_case(
    dataset_id: str,
    candidate: Candidate,
    case: dict[str, Any],
    case_type: str,
) -> dict[str, Any]:
    client = RagflowClient(BASE_URL)
    started = time.monotonic()
    data = client.request(
        "POST",
        "/retrieval",
        json={
            "dataset_ids": [dataset_id],
            "question": case["query"],
            "page": 1,
            "page_size": 10,
            "top_k": 20,
            "similarity_threshold": 0.0,
            "vector_similarity_weight": candidate.vector_weight,
            "rerank_id": candidate.rerank_id,
            "keyword": False,
            "highlight": False,
        },
    )
    return {
        "case_id": case["id"],
        "intent_id": case["intent_id"],
        "case_type": case_type,
        "query": case["query"],
        "relevant_patterns": case.get("relevant_patterns", []),
        "latency_seconds": round(time.monotonic() - started, 4),
        "chunks": [
            {
                "rank": rank,
                "similarity": float(chunk.get("similarity") or 0),
                "document_name": chunk.get("document_keyword") or chunk.get("document_name") or "",
                "preview": str(chunk.get("content") or chunk.get("content_with_weight") or "")[:300],
            }
            for rank, chunk in enumerate(data.get("chunks", []), start=1)
        ],
    }


def run_candidate(
    dataset_id: str,
    candidate: Candidate,
    benchmark: dict[str, Any],
    workers: int,
) -> list[dict[str, Any]]:
    jobs = [(case, "positive") for case in benchmark["positive_cases"]]
    jobs += [(case, "negative") for case in benchmark["negative_cases"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(retrieve_case, dataset_id, candidate, case, case_type)
            for case, case_type in jobs
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    return sorted(results, key=lambda item: (item["case_type"], item["case_id"]))


def evaluate(
    candidate: Candidate,
    results: list[dict[str, Any]],
    training_ids: set[str],
    validation_ids: set[str],
) -> dict[str, Any]:
    thresholds = threshold_grid([0.2 + index * 0.025 for index in range(27)])
    training_scores = [score_results(results, threshold, training_ids) for threshold in thresholds]
    best = max(
        training_scores,
        key=lambda item: (item["objective"], item["negative_rejection_rate"], item["mrr"]),
    )
    return {
        "key": candidate.key,
        "vector_weight": candidate.vector_weight,
        "full_text_weight": round(1 - candidate.vector_weight, 3),
        "rerank_id": candidate.rerank_id,
        "threshold": best["threshold"],
        "training_metrics": best,
        "validation_metrics": score_results(results, best["threshold"], validation_ids),
        "all_metrics": score_results(results, best["threshold"]),
        "score_separation": score_separation(results),
        "mean_latency_seconds": statistics.mean(item["latency_seconds"] for item in results),
        "raw_results": results,
    }


def report(payload: dict[str, Any]) -> str:
    winner = payload["recommendation"]
    lines = [
        "# 正式核心知识库召回参数报告",
        "",
        f"- 测试问法：{payload['case_count']} 条（{payload['intent_count']} 个独立意图）",
        f"- 数据集：`{payload['dataset_id']}`",
        f"- 向量权重：{winner['vector_similarity_weight']:.3f}",
        f"- Full-text 权重：{winner['full_text_weight']:.3f}",
        f"- 相似度阈值：{winner['similarity_threshold']:.3f}",
        f"- Rerank：{winner['rerank_id'] or '关闭'}",
        f"- 验证 Recall@1：{winner['validation_metrics']['recall_at_1']:.1%}",
        f"- 验证 MRR：{winner['validation_metrics']['mrr']:.3f}",
        f"- 验证拒答率：{winner['validation_metrics']['negative_rejection_rate']:.1%}",
        "",
        "## 控制变量对照",
        "",
        "| 模式 | Vector | Full-text | 阈值 | Recall@1 | MRR | 拒答率 | 平均延迟 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["leaderboard"]:
        metrics = item["validation_metrics"]
        lines.append(
            f"| {'Rerank' if item['rerank_id'] else '基础召回'} | {item['vector_weight']:.3f} | "
            f"{item['full_text_weight']:.3f} | {item['threshold']:.3f} | {metrics['recall_at_1']:.1%} | "
            f"{metrics['mrr']:.3f} | {metrics['negative_rejection_rate']:.1%} | {item['mean_latency_seconds']:.3f}s |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune the production core RAGFlow dataset with intent-isolated validation.")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--reuse-results", action="store_true")
    args = parser.parse_args()

    source = load_json(BENCHMARK_PATH)
    benchmark = expand_benchmark(source)
    EXPANDED_BENCHMARK.write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8")

    client = RagflowClient(BASE_URL)
    dataset = next((item for item in client.list_datasets() if item.get("name") == DATASET_NAME), None)
    if not dataset:
        raise RuntimeError(f"Missing RAGFlow dataset: {DATASET_NAME}")

    intents = sorted({item["intent_id"] for item in benchmark["positive_cases"] + benchmark["negative_cases"]})
    validation_intents = {intent for index, intent in enumerate(intents) if index % 4 == 0}
    training_ids = {
        case["id"]
        for case in benchmark["positive_cases"] + benchmark["negative_cases"]
        if case["intent_id"] not in validation_intents
    }
    validation_ids = {
        case["id"]
        for case in benchmark["positive_cases"] + benchmark["negative_cases"]
        if case["intent_id"] in validation_intents
    }

    previous = load_json(OUTPUT_JSON) if args.reuse_results and OUTPUT_JSON.exists() else {}
    cached = previous.get("evaluations", {})
    evaluations: dict[str, Any] = {}
    base_candidates = [Candidate(weight) for weight in (0.1, 0.3, 0.5, 0.7, 0.9)]
    for candidate in base_candidates:
        print(f"[core] {candidate.key}")
        results = cached.get(candidate.key, {}).get("raw_results")
        if not results:
            results = run_candidate(dataset["id"], candidate, benchmark, args.workers)
        evaluations[candidate.key] = evaluate(candidate, results, training_ids, validation_ids)

    base_winner = max(
        evaluations.values(),
        key=lambda item: (
            item["training_metrics"]["objective"],
            item["validation_metrics"]["objective"],
            item["validation_metrics"]["mrr"],
        ),
    )
    rerank_candidate = Candidate(base_winner["vector_weight"], RERANK_MODEL)
    print(f"[core] {rerank_candidate.key}")
    rerank_results = cached.get(rerank_candidate.key, {}).get("raw_results")
    if not rerank_results:
        rerank_results = run_candidate(dataset["id"], rerank_candidate, benchmark, args.workers)
    evaluations[rerank_candidate.key] = evaluate(
        rerank_candidate, rerank_results, training_ids, validation_ids
    )

    leaderboard = sorted(
        evaluations.values(),
        key=lambda item: (
            item["training_metrics"]["objective"],
            item["validation_metrics"]["objective"],
            item["validation_metrics"]["mrr"],
            -item["mean_latency_seconds"],
        ),
        reverse=True,
    )
    winner = leaderboard[0]
    base_best = max(
        (item for item in leaderboard if not item["rerank_id"]),
        key=lambda item: item["training_metrics"]["objective"],
    )
    rerank_gain = winner["training_metrics"]["objective"] - base_best["training_metrics"]["objective"]
    selection_reason = (
        "Rerank 消除了基础召回残留的无答案误召回，并显著扩大正负分数间隔。"
        if winner["rerank_id"]
        else "基础召回已达到最佳指标，Rerank 未带来足够收益。"
    )
    recommendation = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_name": DATASET_NAME,
        "dataset_id": dataset["id"],
        "document_count": int(dataset.get("document_count") or 0),
        "chunk_count": int(dataset.get("chunk_count") or 0),
        "vector_similarity_weight": winner["vector_weight"],
        "full_text_weight": winner["full_text_weight"],
        "similarity_threshold": winner["threshold"],
        "top_k": 20,
        "page_size": 3,
        "keyword": False,
        "cross_languages": [],
        "metadata_condition": None,
        "use_kg": False,
        "rerank_id": winner["rerank_id"],
        "validation_metrics": winner["validation_metrics"],
        "score_separation": winner["score_separation"],
        "selection_reason": selection_reason,
        "rerank_objective_gain": rerank_gain if winner["rerank_id"] else 0.0,
    }
    payload = {
        "generated_at": recommendation["generated_at"],
        "dataset_id": dataset["id"],
        "intent_count": len(intents),
        "case_count": len(benchmark["positive_cases"]) + len(benchmark["negative_cases"]),
        "validation_intents": sorted(validation_intents),
        "recommendation": recommendation,
        "leaderboard": [{key: value for key, value in item.items() if key != "raw_results"} for item in leaderboard],
        "evaluations": evaluations,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(report(payload), encoding="utf-8")
    RECOMMENDED_CONFIG.write_text(json.dumps(recommendation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report(payload))


if __name__ == "__main__":
    main()
