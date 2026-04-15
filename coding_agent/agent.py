import os
import json
import logging
import asyncio
from typing import List, Dict, Callable, Any
from difflib import unified_diff

from .tools import ToolRegistry
from .async_executor import AsyncToolExecutor

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
        self.async_executor = AsyncToolExecutor(tool_registry)

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

                response = asyncio.run(self.process_message(user_input))
                print(f"\n{response}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            logger.info("Session ended by user")
        finally:
            self.async_executor.shutdown()

    async def process_message(self, user_input: str) -> str:
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

                # Execute tool calls in parallel
                tool_results = await self._execute_tool_calls_parallel(message.tool_calls)

                # Add results to conversation in order
                for tool_call, result in zip(message.tool_calls, tool_results):
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

    async def _execute_tool_calls_parallel(self, tool_calls: List[Any]) -> List[str]:
        """Execute tool calls in parallel, with special handling for edits.

        Args:
            tool_calls: List of tool call objects from LLM

        Returns:
            List of tool results in same order as tool_calls
        """
        # Separate edit_file calls from other tools
        edit_calls = []
        other_calls = []
        call_indices = {}  # Track original indices for reordering

        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.function.name
            logger.info(f"Calling tool: {tool_name}")
            print(f"[Agent] Calling {tool_name}...")

            if tool_name == "edit_file":
                edit_calls.append((i, tool_call))
            else:
                other_calls.append((i, tool_call))

        results = [None] * len(tool_calls)

        # Execute non-edit tools in parallel
        if other_calls:
            other_tasks = []
            for idx, tool_call in other_calls:
                try:
                    args = json.loads(tool_call.function.arguments)
                    logger.debug(f"Tool arguments: {args}")
                    other_tasks.append((idx, tool_call.function.name, self.async_executor.execute_async(tool_call.function.name, args)))
                except json.JSONDecodeError as e:
                    result = f"Error: Could not parse arguments: {e}"
                    logger.error(result)
                    print(f"[Warning] {result}")
                    results[idx] = result

            # Wait for all non-edit tools
            if other_tasks:
                task_results = await asyncio.gather(*[task for _, _, task in other_tasks], return_exceptions=True)
                for (idx, tool_name, _), result in zip(other_tasks, task_results):
                    if isinstance(result, Exception):
                        results[idx] = f"Error executing {tool_name}: {str(result)}"
                        logger.error(f"Tool {tool_name} failed: {result}")
                    else:
                        results[idx] = result
                        logger.info(f"Tool {tool_name} completed successfully")
                        print(f"[Tool: {tool_name}] Success")

        # Handle batch edits with single confirmation
        if edit_calls:
            edit_results = await self._handle_batch_edits(edit_calls)
            for (idx, _), result in zip(edit_calls, edit_results):
                results[idx] = result

        return results

    async def _handle_batch_edits(self, edit_calls: List[tuple]) -> List[str]:
        """Handle multiple edit_file calls with batch diff preview and single confirmation.

        Args:
            edit_calls: List of (index, tool_call) tuples for edit_file calls

        Returns:
            List of edit results
        """
        # Parse all edit arguments
        edit_args_list = []
        for idx, tool_call in edit_calls:
            try:
                args = json.loads(tool_call.function.arguments)
                logger.debug(f"Edit arguments: {args}")
                edit_args_list.append(args)
            except json.JSONDecodeError as e:
                result = f"Error: Could not parse arguments: {e}"
                logger.error(result)
                print(f"[Warning] {result}")
                edit_args_list.append(None)

        # Show all diffs
        print("\n[Edit Preview - Multiple Files]")
        for i, args in enumerate(edit_args_list):
            if args is None:
                continue

            path = args.get("path", "")
            old_content = args.get("old_content", "")
            new_content = args.get("new_content", "")

            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            diff = unified_diff(old_lines, new_lines, fromfile=path, tofile=path, lineterm='')

            print(f"\n--- Edit {i+1}/{len(edit_args_list)}: {path} ---")
            print("".join(diff))

        # Single confirmation for all edits
        response = input(f"\nExecute all {len(edit_args_list)} edits? (y/n): ").strip().lower()
        if response != 'y':
            logger.info("User declined batch edits")
            print("[Agent] Edits declined")
            return ["User declined the edit"] * len(edit_args_list)

        # Execute all edits in parallel
        results = []
        tasks = []
        for args in edit_args_list:
            if args is None:
                results.append(None)
                tasks.append(None)
            else:
                tasks.append(self.async_executor.execute_async("edit_file", args))

        # Wait for all edits
        valid_tasks = [t for t in tasks if t is not None]
        if valid_tasks:
            edit_results = await asyncio.gather(*valid_tasks, return_exceptions=True)

            # Merge results back
            edit_idx = 0
            for i, task in enumerate(tasks):
                if task is None:
                    results.append("Error: Failed to parse arguments")
                else:
                    result = edit_results[edit_idx]
                    if isinstance(result, Exception):
                        results.append(f"Error executing edit_file: {str(result)}")
                    else:
                        results.append(result)
                        logger.info(f"Edit executed: {edit_args_list[i].get('path', '')}")
                        print(f"[Tool: edit_file] {result}")
                    edit_idx += 1

        return results
