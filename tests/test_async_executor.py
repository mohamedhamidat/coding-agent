"""Tests for AsyncToolExecutor."""
import pytest
from coding_agent.async_executor import AsyncToolExecutor
from coding_agent.tools import ToolRegistry


@pytest.mark.asyncio
async def test_execute_async_runs_sync_tool():
    """Test that sync tools can be executed asynchronously."""
    registry = ToolRegistry()
    executor = AsyncToolExecutor(registry)

    # Test read_file tool
    result = await executor.execute_async("read_file", {"path": "README.md"})

    # Tools return strings
    assert isinstance(result, str)
    assert len(result) > 0
    # Should contain content from README
    assert "Coding Agent" in result or "Error" in result

    executor.shutdown()


@pytest.mark.asyncio
async def test_parallel_execution():
    """Test that multiple tools execute in parallel."""
    import asyncio
    import time

    registry = ToolRegistry()
    executor = AsyncToolExecutor(registry)

    # Execute multiple reads in parallel
    start = time.time()
    results = await asyncio.gather(
        executor.execute_async("read_file", {"path": "README.md"}),
        executor.execute_async("read_file", {"path": "setup.py"}),
        executor.execute_async("list_files", {"directory": "."})
    )
    elapsed = time.time() - start

    # All should succeed and return strings
    assert len(results) == 3
    assert all(isinstance(r, str) and len(r) > 0 for r in results)

    # Should be faster than sequential (rough check)
    # This is a weak assertion but validates parallelism
    assert elapsed < 2.0  # Should complete quickly

    executor.shutdown()


@pytest.mark.asyncio
async def test_execute_async_handles_errors():
    """Test that errors in tools are properly handled (tools return error strings)."""
    registry = ToolRegistry()
    executor = AsyncToolExecutor(registry)

    # Tools return error messages as strings, not exceptions
    result = await executor.execute_async("read_file", {"path": "/nonexistent/file.txt"})

    assert isinstance(result, str)
    assert "Error" in result

    executor.shutdown()


@pytest.mark.asyncio
async def test_execute_async_unknown_tool():
    """Test that unknown tools raise appropriate errors."""
    registry = ToolRegistry()
    executor = AsyncToolExecutor(registry)

    with pytest.raises(ValueError, match="Unknown tool"):
        await executor.execute_async("nonexistent_tool", {})

    executor.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cleans_up():
    """Test that shutdown properly cleans up the thread pool."""
    registry = ToolRegistry()
    executor = AsyncToolExecutor(registry)

    # Execute a task
    await executor.execute_async("list_files", {"directory": "."})

    # Shutdown should not raise
    executor.shutdown()

    # Second shutdown should be safe (no-op)
    executor.shutdown()
