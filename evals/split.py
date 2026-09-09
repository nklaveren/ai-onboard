"""Merge golden source files and produce a stratified dev/test split.

    uv run evals/split.py                 # writes intent-all / intent-dev / intent-test
    uv run evals/split.py --test-frac 0.4 --seed 42

dev  -> iterate on prompts, look at failures freely.
test -> run once per prompt version, never tune against it.

The split is deterministic (seeded) and stratified by label so both halves
keep the same class balance. Outputs are committed so everyone scores against
the same files; re-run only when the source set changes, and treat that as a
new test set (previous numbers are not comparable).
"""

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "data/golden"
SOURCES = ["intent.jsonl", "intent-heldout.jsonl", "intent-new.jsonl", "intent-gen-minimax.jsonl"]


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def dump(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test-frac", type=float, default=0.4)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows: list[dict] = []
    for name in SOURCES:
        for r in load(GOLDEN / name):
            if r.get("reviewed") is False:
                raise SystemExit(f"{name}: {r['id']} is not reviewed; refusing to split unreviewed labels")
            r.setdefault("source", name)
            rows.append(r)
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ids across sources"

    # Sticky: ids already in dev/test stay where they are, even if their label
    # changed. Only new ids get assigned, stratified by label. Moving examples
    # between splits would make results across versions incomparable.
    prev_dev = {r["id"] for r in load(GOLDEN / "intent-dev.jsonl")} if (GOLDEN / "intent-dev.jsonl").exists() else set()
    prev_test = {r["id"] for r in load(GOLDEN / "intent-test.jsonl")} if (GOLDEN / "intent-test.jsonl").exists() else set()

    dev = [r for r in rows if r["id"] in prev_dev]
    test = [r for r in rows if r["id"] in prev_test]
    new = [r for r in rows if r["id"] not in prev_dev | prev_test]

    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in new:
        by_label[r["expected"]].append(r)
    rng = random.Random(args.seed)
    for label in sorted(by_label):
        group = sorted(by_label[label], key=lambda r: r["id"])
        rng.shuffle(group)
        k = round(len(group) * args.test_frac)
        test += group[:k]
        dev += group[k:]
    if new:
        print(f"assigned {len(new)} new ids; {len(prev_dev) + len(prev_test)} kept in place")
    dev.sort(key=lambda r: r["id"])
    test.sort(key=lambda r: r["id"])

    dump(GOLDEN / "intent-all.jsonl", sorted(rows, key=lambda r: r["id"]))
    dump(GOLDEN / "intent-dev.jsonl", dev)
    dump(GOLDEN / "intent-test.jsonl", test)

    def dist(xs):
        return dict(sorted(Counter(r["expected"] for r in xs).items()))

    print(f"all  {len(rows):>4}  {dist(rows)}")
    print(f"dev  {len(dev):>4}  {dist(dev)}")
    print(f"test {len(test):>4}  {dist(test)}")


if __name__ == "__main__":
    main()
