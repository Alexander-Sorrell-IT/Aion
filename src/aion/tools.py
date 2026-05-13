"""Tool implementations and their JSON schemas for the agent's tool-call API.

Each tool is a Python callable PLUS a schema describing it to the LLM. The
agent dispatches tool calls by looking up the name in TOOL_REGISTRY and
invoking the callable with the parsed arguments.

Tools provided:
    bash    — run a shell command, capture stdout/stderr/exit
    read    — read a file (or a range of lines)
    write   — create or overwrite a file
    edit    — exact-string find-and-replace in an existing file
    grep    — content search across files
    glob    — filename pattern search
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ToolResult:
    """Uniform return shape so the agent can route any tool's output to the LLM
    without per-tool branching."""
    ok: bool
    content: str
    # When non-None, the agent surfaces this in the UI alongside the result.
    summary: str | None = None


# ── bash ──────────────────────────────────────────────────────────────────────


def _tool_bash(command: str, timeout: int = 120) -> ToolResult:
    """Run a shell command. Bash interpretation, no shell escape on the caller's
    behalf — the agent is responsible for quoting its own command string."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, content=f"command timed out after {timeout}s")

    body = proc.stdout
    if proc.stderr:
        body = f"{body}\n[stderr]\n{proc.stderr}" if body else proc.stderr
    if proc.returncode != 0:
        return ToolResult(
            ok=False,
            content=f"[exit {proc.returncode}]\n{body}",
            summary=f"exit {proc.returncode}",
        )
    return ToolResult(ok=True, content=body or "(no output)")


_SCHEMA_BASH = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Run a bash command. Use for git, file system operations, package "
            "managers, build tools, and anything that's not better served by "
            "the specialized read/write/edit/grep/glob tools."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to run."},
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait. Default 120.",
                    "default": 120,
                },
            },
            "required": ["command"],
        },
    },
}


# ── read ──────────────────────────────────────────────────────────────────────


def _tool_read(path: str, offset: int = 0, limit: int = 2000) -> ToolResult:
    """Read a file. Optional offset/limit for paging large files."""
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(ok=False, content=f"file not found: {p}")
    if p.is_dir():
        return ToolResult(ok=False, content=f"path is a directory, not a file: {p}")
    try:
        lines = p.read_text(errors="replace").splitlines()
    except OSError as e:
        return ToolResult(ok=False, content=f"read error: {e}")

    selected = lines[offset : offset + limit]
    numbered = [f"{i + offset + 1:6d}\t{ln}" for i, ln in enumerate(selected)]
    body = "\n".join(numbered)
    total = len(lines)
    truncated = offset + limit < total
    summary = f"{len(selected)} lines"
    if truncated:
        summary += f" (of {total}, truncated)"
    return ToolResult(ok=True, content=body, summary=summary)


_SCHEMA_READ = {
    "type": "function",
    "function": {
        "name": "read",
        "description": "Read a file's contents with line numbers. Optional offset/limit for paging.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or ~ path to the file."},
                "offset": {"type": "integer", "description": "0-based line offset.", "default": 0},
                "limit": {"type": "integer", "description": "Max lines to return.", "default": 2000},
            },
            "required": ["path"],
        },
    },
}


# ── write ─────────────────────────────────────────────────────────────────────


def _tool_write(path: str, content: str) -> ToolResult:
    """Create or overwrite a file. Parent dirs are created if missing."""
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    except OSError as e:
        return ToolResult(ok=False, content=f"write error: {e}")
    return ToolResult(
        ok=True,
        content=f"wrote {len(content)} bytes to {p}",
        summary=f"{len(content.splitlines())} lines",
    )


_SCHEMA_WRITE = {
    "type": "function",
    "function": {
        "name": "write",
        "description": "Create or overwrite a file. Use for new files or full rewrites; prefer 'edit' for surgical changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
}


# ── edit ──────────────────────────────────────────────────────────────────────


def _tool_edit(path: str, old_str: str, new_str: str, replace_all: bool = False) -> ToolResult:
    """Replace an exact substring. Fails if old_str is not unique unless replace_all=True."""
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(ok=False, content=f"file not found: {p}")
    try:
        text = p.read_text()
    except OSError as e:
        return ToolResult(ok=False, content=f"read error: {e}")

    count = text.count(old_str)
    if count == 0:
        return ToolResult(ok=False, content="old_str not found in file")
    if count > 1 and not replace_all:
        return ToolResult(
            ok=False,
            content=f"old_str matches {count} times — pass replace_all=true or pick a more specific snippet",
        )

    new_text = text.replace(old_str, new_str) if replace_all else text.replace(old_str, new_str, 1)
    try:
        p.write_text(new_text)
    except OSError as e:
        return ToolResult(ok=False, content=f"write error: {e}")
    return ToolResult(ok=True, content=f"replaced {count if replace_all else 1} occurrence(s) in {p}")


_SCHEMA_EDIT = {
    "type": "function",
    "function": {
        "name": "edit",
        "description": "Exact-string find-and-replace in an existing file. Fails if old_str isn't unique unless replace_all is true.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string", "description": "Exact text to find (must be unique unless replace_all)."},
                "new_str": {"type": "string", "description": "Replacement text."},
                "replace_all": {"type": "boolean", "default": False},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
}


# ── grep ──────────────────────────────────────────────────────────────────────


def _tool_grep(
    pattern: str,
    path: str = ".",
    include: str | None = None,
    max_results: int = 100,
) -> ToolResult:
    """Content search via regex. Walks the tree from `path`, filters by `include` glob."""
    root = Path(path).expanduser()
    if not root.exists():
        return ToolResult(ok=False, content=f"path not found: {root}")

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return ToolResult(ok=False, content=f"invalid regex: {e}")

    hits: list[str] = []
    for current, dirs, files in os.walk(root):
        # Skip the usual junk
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv"}]
        for f in files:
            if include and not fnmatch.fnmatch(f, include):
                continue
            fp = Path(current) / f
            try:
                with open(fp, errors="replace") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if regex.search(line):
                            hits.append(f"{fp}:{lineno}:{line.rstrip()}")
                            if len(hits) >= max_results:
                                return ToolResult(
                                    ok=True,
                                    content="\n".join(hits),
                                    summary=f"{len(hits)} hits (capped)",
                                )
            except OSError:
                continue

    if not hits:
        return ToolResult(ok=True, content="(no matches)", summary="0 hits")
    return ToolResult(ok=True, content="\n".join(hits), summary=f"{len(hits)} hits")


_SCHEMA_GREP = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Search file contents with a regex. Filters by filename glob via 'include'.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern."},
                "path": {"type": "string", "default": ".", "description": "Root directory."},
                "include": {"type": "string", "description": "Glob filter (e.g. '*.py')."},
                "max_results": {"type": "integer", "default": 100},
            },
            "required": ["pattern"],
        },
    },
}


# ── glob ──────────────────────────────────────────────────────────────────────


def _tool_glob(pattern: str, path: str = ".") -> ToolResult:
    """Filename pattern search. Returns paths matching the glob, sorted by mtime descending."""
    root = Path(path).expanduser()
    if not root.exists():
        return ToolResult(ok=False, content=f"path not found: {root}")

    matches: list[tuple[float, Path]] = []
    for fp in root.rglob("*"):
        if fp.is_file() and fnmatch.fnmatch(fp.name, pattern):
            try:
                matches.append((fp.stat().st_mtime, fp))
            except OSError:
                continue

    matches.sort(reverse=True)
    paths = [str(p) for _, p in matches]
    if not paths:
        return ToolResult(ok=True, content="(no matches)", summary="0 files")
    return ToolResult(ok=True, content="\n".join(paths), summary=f"{len(paths)} files")


_SCHEMA_GLOB = {
    "type": "function",
    "function": {
        "name": "glob",
        "description": "Find files by filename glob (e.g. '*.py'). Returns paths sorted by recency.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Filename glob (e.g. 'test_*.py')."},
                "path": {"type": "string", "default": ".", "description": "Root directory."},
            },
            "required": ["pattern"],
        },
    },
}


# ── registry ─────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, Callable[..., ToolResult]] = {
    "bash": _tool_bash,
    "read": _tool_read,
    "write": _tool_write,
    "edit": _tool_edit,
    "grep": _tool_grep,
    "glob": _tool_glob,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    _SCHEMA_BASH,
    _SCHEMA_READ,
    _SCHEMA_WRITE,
    _SCHEMA_EDIT,
    _SCHEMA_GREP,
    _SCHEMA_GLOB,
]


# Register the extra tools (webfetch, websearch, todo_write, ask_user,
# agent_dispatch) and the Task* family. Done at import time so the agent's
# loop sees them in TOOL_SCHEMAS without further wiring.
def _register_extras() -> None:
    try:
        from .extra_tools import EXTRA_TOOL_REGISTRY, EXTRA_TOOL_SCHEMAS
        TOOL_REGISTRY.update(EXTRA_TOOL_REGISTRY)
        TOOL_SCHEMAS.extend(EXTRA_TOOL_SCHEMAS)
    except ImportError:
        pass
    try:
        from .tasks import TASK_TOOL_REGISTRY, TASK_TOOL_SCHEMAS
        TOOL_REGISTRY.update(TASK_TOOL_REGISTRY)
        TOOL_SCHEMAS.extend(TASK_TOOL_SCHEMAS)
    except ImportError:
        pass
    try:
        from .tier2_tools import TIER2_TOOL_REGISTRY, TIER2_TOOL_SCHEMAS
        TOOL_REGISTRY.update(TIER2_TOOL_REGISTRY)
        TOOL_SCHEMAS.extend(TIER2_TOOL_SCHEMAS)
    except ImportError:
        pass
    try:
        from .tier3_tools import TIER3_TOOL_REGISTRY, TIER3_TOOL_SCHEMAS
        TOOL_REGISTRY.update(TIER3_TOOL_REGISTRY)
        TOOL_SCHEMAS.extend(TIER3_TOOL_SCHEMAS)
    except ImportError:
        pass


_register_extras()


def dispatch(name: str, arguments: dict) -> ToolResult:
    """Look up and invoke a tool by name. Returns a ToolResult."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return ToolResult(ok=False, content=f"unknown tool: {name}")
    try:
        return fn(**arguments)
    except TypeError as e:
        return ToolResult(ok=False, content=f"bad arguments for {name}: {e}")
    except Exception as e:
        return ToolResult(ok=False, content=f"{name} crashed: {e}")
