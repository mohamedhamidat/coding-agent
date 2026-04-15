"""Tests for Agent class."""

import pytest
import json
from unittest.mock import Mock
from coding_agent.agent import Agent, MAX_ITERATIONS
from coding_agent.tools import ToolRegistry


def _mock_response(content=None, tool_calls=None):
    """Helper to create mock litellm response."""
    mock_resp = Mock()
    mock_msg = Mock()
    mock_msg.content = content
    mock_msg.tool_calls = tool_calls
    mock_resp.choices = [Mock(message=mock_msg)]
    return mock_resp


def _mock_tool_call(name, args, call_id="call_123"):
    """Helper to create mock tool call."""
    mock_tc = Mock()
    mock_tc.id = call_id
    mock_tc.function = Mock()
    mock_tc.function.name = name
    mock_tc.function.arguments = json.dumps(args)
    return mock_tc


class TestAgentSecurity:
    """Test agent security features."""

    def test_limits_iterations(self):
        """Should stop after MAX_ITERATIONS to prevent infinite loops."""
        # Mock infinite loop: always returns tool call
        chat_fn = Mock(return_value=_mock_response(
            tool_calls=[_mock_tool_call("fake_tool", {"arg": "value"})]
        ))
        registry = Mock(spec=ToolRegistry)
        registry.get_tools_for_function_calling.return_value = []
        registry.execute.return_value = "result"

        agent = Agent(chat_fn, registry, "test-model", "system prompt")

        result = agent.process_message("test")

        assert "Maximum iterations reached" in result
        assert chat_fn.call_count <= MAX_ITERATIONS

    def test_handles_json_parse_error(self):
        """Should handle malformed JSON in tool arguments."""
        # Create a tool call with invalid JSON
        bad_tool_call = Mock()
        bad_tool_call.id = "call_bad"
        bad_tool_call.function = Mock()
        bad_tool_call.function.name = "test"
        bad_tool_call.function.arguments = "{invalid json}"

        chat_fn = Mock(side_effect=[
            _mock_response(tool_calls=[bad_tool_call]),
            _mock_response(content="Continuing after error")
        ])

        registry = Mock(spec=ToolRegistry)
        registry.get_tools_for_function_calling.return_value = []

        agent = Agent(chat_fn, registry, "test-model", "system prompt")

        result = agent.process_message("test")

        # Should handle gracefully and continue
        assert "Continuing" in result or "Error" in result

    def test_handles_llm_errors(self):
        """Should handle LLM errors gracefully."""
        chat_fn = Mock(side_effect=Exception("LLM error"))
        registry = Mock(spec=ToolRegistry)
        registry.get_tools_for_function_calling.return_value = []

        agent = Agent(chat_fn, registry, "test-model", "system prompt")

        result = agent.process_message("test")

        assert "Error" in result

    def test_handles_connection_errors(self):
        """Should handle LLM connection errors gracefully."""
        chat_fn = Mock(side_effect=ConnectionError("Cannot connect"))
        registry = Mock(spec=ToolRegistry)
        registry.get_tools_for_function_calling.return_value = []

        agent = Agent(chat_fn, registry, "test-model", "system prompt")

        result = agent.process_message("test")

        assert "Error" in result
        assert "Cannot connect" in result


class TestAgentToolExecution:
    """Test tool execution flow."""

    def test_executes_single_tool(self):
        """Should execute a single tool call."""
        chat_fn = Mock(side_effect=[
            _mock_response(tool_calls=[_mock_tool_call("read_file", {"path": "test.txt"})]),
            _mock_response(content="File contains: content")
        ])
        registry = Mock(spec=ToolRegistry)
        registry.get_tools_for_function_calling.return_value = []
        registry.execute.return_value = "content"

        agent = Agent(chat_fn, registry, "test-model", "system prompt")

        result = agent.process_message("read test.txt")

        registry.execute.assert_called_once_with("read_file", {"path": "test.txt"})
        assert "File contains: content" in result

    def test_executes_multiple_tools(self):
        """Should execute multiple tool calls in sequence."""
        chat_fn = Mock(side_effect=[
            _mock_response(tool_calls=[_mock_tool_call("list_files", {"directory": "."})]),
            _mock_response(tool_calls=[_mock_tool_call("read_file", {"path": "test.txt"})]),
            _mock_response(content="Done")
        ])
        registry = Mock(spec=ToolRegistry)
        registry.get_tools_for_function_calling.return_value = []
        registry.execute.side_effect = ["file1\nfile2", "content"]

        agent = Agent(chat_fn, registry, "test-model", "system prompt")

        result = agent.process_message("list and read")

        assert registry.execute.call_count == 2
        assert "Done" in result

    def test_no_tools_returns_directly(self):
        """Should return response directly when no tools called."""
        chat_fn = Mock(return_value=_mock_response(content="Hello, I'm ready to help!"))
        registry = Mock(spec=ToolRegistry)
        registry.get_tools_for_function_calling.return_value = []

        agent = Agent(chat_fn, registry, "test-model", "system prompt")

        result = agent.process_message("hi")

        registry.execute.assert_not_called()
        assert "Hello" in result
