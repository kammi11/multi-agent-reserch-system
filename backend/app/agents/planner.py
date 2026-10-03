import json

from app.schemas.models import ResearchDepth, ResearchPlan
from app.services import llm

SYSTEM = """TASK: research_plan
You are the Research Planner agent in a multi-agent research system.
Given a research question and a research depth, produce a JSON object with:
research_question, objectives (list[str]), subquestions (list[str]),
search_strategy (list[str] of search query seeds), required_source_types
(list of: academic, news, government, official_documentation, general_web),
research_depth. Respond with ONLY the JSON object."""


async def plan_research(question: str, depth: ResearchDepth) -> ResearchPlan:
    user = json.dumps({"question": question, "depth": depth.value})
    data = await llm.complete(SYSTEM, user, expect_json=True)
    data.setdefault("research_question", question)
    data.setdefault("research_depth", depth.value)
    return ResearchPlan(**data)
