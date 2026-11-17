import pytest
from app import judge


def payload(**scores):
    base = {"courage": 5, "ambition": 5, "wisdom": 5, "loyalty": 5}
    base.update(scores)
    return {"evidence": [{"quote": "我不想再解释了", "trait": "loyalty", "why": "重复"}],
            "scores": base, "line": "唔……"}


def test_argmax():
    v = judge.decide("我不想再解释了", payload(courage=9), [])
    assert v["house"] == "courage"


def test_anti_cluster_only_after_history():
    recent = ["courage", "ambition"] * 5          # len=10, last 3 = ambition,courage,ambition
    v = judge.decide("我不想再解释了", payload(courage=8, ambition=7.6),
                     recent + ["courage", "courage", "courage"], penalty=0.85,
                     min_history=10)
    assert v["house"] == "ambition"


def test_balance_is_off_by_default():
    """演示默认：同句同果（MIN_HISTORY_FOR_BALANCE=9999，平衡不生效）。"""
    from app.config import settings
    assert settings.min_history_for_balance > settings.history_window
    recent = ["courage"] * 10
    v = judge.decide("我不想再解释了", payload(courage=9, wisdom=8), recent)
    assert v["house"] == "courage"


def test_no_penalty_under_min_history():
    v = judge.decide("我不想再解释了", payload(courage=8, ambition=7.6),
                     ["courage", "courage", "courage"], penalty=0.85, min_history=10)
    assert v["house"] == "courage"


def test_quote_exact_and_fuzzy():
    assert judge.quote_present("我不想再解释了", "对，我不想再解释了。")
    assert judge.quote_present("我不想在解释了", "对，我不想再解释了。", k=2)
    assert not judge.quote_present("完全无关的一句话在这里", "对，我不想再解释了。", k=2)


def test_quote_failure_marks_degraded():
    p = payload()
    p["evidence"] = [{"quote": "这句话他根本没说过", "trait": "courage", "why": "x"}]
    v = judge.decide("对，我不想再解释了。", p, [])
    assert v["degraded"] is True
    assert v["quote_failures"]


def test_share_cap_forces_runner_up():
    v = judge.decide("对，我不想再解释了。", payload(courage=9, wisdom=8),
                     ["courage"] * 10, max_share=0.4, min_history=10)
    assert v["house"] == "wisdom"


def test_insufficient_returns_no_house():
    v = judge.decide("嗯。", {"insufficient": True}, [])
    assert v["insufficient"] is True and v["house"] is None


def test_empty_evidence_is_insufficient():
    v = judge.decide("随便说点什么", {"scores": {"courage": 3, "ambition": 3,
                                                "wisdom": 3, "loyalty": 3}}, [])
    assert v["insufficient"] is True and v["house"] is None
