from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ..., description="Natural-language question about NYC taxi data."
    )
    thread_id: str | None = Field(
        None, description="Conversation id; omit to start a new one."
    )
    user_id: str | None = Field(None, description="Scopes long-term memory to a user.")


class ChatResponse(BaseModel):
    route: str = Field(..., description="Which path answered: sql, rag, hybrid, error.")
    thread_id: str | None = Field(None, description="Conversation id to continue.")
    reasoning: str | None = Field(None, description="Why the router chose this path.")
    answer: str | None = Field(None, description="Natural-language answer.")
    sql: str | None = Field(None, description="The generated SQL, when the SQL path ran.")
    params: list | None = Field(None, description="Bound SQL parameters.")
    rows: list[dict] | None = Field(None, description="Result rows, when applicable.")
    context: str | None = Field(None, description="Retrieved doc context, for RAG.")
    metrics: dict | None = Field(None, description="Per-query token/cost/latency.")
