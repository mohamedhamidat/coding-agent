import os
import json
import logging
from typing import List, Dict, Callable, Any
from difflib import unified_diff

from .tools import ToolRegistry

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10
CHARS_PER_TOKEN = 4


class Agent:
    """Orchestrates the agentic loop."""

    def __init__(
        self,
        chat_fn: Callable[[List[Dict], str, List[Dict]], Any],
        tool_registry: ToolRegistry,
        model: str,
        system_prompt: str
    ):
        """Initialize agent with LLM client and available tools.

        Args:
            chat_fn: Function that takes (messages, model, tools) and returns LLM response
            tool_registry: Registry of available tools
            model: Model identifier (e.g., "openai/gpt-4", "anthropic/claude-3-5-sonnet")
            system_prompt: System prompt to initialize conversation
        """
        self.chat_fn = chat_fn
        self.registry = tool_registry
        self.model = model
        self.tools = tool_registry.get_tools_for_function_calling()
        self.conversation: List[Dict] = [{"role": "system", "content": system_prompt}]

    def run(self):
        """Start the interactive REPL."""
        logger.info(f"Starting coding agent with model: {self.model}")
        logger.info(f"Working directory: {os.getcwd()}")
        print(f"Starting coding agent with model: {self.model}")
        print(f"Working directory: {os.getcwd()}")
        print("Type your request (Ctrl+C to exit)\n")

        try:
            while True:
                user_input = input("> ").strip()
                if not user_input:
                    continue

                response = self.process_message(user_input)
                print(f"\n{response}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            logger.info("Session ended by user")

    def process_message(self, user_input: str) -> str:
        """Process one user message through the agentic loop."""
        self.conversation.append({"role": "user", "content": user_input})
        logger.debug(f"User input: {user_input}")

        for iteration in range(MAX_ITERATIONS):
            total_chars = sum(len(msg.get("content", "")) for msg in self.conversation)
            approx_tokens = total_chars // CHARS_PER_TOKEN

            logger.debug(f"Iteration {iteration + 1}/{MAX_ITERATIONS}, {len(self.conversation)} messages, ~{approx_tokens} tokens")
            print(f"[Context: {len(self.conversation)} messages, ~{approx_tokens} tokens]")

            try:
                response = self.chat_fn(self.conversation, self.model, self.tools)
            except Exception as e:
                logger.error(f"LLM error: {e}")
                return f"Error: {e}"

            message = response.choices[0].message

            if message.tool_calls:
                logger.debug(f"LLM requested {len(message.tool_calls)} tool call(s)")
                self.conversation.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                })

                for tool_call in message.tool_calls:
                    result = self._execute_tool_call(tool_call)
                    self.conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
            else:
                content = message.content or "No response"
                self.conversation.append({"role": "assistant", "content": content})
                logger.debug("Agent completed without tool calls")
                return content

        logger.warning("Maximum iterations reached")
        return "Error: Maximum iterations reached. The agent may be stuck in a loop."

    def _execute_tool_call(self, tool_call: Any) -> str:
        """Execute a single tool call."""
        tool_name = tool_call.function.name
        logger.info(f"Calling tool: {tool_name}")
        print(f"[Agent] Calling {tool_name}...")

        try:
            args = json.loads(tool_call.function.arguments)
            logger.debug(f"Tool arguments: {args}")
        except json.JSONDecodeError as e:
            result = f"Error: Could not parse arguments: {e}"
            logger.error(result)
            print(f"[Warning] {result}")
            return result

        if tool_name == "edit_file":
            result = self._handle_edit_with_confirmation(args)
        else:
            result = self.registry.execute(tool_name, args)
            logger.info(f"Tool {tool_name} completed successfully")
            print(f"[Tool: {tool_name}] Success")

        return result

    def _handle_edit_with_confirmation(self, args: Dict) -> str:
        """Handle edit_file with diff preview and confirmation."""
        path = args.get("path", "")
        old_content = args.get("old_content", "")
        new_content = args.get("new_content", "")

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = unified_diff(old_lines, new_lines, fromfile=path, tofile=path, lineterm='')

        print("\n[Edit Preview]")
        print("".join(diff))

        response = input("\nExecute this edit? (y/n): ").strip().lower()
        if response != 'y':
            logger.info(f"User declined edit to {path}")
            print("[Agent] Edit declined")
            return "User declined the edit"

        result = self.registry.execute("edit_file", args)
        logger.info(f"Edit executed: {path}")
        print(f"[Tool: edit_file] {result}")
        return result
