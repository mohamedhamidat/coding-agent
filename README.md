# Coding Agent

A simple, secure coding agent that uses LLMs to help you read, edit, and manage files through natural language conversation. Built with native function calling for robust tool execution.

## Features

- 🤖 **Multiple LLM Support** - OpenAI, Anthropic Claude, Ollama (100+ providers via litellm)
- 🔒 **Security First** - Path traversal protection, file size limits, edit confirmation
- 🎯 **Native Function Calling** - Robust tool execution (no fragile regex parsing)
- ⚡ **Parallel Tool Execution** - Multiple operations run concurrently for speed
- 📝 **Interactive REPL** - Natural conversation interface
- 🛡️ **Safe by Design** - All file operations sandboxed to working directory

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd coding-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Quick Start

### Using Ollama (Free, Local)

```bash
# Install Ollama
brew install ollama  # macOS
# or download from https://ollama.ai

# Pull a model
ollama pull gemma4

# Run the agent
python main.py --model ollama/gemma4
```

### Using OpenAI

```bash
# Set your API key
export OPENAI_API_KEY="sk-..."

# Run with GPT-4
python main.py --model openai/gpt-4o

# Or with o1-mini (best for coding)
python main.py --model openai/o1-mini
```

### Using Anthropic Claude

```bash
# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run with Claude
python main.py --model anthropic/claude-3-5-sonnet-20241022
```

## Usage Examples

### Reading Files
```
> Read the contents of main.py and summarize what it does
```

### Listing Files
```
> List all Python files in the current directory
```

### Editing Files
```
> In main.py, change the default model from ollama/gemma4 to openai/gpt-4o
```

The agent will:
1. Show you a diff preview of the changes
2. Ask for confirmation before executing
3. Apply the edit only after you confirm

### Creating Files
```
> Create a new file called hello.py that prints "Hello, World!"
```

## Command Line Options

```bash
python main.py --help

Options:
  --model MODEL    Model identifier (default: ollama/gemma4)
  -v, --verbose    Enable verbose logging
```

## Logging

Logs are written to `coding_agent.log` in the current directory.

**Enable verbose logging:**
```bash
python main.py --model openai/gpt-4o -v
```

This will:
- Show detailed debug output in terminal
- Log all tool calls and responses
- Help troubleshoot issues

## Available Tools

The agent has access to three core tools:

1. **read_file** - Read file contents
2. **list_files** - List files in a directory
3. **edit_file** - Edit or create files (with confirmation)

### Parallel Tool Execution

When LLMs make **multiple tool calls in one response**, the agent automatically executes them in parallel:

```
> Read main.py, setup.py, and README.md

# LLM makes 3 separate read_file calls
# Agent executes all 3 concurrently via asyncio.gather()
```

**How it works:**
1. LLM returns multiple tool calls in a single response
2. Agent separates edits from other operations
3. Non-edit tools execute in parallel using `asyncio.gather()`
4. Edit tools show batch diff preview with single confirmation

**Batch Edit Confirmation:**

When multiple edits are requested, the agent shows all diffs together:

```
> Create config.json with {"debug": true} and create test.py with a hello world script

[Edit Preview - Multiple Files]

--- Edit 1/2: config.json ---
+{"debug": true}

--- Edit 2/2: test.py ---
+print("Hello, World!")

Execute all 2 edits? (y/n):
```

**Performance Benefits:**
- Multiple file reads execute concurrently (3-5x faster)
- Batch operations complete faster
- Tool call order preserved in results
- Edit operations still require confirmation

## Security Features

### Path Traversal Protection
All file paths are validated to ensure they're within the working directory:
```python
# ✅ Allowed
read_file("src/main.py")
read_file("../coding-agent/README.md")  # If within cwd

# ❌ Blocked
read_file("/etc/passwd")
read_file("../../outside/project")
```

### File Size Limits
- Maximum file size: **10MB**
- Prevents memory exhaustion attacks
- Both read and write operations protected

### Edit Confirmation
All file edits require explicit user confirmation:
1. Shows unified diff preview
2. Waits for `y/n` confirmation
3. Only executes after approval

### Binary File Protection
Attempts to read binary files are rejected with helpful error messages.

## Architecture

```
main.py              → Entry point, logging configuration
├── Agent            → Orchestrates agentic loop (now async!)
├── AsyncToolExecutor → Executes tools concurrently
├── ToolRegistry     → Manages tools & function calling
├── PromptBuilder    → Builds system prompts
└── Tools            → read_file, list_files, edit_file
```

**Key Design Decisions:**
- **Native function calling** - No regex parsing, uses structured LLM responses
- **Async/await architecture** - Tools execute in parallel via asyncio.gather()
- **Thread pool execution** - Sync tools wrapped in async interface
- **Dependency injection** - Agent accepts generic `chat_fn`, easy to test
- **Security by default** - All operations validated and sandboxed

## Development

### Running Tests

```bash
# Run all tests (30 tests)
pytest tests/ -v

# With coverage report
pytest tests/ --cov=coding_agent --cov-report=term-missing

# Run only parallel execution tests
pytest tests/test_integration.py -v
```

**Test Suite:**
- ✅ 30 tests covering all functionality
- ✅ Security tests for path traversal, file size limits
- ✅ Async/parallel execution tests
- ✅ Agent and tool execution tests

### Project Structure

```
coding-agent/
├── coding_agent/              # Main package
│   ├── __init__.py
│   ├── agent.py              # Async agentic loop orchestration
│   ├── async_executor.py     # Parallel tool execution
│   ├── tools.py              # File operation tools
│   └── prompt_builder.py     # System prompt generation
├── tests/                    # Test suite (30 tests)
│   ├── test_agent.py         # Agent tests (async)
│   ├── test_async_executor.py # Parallel execution tests
│   └── test_security.py      # Security tests
├── main.py                  # Entry point
├── setup.py                 # Package configuration
└── README.md                # This file
```

## Supported Models

### OpenAI
- `openai/o1-mini` - Best for coding tasks
- `openai/gpt-4o` - Fast, capable, good all-around
- `openai/gpt-3.5-turbo` - Budget option

### Anthropic
- `anthropic/claude-3-5-sonnet-20241022` - Latest, most capable
- `anthropic/claude-3-opus-20240229` - Most powerful
- `anthropic/claude-3-haiku-20240307` - Fastest/cheapest

### Ollama (Local)
- `ollama/gemma4` - Google's Gemma model
- `ollama/codellama` - Code-specialized
- `ollama/deepseek-coder` - Good coding performance

See [litellm providers](https://docs.litellm.ai/docs/providers) for 100+ more options.

## Troubleshooting

### "LLM Provider NOT provided" Error
Make sure to use the `provider/model` format:
```bash
# ❌ Wrong
python main.py --model gpt-4

# ✅ Correct
python main.py --model openai/gpt-4
```

### Ollama Connection Error
```bash
# Start Ollama service
ollama serve

# In another terminal
python main.py --model ollama/gemma4
```

### API Key Not Found
```bash
# Check if key is set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Set permanently in ~/.zshrc or ~/.bashrc
export OPENAI_API_KEY="sk-..."
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [litellm](https://github.com/BerriAI/litellm) for unified LLM access
- Inspired by [Mihail Eric's "The Emperor Has No Clothes"](https://www.mihaileric.com/The-Emperor-Has-No-Clothes/)
- Uses native function calling for robust tool execution
