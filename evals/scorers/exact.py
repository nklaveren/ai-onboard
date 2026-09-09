"""Exact-match scorer for closed-label classification."""

import re

INVALID = "invalid"
_THINK = re.compile(r"<think>.*?(</think>|$)", re.DOTALL)


def normalize(raw: str, labels: set[str]) -> str:
    """Map a model response to a known label, or INVALID.

    Strips inline reasoning blocks (<think>...</think>) emitted by some
    providers, then tolerates surrounding whitespace, quotes, backticks,
    punctuation and casing. If the response contains more than one label or
    no label at all, it is INVALID: the prompt asked for exactly one category.
    """
    cleaned = re.sub(r"[`\"'.\s]+", " ", _THINK.sub("", raw).lower()).strip()
    if cleaned in labels:
        return cleaned
    found = {w for w in re.findall(r"[a-z_]+", cleaned) if w in labels}
    return found.pop() if len(found) == 1 else INVALID


def score(expected: str, predicted: str) -> bool:
    return expected == predicted
