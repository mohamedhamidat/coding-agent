import os
import inspect
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List

logger = logging.getLogger(__name__)

_tools: Dict[str, Callable] = {}


def tool(func: Callable) -> Callable:
    """Decorator to register a function as a tool."""
    _tools[func.__name__] = func
    return func


class ToolRegistry:
    """Manages available tools and generates descriptions for LLM."""

    def __init__(self):
        self.tools = _tools

    def get_tools_for_function_calling(self) -> List[Dict]:
        """Generate tools in function calling format for litellm."""
        tools = []

        for name, func in self.tools.items():
            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    type_name = param.annotation.__name__
                    if type_name == "int":
                        param_type = "integer"
                    elif type_name == "bool":
                        param_type = "boolean"

                properties[param_name] = {
                    "type": param_type,
                    "description": f"{param_name} parameter"
                }

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            tool_def = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func.__doc__ or f"Execute {name}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }

            tools.append(tool_def)

        logger.debug(f"Generated {len(tools)} tool definitions")
        return tools

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool with given arguments."""
        if tool_name not in self.tools:
            logger.error(f"Unknown tool: {tool_name}")
            return f"Error: Unknown tool '{tool_name}'"

        try:
            result = self.tools[tool_name](**args)
            logger.debug(f"Tool {tool_name} executed successfully")
            return result
        except TypeError as e:
            logger.error(f"Invalid arguments for {tool_name}: {e}")
            return f"Error: Invalid arguments for {tool_name}: {e}"
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}")
            return f"Error executing {tool_name}: {e}"


MAX_FILE_SIZE = 10 * 1024 * 1024
def validate_path(path: str) -> Path:
    """Validate path is within working directory and resolve it safely."""
    if not path or not path.strip():
        raise ValueError("Path cannot be empty")

    base = Path.cwd()
    try:
        target = (base / path).resolve()
    except (ValueError, OSError) as e:
        raise ValueError(f"Invalid path: {e}")

    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("Path traversal not allowed")

    return target


# Core tools
@tool
def read_file(path: str) -> str:
    """Read and return contents of file at given path."""
    try:
        target = validate_path(path)

        if target.stat().st_size > MAX_FILE_SIZE:
            return f"Error: File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)"

        with open(target, 'r') as f:
            return f.read()
    except ValueError as e:
        return f"Error: {e}"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except UnicodeDecodeError:
        return f"Error: File is not a text file: {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def list_files(directory: str = ".") -> str:
    """List files in the given directory (non-recursive, current level only)."""
    try:
        target = validate_path(directory)

        if not target.is_dir():
            return f"Error: Not a directory: {directory}"

        entries = os.listdir(target)

        files = []
        dirs = []
        for entry in entries:
            if entry.startswith('.'):
                continue
            full_path = target / entry
            if full_path.is_file():
                files.append(entry)
            elif full_path.is_dir():
                dirs.append(entry + "/")

        result = sorted(dirs) + sorted(files)
        return "\n".join(result) if result else "Directory is empty"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing files: {str(e)}"


@tool
def edit_file(path: str, old_content: str, new_content: str) -> str:
    """Replace old_content with new_content in file. Creates new file if old_content is empty."""
    try:
        target = validate_path(path)

        if len(new_content) > MAX_FILE_SIZE:
            return f"Error: Content too large (max {MAX_FILE_SIZE // (1024*1024)}MB)"

        current = ""
        if target.exists():
            if target.stat().st_size > MAX_FILE_SIZE:
                return f"Error: Existing file too large (max {MAX_FILE_SIZE // (1024*1024)}MB)"
            try:
                with open(target, 'r') as f:
                    current = f.read()
            except UnicodeDecodeError:
                return f"Error: File is not a text file: {path}"

        if old_content == "" and current == "":
            with open(target, 'w') as f:
                f.write(new_content)
            logger.info(f"Created new file: {path}")
            return f"Created new file: {path}"

        if old_content not in current:
            return f"Error: old_content not found in {path}"

        updated = current.replace(old_content, new_content, 1)

        with open(target, 'w') as f:
            f.write(updated)

        return f"Successfully edited {path}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error editing file: {str(e)}"
