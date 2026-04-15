"""Build system prompts for the coding agent."""


class PromptBuilder:
    """Builds system prompts from tool descriptions."""

    @staticmethod
    def build_system_prompt() -> str:
        """Generate system prompt for coding assistant.

        Note: Tools are passed separately via function calling API,
        so they don't need to be described in the system prompt.

        Returns:
            System prompt for the LLM
        """
        return """You are a coding assistant. You can help users by reading, listing, and editing files.

You have access to tools for file operations. When you need to examine or modify files, use the available tools.

Always think step by step and use tools when needed to accomplish the user's request."""
