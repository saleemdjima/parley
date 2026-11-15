"""LLM-as-judge verification for answers that make factual claims.

The judge is grounded: it sees the evidence the answer was built from (the SQL
result rows and/or the retrieved documentation) and either confirms the answer or
rewrites it to match. Greetings/clarifications carry no factual claim and skip it.
"""

import logging

from pydantic import BaseModel, Field

from parley import llm

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """You verify an assistant's answer against the evidence it was based on.

Question: {question}

Evidence (the ground truth the answer must be consistent with):
{evidence}

Proposed answer: {answer}

Is the proposed answer consistent with the evidence? Sensible rounding, natural
phrasing, reasonable summarization, and labels implied by the question or SQL (e.g. the
unit being counted) are all fine -- only mark it unsupported if a figure or claim
genuinely contradicts the evidence or cannot be derived from it. If consistent, set
supported=true and return the answer unchanged. If not, set supported=false and rewrite
the answer so it matches the evidence, using only what the evidence shows."""


class Verdict(BaseModel):
    supported: bool = Field(
        description="True if the answer is fully supported by the evidence"
    )
    answer: str = Field(
        description="The answer unchanged if supported, otherwise a corrected, "
        "evidence-grounded rewrite"
    )


def judge(question: str, answer: str, evidence: str) -> Verdict:
    prompt = JUDGE_PROMPT.format(question=question, evidence=evidence, answer=answer)
    verdict = llm.extract(prompt, Verdict)
    logger.debug("judge supported=%s", verdict.supported)
    return verdict
