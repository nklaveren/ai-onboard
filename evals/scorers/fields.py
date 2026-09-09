"""Per-field scorer for structured extraction."""

import json
import re

FIELDS = ["intent", "order_id", "amount", "currency", "deadline", "sentiment", "action"]


def parse(raw: str) -> dict | None:
    """Extract the first JSON object from a model response. None if unparseable."""
    text = re.sub(r"<think>.*?(</think>|$)", "", raw, flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _norm_id(v):
    if v is None or v == "":
        return None
    return str(v).strip().lstrip("#").upper()


def _norm_amount(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    m = re.search(r"-?\d[\d,]*\.?\d*", str(v))
    return round(float(m.group(0).replace(",", "")), 2) if m else None


def _norm_str(v):
    return None if v is None or v == "" else str(v).strip().lower()


def _norm_deadline(v):
    """Deadline is free text; score presence + loose containment rather than exact match."""
    if v is None or str(v).strip().lower() in ("", "null", "none"):
        return None
    return re.sub(r"[^a-z0-9 ]", "", str(v).lower()).strip()


NORM = {
    "intent": _norm_str,
    "order_id": _norm_id,
    "amount": _norm_amount,
    "currency": lambda v: None if v in (None, "") else str(v).strip().upper(),
    "deadline": _norm_deadline,
    "sentiment": _norm_str,
    "action": _norm_str,
}


def score(expected: dict, predicted: dict | None, skip: set[str] = frozenset()) -> dict[str, bool]:
    """Field -> correct. Unparseable output scores every field as wrong.
    Fields in `skip` (e.g. intent supplied by an upstream stage) are not scored."""
    fs = [f for f in FIELDS if f not in skip]
    if predicted is None:
        return {f: False for f in fs}
    out = {}
    for f in fs:
        e, p = NORM[f](expected.get(f)), NORM[f](predicted.get(f))
        if f == "deadline" and e and p:
            out[f] = e in p or p in e  # both mention the constraint; wording may differ
        else:
            out[f] = e == p
    return out
