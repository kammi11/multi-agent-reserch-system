import json

from app.services import llm

SYSTEM = """TASK: query_generation
You are the Search Query Agent. Given the research question and
subquestions, generate a small set of distinct, non-duplicate search
queries (short keyword-style, not full sentences) that would surface
good evidence. Respond with ONLY JSON: {"queries": ["...", "..."]}"""


async def generate_queries(question: str, subquestions: list[str], max_queries: int) -> list[str]:
    user = json.dumps({"question": question, "subquestions": subquestions, "max_queries": max_queries})
    data = await llm.complete(SYSTEM, user, expect_json=True)
    queries = data.get("queries") or [question]
    # Final dedupe/cap safety net regardless of provider behavior.
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = q.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(q.strip())
    return out[:max_queries] or [question]
