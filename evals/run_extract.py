"""Run the structured-extraction golden set against a model and score per field.

    OLLAMA_API_KEY=x uv run evals/run_extract.py --base-url http://localhost:11434/v1 \
        --api-key-env OLLAMA_API_KEY --model qwen3.5:4b --reasoning-effort none

Reports: JSON validity rate, per-field accuracy, all-fields-correct rate, and
failures with the wrong fields highlighted. Same client/flags as run.py.
"""

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.run import classify  # noqa: E402
from evals.scorers import fields  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def user_message(row: dict, given_intent: bool) -> str:
    if given_intent:
        return f"Intent (already classified upstream): {row['expected']['intent']}\n\nMessage:\n{row['input']}"
    return row["input"]


async def run(rows, client_kw, params, system, concurrency, given_intent=False):
    from openai import AsyncOpenAI

    client = AsyncOpenAI(**client_kw)
    sem = asyncio.Semaphore(concurrency)
    outs = await asyncio.gather(*(classify(client, params, system, user_message(r, given_intent), sem) for r in rows))
    skip = {"intent"} if given_intent else set()
    results = []
    for row, (raw, tokens) in zip(rows, outs):
        pred = fields.parse(raw)
        sc = fields.score(row["expected"], pred, skip)
        results.append(
            {
                "id": row["id"],
                "input": row["input"],
                "expected": row["expected"],
                "predicted": pred,
                "raw": raw,
                "parsed": pred is not None,
                "field_correct": sc,
                "correct": all(sc.values()),
                "tags": row["tags"],
                "notes": row.get("notes", ""),
                "completion_tokens": tokens,
            }
        )
    return results


def render(results):
    n = len(results)
    parsed = sum(r["parsed"] for r in results)
    full = sum(r["correct"] for r in results)
    tokens = sum(r["completion_tokens"] for r in results)
    lines = [
        f"json valid: {parsed}/{n} = {parsed / n:.1%}    all fields correct: {full}/{n} = {full / n:.1%}    completion tokens: {tokens} ({tokens / n:.1f}/example)",
        "",
        f"{'field':<11}{'acc':>8}   most common confusions (expected -> predicted)",
    ]
    scored = [f for f in fields.FIELDS if f in results[0]["field_correct"]]
    for f in scored:
        ok = sum(r["field_correct"][f] for r in results)
        conf = Counter(
            (str(fields.NORM[f](r["expected"].get(f))), str(fields.NORM[f]((r["predicted"] or {}).get(f))))
            for r in results
            if not r["field_correct"][f]
        )
        top = ", ".join(f"{e}->{p} x{c}" for (e, p), c in conf.most_common(3))
        lines.append(f"{f:<11}{ok / n:>8.1%}   {top}")
    lines.append("")

    by_tag = defaultdict(list)
    for r in results:
        for t in r["tags"]:
            by_tag[t].append(r["correct"])
    lines.append(f"{'tag':<18}{'n':>4}{'all-correct':>13}")
    for t, hits in sorted(by_tag.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        lines.append(f"{t:<18}{len(hits):>4}{sum(hits) / len(hits):>13.1%}")
    lines.append("")

    fails = [r for r in results if not r["correct"]]
    lines.append(f"failures: {len(fails)}")
    for r in fails:
        wrong = [f for f in r["field_correct"] if not r["field_correct"][f]]
        if not r["parsed"]:
            lines.append(f"  [{r['id']}] UNPARSEABLE raw={r['raw'][:100]!r}")
            continue
        diffs = ", ".join(f"{f}: {r['expected'].get(f)!r} -> {(r['predicted'] or {}).get(f)!r}" for f in wrong)
        lines.append(f"  [{r['id']}] {diffs}")
        lines.append(f"      {r['input'][:110]!r}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=ROOT / "data/golden/extraction.jsonl", type=Path)
    ap.add_argument("--prompt", default=ROOT / "prompts/extract.md", type=Path)
    ap.add_argument("--model", default=os.environ.get("EVAL_MODEL", "gpt-4o-mini"))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--no-think", action="store_true")
    ap.add_argument("--reasoning-effort")
    ap.add_argument("--json-mode", action="store_true", help='send response_format={"type":"json_object"}')
    ap.add_argument("--given-intent", action="store_true", help="pipeline mode: pass the gold intent as input, do not score it")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.dataset.resolve().read_text().splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"{args.api_key_env} is not set", file=sys.stderr)
        return 1

    client_kw = {"api_key": api_key, "base_url": args.base_url}
    params = {"model": args.model, "temperature": args.temperature, "max_tokens": args.max_tokens}
    extra = {}
    if args.no_think:
        extra["thinking"] = {"type": "disabled"}
    if extra:
        params["extra_body"] = extra
    if args.reasoning_effort:
        params["reasoning_effort"] = args.reasoning_effort
    if args.json_mode:
        params["response_format"] = {"type": "json_object"}

    results = asyncio.run(run(rows, client_kw, params, args.prompt.resolve().read_text(), args.concurrency, args.given_intent))
    meta = {
        "dataset": str(args.dataset.resolve().relative_to(ROOT)),
        "prompt": str(args.prompt.resolve().relative_to(ROOT)),
        "base_url": args.base_url or "https://api.openai.com/v1",
        **{k: v for k, v in params.items() if k != "extra_body"},
        "json_mode": args.json_mode,
        "given_intent": args.given_intent,
        "n": len(results),
        "all_correct": sum(r["correct"] for r in results) / len(results),
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print(f"dataset: {meta['dataset']}  prompt: {meta['prompt']}  model: {args.model}  json_mode: {args.json_mode}")
    print(render(results))

    out = args.out.resolve() if args.out else ROOT / "results" / "extraction" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{args.model.replace('/', '_')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.write(json.dumps({"meta": meta}) + "\n")
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0 if all(r["correct"] for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
