class AgentError(Exception):
    """Base class for parley errors intended to surface to callers."""


class InvalidQuestion(AgentError):
    """The incoming question failed validation."""


class EngineError(AgentError):
    """A query engine failed to run the built query."""


class RetrievalError(AgentError):
    """The RAG retrieval step failed."""
