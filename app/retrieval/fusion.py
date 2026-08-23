"""Reciprocal rank fusion — Week 2.

Merges the dense and keyword result lists into one ranked candidate pool
without needing to normalize cosine similarity against ts_rank (which live
on completely different scales — RRF only looks at rank position, not the
raw scores, which sidesteps that problem entirely).
"""

from __future__ import annotations


def reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Standard RRF: score(doc) = sum over lists of 1 / (k + rank_in_list).
    k=60 is the commonly-cited default from the original RRF paper and is a
    reasonable starting point; not something to tune until you have an eval
    set large enough to trust the signal (50+ queries).
    """
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            key = item["id"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            items.setdefault(key, item)

    fused = sorted(items.values(), key=lambda item: scores[item["id"]], reverse=True)
    for item in fused:
        item["rrf_score"] = scores[item["id"]]
    return fused
