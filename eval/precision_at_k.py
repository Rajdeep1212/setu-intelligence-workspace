import asyncio
import json
from pathlib import Path

from app.db import AsyncSessionLocal
from app.retrieval.pipeline import retrieve

EVAL_SET_PATH = Path(__file__).parent / "eval_set.jsonl"


def _load_eval_set() -> list[dict]:
    if not EVAL_SET_PATH.exists() or not EVAL_SET_PATH.read_text(encoding='utf-8').strip():
        return []
    return [
        json.loads(line)
        for line in EVAL_SET_PATH.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


async def evaluate(k: int = 5) -> None:
    rows = _load_eval_set()
    if not rows:
        print("No eval rows found.")
        return

    metrics = {
        "overall": {"p1": [], "p3": [], "p5": [], "r5": [], "mrr5": []},
        "bn": {"p1": [], "p3": [], "p5": [], "r5": [], "mrr5": []},
        "hi": {"p1": [], "p3": [], "p5": [], "r5": [], "mrr5": []},
        "en": {"p1": [], "p3": [], "p5": [], "r5": [], "mrr5": []},
    }

    per_query_results = []

    async with AsyncSessionLocal() as session:
        for row in rows:
            query = row["query"]
            lang = row.get("language")
            relevant_ids = set(row["relevant_chunk_ids"])
            
            results = await retrieve(session, query, lang, candidate_k=20, final_k=k)
            retrieved_ids = [r["id"] for r in results]
            
            p1 = len(set(retrieved_ids[:1]) & relevant_ids) / 1.0
            p3 = len(set(retrieved_ids[:3]) & relevant_ids) / 3.0
            p5 = len(set(retrieved_ids[:5]) & relevant_ids) / 5.0
            r5 = len(set(retrieved_ids[:5]) & relevant_ids) / len(relevant_ids) if relevant_ids else 0.0
            
            mrr5 = 0.0
            for i, rid in enumerate(retrieved_ids[:5]):
                if rid in relevant_ids:
                    mrr5 = 1.0 / (i + 1)
                    break
            
            metrics["overall"]["p1"].append(p1)
            metrics["overall"]["p3"].append(p3)
            metrics["overall"]["p5"].append(p5)
            metrics["overall"]["r5"].append(r5)
            metrics["overall"]["mrr5"].append(mrr5)
            
            if lang in metrics:
                metrics[lang]["p1"].append(p1)
                metrics[lang]["p3"].append(p3)
                metrics[lang]["p5"].append(p5)
                metrics[lang]["r5"].append(r5)
                metrics[lang]["mrr5"].append(mrr5)
                
            per_query_results.append({
                "query": query,
                "language": lang,
                "relevant_ids": list(relevant_ids),
                "retrieved_ids": retrieved_ids,
                "hit": mrr5 > 0,
                "mrr": mrr5
            })

    def print_metrics(name, data):
        if not data["p1"]: return
        print(f"--- {name.upper()} (n={len(data['p1'])}) ---")
        print(f"P@1:  {sum(data['p1'])/len(data['p1']):.3f}")
        print(f"P@3:  {sum(data['p3'])/len(data['p3']):.3f}")
        print(f"P@5:  {sum(data['p5'])/len(data['p5']):.3f}")
        print(f"R@5:  {sum(data['r5'])/len(data['r5']):.3f}")
        print(f"MRR@5:{sum(data['mrr5'])/len(data['mrr5']):.3f}\n")

    print_metrics("overall", metrics["overall"])
    print_metrics("bn", metrics["bn"])
    print_metrics("hi", metrics["hi"])
    print_metrics("en", metrics["en"])
    
    with open("eval_results.json", "w", encoding='utf-8') as f:
        json.dump(per_query_results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(evaluate())
