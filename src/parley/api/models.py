from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ..., description="Natural-language question about NYC taxi data."
    )


class ChatResponse(BaseModel):
    route: str = Field(..., description="Which path answered: sql, rag, hybrid, error.")
    answer: str | None = Field(None, description="Natural-language answer.")
    sql: str | None = Field(None, description="The generated SQL, when the SQL path ran.")
    params: list | None = Field(None, description="Bound SQL parameters.")
    rows: list[dict] | None = Field(None, description="Result rows, when applicable.")
    context: str | None = Field(None, description="Retrieved doc context, for RAG.")
    metrics: dict | None = Field(None, description="Per-query token/cost/latency.")
