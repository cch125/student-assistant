from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PROJECT_ROOT / "outputs" / "content_snapshot.json"


def snapshot() -> dict[str, str]:
    result = {}
    for directory in (PROJECT_ROOT / "data" / "cleaned" / "ragflow_markdown", PROJECT_ROOT / "data" / "cleaned" / "service_cards"):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            result[str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the public-data refresh pipeline and record content changes.")
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--max-pages-per-seed", type=int, default=12)
    parser.add_argument("--sync-ragflow", action="store_true")
    args = parser.parse_args()

    before = snapshot()
    run(
        "crawler/jnu_crawler.py",
        "--max-pages",
        str(args.max_pages),
        "--depth",
        str(args.depth),
        "--max-pages-per-seed",
        str(args.max_pages_per_seed),
    )
    run("cleaner/clean_jnu_docs.py")
    run("cleaner/build_service_cards.py")
    run("multimodal/postprocess_mineru.py")
    run("scripts/quality_gate.py", "--check-links")
    if args.sync_ragflow:
        run("ragflow/import_core_services.py")
        run(
            "ragflow/import_experiment_pipelines.py",
            "--refresh-prefix",
            "multimodal__",
            "--refresh-changed",
            "--prune",
        )

    after = snapshot()
    state = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(path for path in set(before) & set(after) if before[path] != after[path]),
        "unchanged": sum(before.get(path) == digest for path, digest in after.items()),
        "hashes": after,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in state.items() if key != "hashes"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
