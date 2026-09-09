"""Leakage audit: lexical overlap between prompt examples and a golden dataset.

    uv run evals/audit.py --prompt prompts/intent-v5.md --dataset data/golden/intent-test.jsonl

For every quoted example in the prompt, prints the dataset row with the highest
token Jaccard similarity. Exit code 1 if any pair exceeds --max (default 0.3).

Why: prompt v2 of this project scored 100% partly because two of its inline
examples were near-verbatim copies of dataset rows (Jaccard 1.00 and 0.83).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STOP = set(
    "i my me the a an to is it and for of on in but that this at with you your do can if not no so be or "
    "was got one there before about up have has did didn t s m re ve".split()
)

# Prompt examples: lines like  - "text" -> label   or inline  ("text" → label)
# Quoted examples: "text" -> label, ("text" → label), or any quoted span of 4+ words
EXAMPLE_RE = re.compile(r'"((?:[^"\s]+\s+){3,}[^"\s]+)"')


def tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", s.lower()) if w not in STOP and len(w) > 1}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", type=Path, default=ROOT / "prompts/intent.md")
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/golden/intent.jsonl")
    ap.add_argument("--max", type=float, default=0.3, help="fail above this Jaccard")
    args = ap.parse_args()

    examples = EXAMPLE_RE.findall(args.prompt.read_text())
    rows = [json.loads(l) for l in args.dataset.read_text().splitlines() if l.strip()]
    if not examples:
        print("no quoted examples found in prompt")
        return 0

    worst = 0.0
    print(f"{len(examples)} prompt examples vs {len(rows)} dataset rows  (threshold {args.max})\n")
    for ex in examples:
        te = tokens(ex)
        best = max(rows, key=lambda r: jaccard(te, tokens(r["input"])))
        j = jaccard(te, tokens(best["input"]))
        worst = max(worst, j)
        flag = "LEAK" if j > args.max else "    "
        print(f"{flag} {j:.2f} [{best['id']}]  {ex!r}")
        print(f"          ~ {best['input']!r}  shared={sorted(te & tokens(best['input']))}")
    print(f"\nworst: {worst:.2f}")
    return 1 if worst > args.max else 0


if __name__ == "__main__":
    raise SystemExit(main())
