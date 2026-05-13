"""Memory-git: action-level audit trail via local git.

Every Write/Edit/MultiEdit (and optionally other tool calls) gets committed
to a local git repo at <config_dir>/memory/.git/. The user gets a
tamper-evident log of every change the agent made.

Controlled by brand.config.json `memoryGit`:
    enabled    — initialize the repo at first run
    branch     — default branch name
    remote     — optional remote URL for push
    autoCommit — gate per-action commits
    autoPush   — push on each commit OR on session end (driven by caller)

This module exposes:
    init_memory_repo(config_dir, brand)       — first-run setup
    autocommit(memory_dir, slug, action)      — make one commit if dirty
    autopush(memory_dir)                      — push if origin exists
    git_log(memory_dir, limit)                — read recent commits

Hook integration is in hooks.py — this module is the data layer.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import BrandConfig


@dataclass(frozen=True)
class CommitEntry:
    sha: str
    message: str
    timestamp: str


def _run(cwd: Path, *args: str, check: bool = False) -> tuple[int, str, str]:
    """Thin git wrapper. Returns (returncode, stdout, stderr)."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout, proc.stderr


def init_memory_repo(config_dir: Path, brand: BrandConfig) -> bool:
    """Initialize the memory git repo if enabled and not already present.

    Returns True if anything was created. Idempotent — safe to call on
    every install/first-run.
    """
    if not brand.memory_git.enabled:
        return False

    memory_dir = config_dir / "memory"
    git_dir = memory_dir / ".git"
    memory_dir.mkdir(parents=True, exist_ok=True)

    if git_dir.is_dir():
        # Repo exists already. If a remote is configured in brand but not
        # set on the repo, add it.
        if brand.memory_git.remote:
            rc, _, _ = _run(memory_dir, "remote", "get-url", "origin")
            if rc != 0:
                _run(memory_dir, "remote", "add", "origin", brand.memory_git.remote)
        return False

    # Fresh init.
    _run(memory_dir, "init", "--initial-branch", brand.memory_git.branch, check=False)
    # Best-effort branch rename for older git versions that ignored --initial-branch.
    _run(memory_dir, "symbolic-ref", "HEAD", f"refs/heads/{brand.memory_git.branch}")

    # Local-only identity so commits work even without a global user.email.
    _run(memory_dir, "config", "user.email", f"{brand.binary}@localhost")
    _run(memory_dir, "config", "user.name", f"{brand.display} Memory Auto-commit")

    # Default .gitignore for the memory dir.
    (memory_dir / ".gitignore").write_text(
        "*.swp\n*.swo\n*~\n.DS_Store\nThumbs.db\n"
    )

    # Initial commit so subsequent autocommits have a base.
    _run(memory_dir, "add", "-A")
    _, status, _ = _run(memory_dir, "status", "--porcelain")
    if status.strip():
        _run(
            memory_dir,
            "commit",
            "-q",
            "-m",
            f"memory: initial commit ({brand.display} install "
            f"{datetime.now(timezone.utc).isoformat()})",
        )

    if brand.memory_git.remote:
        _run(memory_dir, "remote", "add", "origin", brand.memory_git.remote)

    return True


def autocommit(memory_dir: Path, slug: str = "auto", action: str = "edit") -> bool:
    """Stage all and commit if anything is dirty. Returns True if a commit was made.

    Fast-path returns False in ~10ms when nothing to commit — safe to call on
    every tool invocation.
    """
    if not (memory_dir / ".git").is_dir():
        return False

    rc, status, _ = _run(memory_dir, "status", "--porcelain")
    if rc != 0 or not status.strip():
        return False

    if slug == "auto" and action == "edit":
        msg = f"memory: auto-update {datetime.now(timezone.utc).isoformat()}"
    else:
        msg = f"memory: {slug} ({action})"

    _run(memory_dir, "add", "-A")
    rc, _, _ = _run(memory_dir, "commit", "-q", "-m", msg)
    return rc == 0


def autopush(memory_dir: Path) -> bool:
    """Push to origin if it exists. Non-blocking (backgrounded). Returns True
    if the push was kicked off (not necessarily completed)."""
    if not (memory_dir / ".git").is_dir():
        return False

    rc, _, _ = _run(memory_dir, "remote", "get-url", "origin")
    if rc != 0:
        return False

    # Fire-and-forget: spawn the push detached so the caller doesn't wait
    # on the network. We use Popen + start_new_session for the detach.
    subprocess.Popen(
        ["git", "push", "-q", "origin", "HEAD"],
        cwd=memory_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True


def git_log(memory_dir: Path, limit: int = 20) -> list[CommitEntry]:
    """Return the most recent N commits in the memory repo."""
    if not (memory_dir / ".git").is_dir():
        return []
    rc, out, _ = _run(
        memory_dir,
        "log",
        f"-{limit}",
        "--pretty=format:%H%x00%s%x00%ct",
    )
    if rc != 0 or not out.strip():
        return []
    entries: list[CommitEntry] = []
    for line in out.strip().split("\n"):
        parts = line.split("\x00")
        if len(parts) != 3:
            continue
        sha, message, ct = parts
        try:
            ts = datetime.fromtimestamp(int(ct), tz=timezone.utc).isoformat()
        except ValueError:
            ts = ct
        entries.append(CommitEntry(sha=sha, message=message, timestamp=ts))
    return entries
