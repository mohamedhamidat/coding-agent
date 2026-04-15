"""Simple coding agent with local LLM via Ollama."""

from .agent import Agent
from .tools import ToolRegistry
from .prompt_builder import PromptBuilder

__version__ = "0.1.0"
__all__ = ["Agent", "ToolRegistry", "PromptBuilder"]
