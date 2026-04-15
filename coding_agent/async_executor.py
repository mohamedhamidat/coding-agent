"""Async executor for wrapping synchronous tools."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any


class AsyncToolExecutor:
    """Executes synchronous tools asynchronously using a thread pool."""

    def __init__(self, tool_registry, max_workers: int = 10):
        """Initialize the async executor.

        Args:
            tool_registry: ToolRegistry instance containing registered tools
            max_workers: Maximum number of worker threads for parallel execution
        """
        self.tool_registry = tool_registry
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def execute_async(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a synchronous tool asynchronously.

        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool

        Returns:
            Tool execution result as string

        Raises:
            ValueError: If tool_name is not registered
            Exception: Any exception raised by the tool
        """
        if tool_name not in self.tool_registry.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_func = self.tool_registry.tools[tool_name]

        # Run the synchronous tool in the thread pool
        # We need to use a lambda to properly unpack **args
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            lambda: tool_func(**args)
        )

        return result

    def shutdown(self):
        """Shutdown the thread pool executor."""
        if self.executor:
            self.executor.shutdown(wait=True)
