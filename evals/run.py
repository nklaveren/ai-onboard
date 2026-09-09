"""Run a golden dataset against a model and score it.

Usage:
    uv run evals/run.py                       # intent dataset, default model
    uv run evals/run.py --model gpt-4o        # different model
    uv run evals/run.py --tag negation        # only examples with this tag
    uv run evals/run.py --check               # validate dataset, no API calls

    # any OpenAI-compatible endpoint, e.g. MiniMax with reasoning turned off:
    uv run evals/run.py --base-url https://api.minimax.io/v1 --api-key-env MINIMAX_API_KEY \
        --model MiniMax-M3 --no-think

    # local Ollama (Qwen3.5), thinking off:
    OLLAMA_API_KEY=x uv run evals/run.py --base-url http://localhost:11434/v1 \
        --api-key-env OLLAMA_API_KEY --model qwen3.5:4b --reasoning-effort none

Defaults: OPENAI_API_KEY / OPENAI_BASE_URL.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.report import Result, render  # noqa: E402
from evals.scorers import exact  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LABELS: list[str] = []  # filled from --labels or inferred from the dataset
LABEL_SETS = {
    "intent": ["cancellation", "billing", "login", "shipping", "other"],
    "injection": ["injection", "benign"],
}
REQUIRED_KEYS = {"id", "input", "expected", "tags"}


def load_dataset(path: Path) -> list[dict]:
    rows = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = REQUIRED_KEYS - row.keys()
        if missing:
            raise ValueError(f"{path}:{lineno} missing keys {sorted(missing)}")
        rows.append(row)
    global LABELS
    if not LABELS:
        seen = {r["expected"] for r in rows}
        LABELS = next((v for v in LABEL_SETS.values() if seen <= set(v)), sorted(seen))
    bad = [r for r in rows if r["expected"] not in LABELS]
    if bad:
        raise ValueError(f"{path}: labels not in {LABELS}: {sorted({r['expected'] for r in bad})}")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids in dataset")
    return rows


def check(rows: list[dict]) -> None:
    from collections import Counter

    print(f"{len(rows)} examples, {len(LABELS)} labels")
    print("by label:", dict(Counter(r["expected"] for r in rows)))
    print("by tag:  ", dict(Counter(t for r in rows for t in r["tags"])))


async def classify(client, params: dict, system: str, text: str, sem: asyncio.Semaphore) -> str:
    from openai import RateLimitError

    async with sem:
        for attempt in range(6):
            try:
                resp = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": text},
                    ],
                    **params,
                )
                break
            except RateLimitError:
                if attempt == 5:
                    raise
                wait = 30 * 2**attempt
                print(f"429, waiting {wait}s", file=sys.stderr)
                await asyncio.sleep(wait)
    usage = resp.usage.completion_tokens if resp.usage else 0
    return resp.choices[0].message.content or "", usage


async def run(rows: list[dict], client_kw: dict, params: dict, system: str, concurrency: int) -> list[Result]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(**client_kw)
    sem = asyncio.Semaphore(concurrency)
    outs = await asyncio.gather(*(classify(client, params, system, r["input"], sem) for r in rows))
    results = []
    for row, (raw, tokens) in zip(rows, outs):
        predicted = exact.normalize(raw, set(LABELS))
        results.append(
            Result(
                id=row["id"],
                input=row["input"],
                expected=row["expected"],
                predicted=predicted,
                raw=raw,
                correct=exact.score(row["expected"], predicted),
                tags=row["tags"],
                notes=row.get("notes", ""),
                completion_tokens=tokens,
            )
        )
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=ROOT / "data/golden/intent.jsonl", type=Path)
    ap.add_argument("--prompt", default=ROOT / "prompts/intent.md", type=Path)
    ap.add_argument("--model", default=os.environ.get("EVAL_MODEL", "gpt-4o-mini"))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY", help="env var holding the API key")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=256, help="reasoning models need room; 10 is not enough")
    ap.add_argument("--no-think", action="store_true", help='send thinking={"type":"disabled"} (MiniMax)')
    ap.add_argument("--reasoning-effort", help="standard OpenAI param; 'none' disables thinking on Ollama/Qwen3.5")
    ap.add_argument("--labels", help="comma-separated label set (default: inferred from dataset)")
    ap.add_argument("--tag", help="only run examples carrying this tag")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", type=Path, help="write per-example results as JSONL (default: results/<ts>-<model>.jsonl)")
    ap.add_argument("--check", action="store_true", help="validate the dataset and exit")
    args = ap.parse_args()

    global LABELS
    if args.labels:
        LABELS = args.labels.split(",")
    args.dataset = args.dataset.resolve()
    args.prompt = args.prompt.resolve()
    rows = load_dataset(args.dataset)
    if args.check:
        check(rows)
        return 0
    if args.tag:
        rows = [r for r in rows if args.tag in r["tags"]]
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("no examples selected", file=sys.stderr)
        return 1
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"{args.api_key_env} is not set", file=sys.stderr)
        return 1

    client_kw = {"api_key": api_key, "base_url": args.base_url}
    params = {"model": args.model, "temperature": args.temperature, "max_tokens": args.max_tokens}
    if args.no_think:
        params["extra_body"] = {"thinking": {"type": "disabled"}}
    if args.reasoning_effort:
        params["reasoning_effort"] = args.reasoning_effort

    system = args.prompt.read_text()
    results = asyncio.run(run(rows, client_kw, params, system, args.concurrency))

    meta = {
        "dataset": str(args.dataset.relative_to(ROOT)),
        "prompt": str(args.prompt.relative_to(ROOT)),
        "base_url": args.base_url or "https://api.openai.com/v1",
        **params,
        "n": len(results),
        "accuracy": sum(r.correct for r in results) / len(results),
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print("  ".join(f"{k}: {v}" for k, v in meta.items() if k in ("dataset", "prompt", "model", "base_url")))
    print(render(results, LABELS))

    out = args.out.resolve() if args.out else None
    if out is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = ROOT / "results" / f"{ts}-{args.model.replace('/', '_')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.write(json.dumps({"meta": meta}) + "\n")
        for r in results:
            f.write(json.dumps(r.__dict__) + "\n")
    print(f"\nwrote {out.relative_to(ROOT)}")

    return 0 if all(r.correct for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
