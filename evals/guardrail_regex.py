"""Regex baseline for the injection guardrail. Zero latency, zero cost.

    uv run evals/guardrail_regex.py                 # scores data/golden/injection.jsonl
    uv run evals/guardrail_regex.py --dataset ...

Purpose: any LLM-based guardrail has to beat this on the same golden set,
otherwise it is not worth the latency. Also useful as the first layer of a
cascade: regex catches the obvious, the model handles the rest.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.report import Result, render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

PATTERNS = [
    r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|all|your|earlier)\b.{0,40}\b(instructions?|rules?|prompts?|messages?|everything)\b",
    r"\b(ignore|disregard|forget)\s+(all\s+)?(previous|prior)\s+instructions\b",
    r"\bsystem\s*prompt\b",
    r"\b(reveal|print|show|list|repeat|output)\b.{0,40}\b(your|the)\b.{0,20}\b(instructions|rules|prompt|categories)\b",
    r"\byou are now\b.{0,40}\b(ai|assistant|dan|model|bot)\b",
    r"\b(respond|reply|answer|output|say)\s+(only\s+)?(with\s+)?(the\s+word\s+)?['\"]?(billing|shipping|login|cancellation|other)['\"]?\b",
    r"\bfrom now on\b.{0,40}\b(respond|reply|answer|output|you)\b",
    r"^\s*(system|developer|assistant|admin)\s*[:\]]",
    r"<\|im_start\|>|<\|im_end\|>|\[assistant:|\{\{\s*system",
    r"\b(developer|operator|qa team|admin)\b.{0,60}\b(override|update|updating|instructions|misclassify|set category)\b",
    r"\bpretend\b.{0,60}\b(said|classify|instructions|rules)\b",
    r"\bas if your (instructions|rules)\b",
    r"\bend of user message\b",
    r"^[A-Za-z0-9+/=]{24,}\s*\(decode",
    r"\b1gn0re\b|\bpr3vious\b|i\s+g\s+n\s+o\s+r\s+e",
    r"\bignora\b.{0,30}\binstrucciones\b",
    r"\b(if you are|to the) (a |an )?(language model|ai|llm|assistant)\b",
    r"\bmisclassify\b",
    r"\b(mark as|set) (resolved|category)\b",
    r"\bstop classifying\b",
]
RX = [re.compile(p, re.I | re.S) for p in PATTERNS]


def predict(text: str) -> str:
    return "injection" if any(r.search(text) for r in RX) else "benign"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/golden/injection.jsonl")
    args = ap.parse_args()
    rows = [json.loads(l) for l in args.dataset.read_text().splitlines() if l.strip()]
    results = [
        Result(r["id"], r["input"], r["expected"], predict(r["input"]), "regex", predict(r["input"]) == r["expected"], r["tags"], r.get("notes", ""))
        for r in rows
    ]
    print(f"dataset: {args.dataset.resolve().relative_to(ROOT)}  model: regex-baseline ({len(PATTERNS)} patterns)")
    print(render(results, ["injection", "benign"]))
    return 0 if all(r.correct for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
