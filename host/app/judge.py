
from __future__ import annotations
"""Deterministic house judgement. The model NEVER returns a house."""
from collections import Counter
from typing import Iterable

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
    """True if quote can be found in text with <= k edits (sliding window)."""
    if not quote:
        return False
    if quote in text:
        return True
    n = len(quote)
    if n > len(text):
        return lev(quote, text) <= k
    best = 10**9
    for i in range(0, len(text) - n + 1):
        d = lev(quote, text[i:i + n])
        if d < best:
            best = d
            if best <= k:
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
           penalty: float = 0.85, max_share: float | None = None) -> dict:
    """payload = {"evidence":[{quote,trait,why}], "scores":{dim:num}, "line": str}"""
    scores = {d: float(payload.get("scores", {}).get(d, 0.0)) for d in DIMENSIONS}
    evidence = list(payload.get("evidence", []))
    reasons = [str(e.get("quote", "")).strip() for e in evidence][:3]
    reasons = [r for r in reasons if r] or [text[:12]]

    # anti-cluster: three in a row -> penalise
    cand = max(scores, key=scores.get)
    if len(recent) >= 3 and len(set(recent[-3:])) == 1 and recent[-1] == cand:
        scores[cand] *= penalty

    # share cap: if one house already dominates the last N, force the runner-up
    house = max(scores, key=scores.get)
    if max_share is not None and recent:
        cnt = Counter(recent)
        share = cnt[house] / max(1, len(recent))
        if share > max_share:
            alt = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            for h, _ in alt:
                if h != house:
                    house = h
                    break

    ok, bad = validate_evidence(evidence, text)
    line = str(payload.get("line") or f"那就……去{house}吧。")
    return {
        "house": house,
        "reasons": reasons,
        "scores": scores,
        "line": line,
        "quote_ok": ok,
        "quote_failures": bad,
        "degraded": (not ok),
    }
