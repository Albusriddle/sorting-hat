
from __future__ import annotations
"""Deterministic house judgement. The model NEVER returns a house."""
from collections import Counter
from typing import Iterable

from .config import settings
from .persona import display_name

DIMENSIONS = ("courage", "ambition", "wisdom", "loyalty")


def lev(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if not la:
        return lb
    if not lb:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def quote_present(quote: str, text: str, k: int = 2) -> bool:
    if not quote:
        return False
    if quote in text:
        return True
    n = len(quote)
    if n > len(text):
        return lev(quote, text) <= k
    for i in range(0, len(text) - n + 1):
        if lev(quote, text[i:i + n]) <= k:
            return True
    return False


def validate_evidence(evidence: Iterable[dict], text: str, k: int = 2) -> tuple[bool, list[str]]:
    bad = []
    for i, ev in enumerate(evidence):
        q = str(ev.get("quote", "")).strip()
        if not quote_present(q, text, k):
            bad.append(f"evidence[{i}] quote not found")
    return (not bad), bad


def decide(text: str, payload: dict, recent: list[str], *,
           penalty: float | None = None,
           max_share: float | None = None,
           min_history: int | None = None) -> dict:
    """payload = {"evidence":[{quote,trait,why}], "scores":{dim:num}, "line": str}"""
    penalty = settings.recent3_penalty if penalty is None else penalty
    max_share = settings.max_share if max_share is None else max_share
    min_history = settings.min_history_for_balance if min_history is None else min_history

    if payload.get("insufficient"):
        return {"house": None, "insufficient": True, "reasons": [], "scores": {},
                "line": "", "quote_ok": False, "quote_failures": ["insufficient"],
                "degraded": True}

    scores = {d: float(payload.get("scores", {}).get(d, 0.0)) for d in DIMENSIONS}
    if max(scores.values()) <= 0:
        return {"house": None, "insufficient": True, "reasons": [], "scores": scores,
                "line": "", "quote_ok": False, "quote_failures": ["all zero"],
                "degraded": True}

    evidence = list(payload.get("evidence", []))
    if not evidence:
        return {"house": None, "insufficient": True, "reasons": [], "scores": scores,
                "line": "", "quote_ok": False, "quote_failures": ["no evidence"],
                "degraded": True}
    reasons = [str(e.get("quote", "")).strip() for e in evidence][:3]
    reasons = [r for r in reasons if r] or [text[:12]]

    # 只有攒够历史才做配平；演示期（<10 次）不做轮转，保证同句同果。
    if len(recent) >= min_history:
        cand = max(scores, key=scores.get)
        if len(set(recent[-3:])) == 1 and recent[-1] == cand:
            scores[cand] *= penalty

    house = max(scores, key=scores.get)

    if len(recent) >= min_history:
        cnt = Counter(recent)
        share = cnt[house] / max(1, len(recent))
        if share > max_share:
            for h, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
                if h != house:
                    house = h
                    break

    ok, bad = validate_evidence(evidence, text)
    line = str(payload.get("line") or f"那就……去{display_name(house)}吧。")
    return {
        "house": house,
        "reasons": reasons,
        "scores": scores,
        "line": line,
        "quote_ok": ok,
        "quote_failures": bad,
        "degraded": (not ok),
        "insufficient": False,
    }
