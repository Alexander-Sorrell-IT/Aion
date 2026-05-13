"""aion — configurable agent CLI."""

__version__ = "0.1.0"

# Shared mutable container so subagent-spawning tools (agent_dispatch in
# extra_tools.py, task_create in tasks.py) can find the parent's permission
# state without a circular import. The CLI sets this at agent construction.
_PARENT_PERMISSIONS_REF: list = []


def set_parent_permissions(perms) -> None:
    """Wire the parent agent's permission state so subagents can inherit it."""
    _PARENT_PERMISSIONS_REF.clear()
    _PARENT_PERMISSIONS_REF.append(perms)
