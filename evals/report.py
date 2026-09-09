"""Aggregate scored results into a human-readable report."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class Result:
    id: str
    input: str
    expected: str
    predicted: str
    raw: str
    correct: bool
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    completion_tokens: int = 0


def _f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def render(results: list[Result], labels: list[str]) -> str:
    n = len(results)
    correct = sum(r.correct for r in results)
    tokens = sum(r.completion_tokens for r in results)
    lines = [f"accuracy: {correct}/{n} = {correct / n:.1%}    completion tokens: {tokens} ({tokens / n:.1f}/example)", ""]

    # Per-label precision / recall / F1
    lines.append(f"{'label':<14}{'n':>4}{'prec':>8}{'rec':>8}{'f1':>8}")
    for label in labels:
        tp = sum(r.expected == label and r.predicted == label for r in results)
        fp = sum(r.expected != label and r.predicted == label for r in results)
        fn = sum(r.expected == label and r.predicted != label for r in results)
        p, rc, f = _f1(tp, fp, fn)
        lines.append(f"{label:<14}{tp + fn:>4}{p:>8.2f}{rc:>8.2f}{f:>8.2f}")
    lines.append("")

    # Confusion matrix (rows = expected, cols = predicted)
    cols = labels + ["invalid"]
    conf = Counter((r.expected, r.predicted) for r in results)
    head = "expected \\ pred"
    lines.append(f"{head:<16}" + "".join(f"{c[:8]:>9}" for c in cols))
    for e in labels:
        lines.append(f"{e:<16}" + "".join(f"{conf[(e, c)]:>9}" for c in cols))
    lines.append("")

    # Per-tag accuracy: this is where "92%" turns into "fails every negation"
    by_tag: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for t in r.tags:
            by_tag[t].append(r.correct)
    lines.append(f"{'tag':<14}{'n':>4}{'acc':>8}")
    for t, hits in sorted(by_tag.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        lines.append(f"{t:<14}{len(hits):>4}{sum(hits) / len(hits):>8.1%}")
    lines.append("")

    failures = [r for r in results if not r.correct]
    lines.append(f"failures: {len(failures)}")
    for r in failures:
        lines.append(f"  [{r.id}] expected={r.expected} predicted={r.predicted} raw={r.raw!r}")
        lines.append(f"      {r.input}")
        if r.notes:
            lines.append(f"      note: {r.notes}")
    return "\n".join(lines)
