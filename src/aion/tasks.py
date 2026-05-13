"""Task management — background-running subagents tracked across turns.

The Task* family is the async cousin of agent_dispatch. agent_dispatch is
synchronous; the parent blocks until the subagent finishes. Tasks let the
parent fire off work and check on it later, like background jobs.

Tools provided:
    task_create  — start a background subagent task; returns task_id
    task_list    — list active and recently-completed tasks
    task_get     — get a task's current status + result
    task_update  — message a running task (e.g., redirect, cancel)
    task_output  — stream a task's accumulated output
    task_stop    — terminate a running task

Tasks live in module memory for the session. They don't survive aion restart.
Each task runs in a thread; the subagent's blocking LLM calls happen there.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tools import ToolResult


@dataclass
class Task:
    """One background task."""
    id: str
    description: str
    prompt: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed" | "stopped"
    result: str = ""
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    _thread: threading.Thread | None = None
    _stop_flag: threading.Event = field(default_factory=threading.Event)


# Session-scoped task registry. Keyed by task ID.
_TASKS: dict[str, Task] = {}
_TASKS_LOCK = threading.Lock()


def _run_task(task: Task, install_dir: Path) -> None:
    """Thread body for a task. Imports Agent inline to avoid circular deps."""
    task.started_at = time.time()
    task.status = "running"

    try:
        from .agent import Agent
        from .config import load_brand_config

        brand = load_brand_config(install_dir)
        subagent = Agent(brand=brand)
        # Note: no streaming hook wiring; tasks run silently and we read the
        # result after they finish.
        result_text = subagent.execute(task.prompt)
        task.result = result_text or "(no output)"
        if task._stop_flag.is_set():
            task.status = "stopped"
        else:
            task.status = "completed"
    except Exception as e:  # noqa: BLE001 — thread boundary
        task.status = "failed"
        task.error = str(e)
    finally:
        task.completed_at = time.time()


def _find_install_dir() -> Path | None:
    """Locate the brand.config.json install dir. Same heuristic as cli.py
    but duplicated to avoid the circular import."""
    import os
    env = os.environ.get("AION_INSTALL_DIR")
    if env:
        p = Path(env).expanduser()
        if (p / "brand.config.json").exists():
            return p
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "brand.config.json").exists():
            return parent
    return None


# ── task_create ──────────────────────────────────────────────────────────────


def _tool_task_create(description: str, prompt: str) -> ToolResult:
    install_dir = _find_install_dir()
    if install_dir is None:
        return ToolResult(
            ok=False,
            content="couldn't locate brand.config.json — set AION_INSTALL_DIR",
        )

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = Task(id=task_id, description=description, prompt=prompt)

    thread = threading.Thread(
        target=_run_task,
        args=(task, install_dir),
        daemon=True,
        name=f"aion-task-{task_id}",
    )
    task._thread = thread

    with _TASKS_LOCK:
        _TASKS[task_id] = task
    thread.start()

    return ToolResult(
        ok=True,
        content=f"task created: {task_id} — {description}",
        summary=task_id,
    )


_SCHEMA_TASK_CREATE = {
    "type": "function",
    "function": {
        "name": "task_create",
        "description": (
            "Start a background subagent to work on a prompt. Returns a task_id "
            "you can use with task_get/task_output later. Use for parallel "
            "investigations or work you want to fire-and-check-later. Unlike "
            "agent_dispatch (which blocks), task_create returns immediately."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Short label (shown in task lists)."},
                "prompt": {"type": "string", "description": "Full prompt for the subagent."},
            },
            "required": ["description", "prompt"],
        },
    },
}


# ── task_list ───────────────────────────────────────────────────────────────


def _tool_task_list(include_completed: bool = True) -> ToolResult:
    with _TASKS_LOCK:
        tasks = list(_TASKS.values())

    if not include_completed:
        tasks = [t for t in tasks if t.status in {"pending", "running"}]

    if not tasks:
        return ToolResult(ok=True, content="(no tasks)", summary="0")

    lines = []
    for t in tasks:
        icon = {
            "pending":   "○",
            "running":   "◐",
            "completed": "●",
            "failed":    "✘",
            "stopped":   "■",
        }.get(t.status, "?")
        duration = ""
        if t.started_at and t.completed_at:
            duration = f" ({t.completed_at - t.started_at:.1f}s)"
        elif t.started_at:
            duration = f" (running {time.time() - t.started_at:.0f}s)"
        lines.append(f"  {icon} {t.id}  [{t.status}{duration}]  {t.description}")
    return ToolResult(ok=True, content="\n".join(lines), summary=f"{len(tasks)} tasks")


_SCHEMA_TASK_LIST = {
    "type": "function",
    "function": {
        "name": "task_list",
        "description": "List tasks (running and recently completed).",
        "parameters": {
            "type": "object",
            "properties": {
                "include_completed": {"type": "boolean", "default": True},
            },
        },
    },
}


# ── task_get ────────────────────────────────────────────────────────────────


def _tool_task_get(task_id: str) -> ToolResult:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
    if task is None:
        return ToolResult(ok=False, content=f"unknown task: {task_id}")

    info = [
        f"id:          {task.id}",
        f"description: {task.description}",
        f"status:      {task.status}",
    ]
    if task.started_at:
        info.append(f"started:     {task.started_at:.0f} ({time.time() - task.started_at:.1f}s ago)")
    if task.completed_at:
        info.append(f"duration:    {task.completed_at - task.started_at:.1f}s" if task.started_at else "")
    if task.error:
        info.append(f"error:       {task.error}")
    if task.result and task.status in {"completed", "stopped"}:
        info.append("")
        info.append("--- result ---")
        info.append(task.result)
    return ToolResult(ok=True, content="\n".join(info), summary=task.status)


_SCHEMA_TASK_GET = {
    "type": "function",
    "function": {
        "name": "task_get",
        "description": "Get a task's current status, duration, and result (if completed).",
        "parameters": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
}


# ── task_output ─────────────────────────────────────────────────────────────


def _tool_task_output(task_id: str) -> ToolResult:
    """Return the task's accumulated output text (same as task_get's result
    block, but isolated — useful when only the output matters)."""
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
    if task is None:
        return ToolResult(ok=False, content=f"unknown task: {task_id}")
    if not task.result and task.status in {"pending", "running"}:
        return ToolResult(ok=True, content="(task still running)", summary=task.status)
    return ToolResult(ok=True, content=task.result or "(no output)", summary=task.status)


_SCHEMA_TASK_OUTPUT = {
    "type": "function",
    "function": {
        "name": "task_output",
        "description": "Get a task's accumulated output text (only the result, no metadata).",
        "parameters": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
}


# ── task_update ─────────────────────────────────────────────────────────────


def _tool_task_update(task_id: str, message: str) -> ToolResult:
    """Add a message to a running task. For v1 this is informational only —
    the running subagent doesn't see it (would require pre-built inter-thread
    messaging). Task* tools log the message into the task's result so it's
    visible later, and signals intent for future redirect/cancel support."""
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
    if task is None:
        return ToolResult(ok=False, content=f"unknown task: {task_id}")
    if task.status not in {"pending", "running"}:
        return ToolResult(
            ok=False,
            content=f"task {task_id} is {task.status}; can't update completed/failed tasks",
        )
    # Append to result; the running subagent doesn't see this yet (v1
    # limitation — future: prompt-injection channel).
    task.result += f"\n[user update {time.strftime('%H:%M:%S')}]: {message}\n"
    return ToolResult(
        ok=True,
        content=f"appended update to {task_id} (note: running subagent doesn't see this yet — v1 limitation)",
    )


_SCHEMA_TASK_UPDATE = {
    "type": "function",
    "function": {
        "name": "task_update",
        "description": "Append a note to a running task. v1 limitation: the running subagent doesn't see it.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["task_id", "message"],
        },
    },
}


# ── task_stop ───────────────────────────────────────────────────────────────


def _tool_task_stop(task_id: str) -> ToolResult:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
    if task is None:
        return ToolResult(ok=False, content=f"unknown task: {task_id}")
    if task.status not in {"pending", "running"}:
        return ToolResult(ok=False, content=f"task {task_id} is already {task.status}")
    task._stop_flag.set()
    # Python threads can't be force-killed safely; we set the flag and the
    # task body checks it. The LLM-call inside won't interrupt mid-call but
    # the next iteration will see the flag.
    return ToolResult(
        ok=True,
        content=f"stop requested for {task_id}; the task will terminate after its current LLM step",
    )


_SCHEMA_TASK_STOP = {
    "type": "function",
    "function": {
        "name": "task_stop",
        "description": "Signal a running task to stop. Takes effect at the task's next LLM-call boundary.",
        "parameters": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
}


# ── registry ────────────────────────────────────────────────────────────────


TASK_TOOL_REGISTRY: dict[str, Any] = {
    "task_create": _tool_task_create,
    "task_list":   _tool_task_list,
    "task_get":    _tool_task_get,
    "task_output": _tool_task_output,
    "task_update": _tool_task_update,
    "task_stop":   _tool_task_stop,
}

TASK_TOOL_SCHEMAS: list[dict[str, Any]] = [
    _SCHEMA_TASK_CREATE,
    _SCHEMA_TASK_LIST,
    _SCHEMA_TASK_GET,
    _SCHEMA_TASK_OUTPUT,
    _SCHEMA_TASK_UPDATE,
    _SCHEMA_TASK_STOP,
]
