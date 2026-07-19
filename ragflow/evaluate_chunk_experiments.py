from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from import_experiment_pipelines import CONFIG_PATH, PROJECT_ROOT, RagflowClient


OUTPUT_JSON = PROJECT_ROOT / "outputs" / "chunk_experiment_results.json"
OUTPUT_CSV = PROJECT_ROOT / "outputs" / "chunk_experiment_results.csv"


def content_of(chunk: dict[str, Any]) -> str:
    return str(chunk.get("content_with_weight") or chunk.get("content") or "")


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    client = RagflowClient("http://localhost:8080/api/v1")
    datasets = {item["name"]: item for item in client.list_datasets()}
    results: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}

    for experiment in config["datasets"]:
        key = experiment["key"]
        dataset = datasets.get(experiment["name"])
        if not dataset:
            raise RuntimeError(f"Missing experiment dataset: {experiment['name']}")
        documents = client.list_documents(dataset["id"])
        incomplete = [item for item in documents if float(item.get("progress") or 0) != 1]
        if incomplete:
            raise RuntimeError(f"Experiment {key} still has {len(incomplete)} incomplete documents")

        reciprocal_ranks: list[float] = []
        hit_count = 0
        for question_item in config["questions"]:
            payload = client.request(
                "POST",
                "/retrieval",
                json={
                    "dataset_ids": [dataset["id"]],
                    "question": question_item["question"],
                    "page": 1,
                    "page_size": 10,
                    "top_k": 10,
                    "similarity_threshold": 0.1,
                    "vector_similarity_weight": 0.3,
                    "highlight": False,
                },
            )
            chunks = payload.get("chunks", [])
            expected = question_item["expected_terms"]
            first_rank = None
            matched_terms: set[str] = set()
            top_results = []
            for rank, chunk in enumerate(chunks, start=1):
                content = content_of(chunk)
                current = [term for term in expected if term in content]
                matched_terms.update(current)
                if current and first_rank is None:
                    first_rank = rank
                top_results.append(
                    {
                        "rank": rank,
                        "document_name": chunk.get("document_name") or chunk.get("docnm_kwd"),
                        "similarity": chunk.get("similarity"),
                        "matched_terms": current,
                        "preview": content[:300],
                    }
                )
            hit = first_rank is not None
            hit_count += int(hit)
            reciprocal_ranks.append(1 / first_rank if first_rank else 0)
            results.append(
                {
                    "experiment": key,
                    "dataset_id": dataset["id"],
                    "question": question_item["question"],
                    "expected_terms": expected,
                    "matched_terms": sorted(matched_terms),
                    "hit": hit,
                    "first_relevant_rank": first_rank,
                    "result_count": len(chunks),
                    "top_results": top_results,
                }
            )
            print(f"[{key}] {'HIT' if hit else 'MISS'} rank={first_rank}: {question_item['question']}")

        summaries[key] = {
            "dataset_id": dataset["id"],
            "chunk_tokens": experiment["chunk_token_num"],
            "overlap_percent": experiment["overlapped_percent"],
            "questions": len(config["questions"]),
            "hits": hit_count,
            "hit_rate": hit_count / len(config["questions"]),
            "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
            "document_count": len(documents),
            "chunk_count": dataset.get("chunk_count"),
        }

    payload = {"summaries": summaries, "results": results}
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "experiment",
                "question",
                "hit",
                "first_relevant_rank",
                "result_count",
                "expected_terms",
                "matched_terms",
            ],
        )
        writer.writeheader()
        for item in results:
            writer.writerow(
                {
                    **{key: item[key] for key in writer.fieldnames if key not in {"expected_terms", "matched_terms"}},
                    "expected_terms": " | ".join(item["expected_terms"]),
                    "matched_terms": " | ".join(item["matched_terms"]),
                }
            )
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
