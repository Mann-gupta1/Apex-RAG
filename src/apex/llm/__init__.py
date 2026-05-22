"""LLM clients. Currently Ollama only, but designed so additional providers can be
slotted in behind a thin functional interface (``generate``, ``stream``)."""
from apex.llm.ollama_client import generate, stream

__all__ = ["generate", "stream"]
