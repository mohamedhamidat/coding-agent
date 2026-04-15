#!/usr/bin/env python3
"""Simple coding agent with LLM support via litellm."""

import os
import sys
import logging
import argparse
from typing import List, Dict
import litellm
from coding_agent import ToolRegistry, Agent, PromptBuilder


def setup_logging(verbose: bool = False):
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('coding_agent.log'),
            logging.StreamHandler(sys.stderr) if verbose else logging.NullHandler()
        ]
    )

    litellm.set_verbose = verbose


def chat_with_llm(messages: List[Dict], model: str, tools: List[Dict]):
    """Chat function wrapper for litellm with function calling.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model identifier (e.g., "openai/gpt-4", "anthropic/claude-3-5-sonnet")
        tools: List of tool definitions in function calling format

    Returns:
        Full litellm response object (includes tool calls if any)

    Environment variables used:
        - OPENAI_API_KEY: For OpenAI models (gpt-4, gpt-3.5-turbo, etc.)
        - ANTHROPIC_API_KEY: For Claude models (claude-3-5-sonnet, etc.)
        - No key needed for Ollama models (local)
    """
    return litellm.completion(
        model=model,
        messages=messages,
        tools=tools
    )


def main():
    """Entry point for the coding agent."""
    parser = argparse.ArgumentParser(
        description="Coding agent with support for multiple LLM providers",
        epilog="""
    Examples:
    # Ollama (local, no API key needed)
    %(prog)s --model ollama/gemma4

    # OpenAI (requires OPENAI_API_KEY env var)
    %(prog)s --model openai/o1-mini
    %(prog)s --model openai/gpt-4o
    %(prog)s --model openai/gpt-3.5-turbo

    # Anthropic Claude (requires ANTHROPIC_API_KEY env var)
    %(prog)s --model anthropic/claude-3-5-sonnet-20241022
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--model",
        default="ollama/gemma4",
        help="Model identifier (format: provider/model). Examples: openai/o1-mini, anthropic/claude-3-5-sonnet-20241022, ollama/gemma4"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (logs to stderr and coding_agent.log)"
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    logger.info(f"Starting coding agent with model: {args.model}")
    registry = ToolRegistry()
    prompt = PromptBuilder.build_system_prompt()
    agent = Agent(
        chat_fn=chat_with_llm,
        tool_registry=registry,
        model=args.model,
        system_prompt=prompt
    )

    try:
        agent.run()
    except Exception as e:
        logger.exception("Unexpected error occurred")
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
