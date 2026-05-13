"""Extra tools — parity additions toward Proteus's 41-tool surface.

Bundled as a separate module from tools.py so the core agent stays lean.
Imported and registered at module load.

Currently provides:
  webfetch         — fetch a URL, return content as markdown
  websearch        — search the web via DuckDuckGo HTML endpoint
  todo_write       — overwrite the session's TODO list (lightweight task tracker)
  ask_user         — prompt the user mid-execution for a clarifying answer
  agent_dispatch   — spawn a subagent with its own context, return its result

The Task* family (TaskCreate / TaskGet / TaskList / TaskUpdate / TaskOutput /
TaskStop) for managing background subagent jobs is in tasks.py — it has more
state to manage and deserves its own module.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from typing import Any

import httpx

from .tools import ToolResult


# ── webfetch ────────────────────────────────────────────────────────────────


# Module-level cache: url → (timestamp, markdown_content). 15-min TTL like
# Proteus. Threadsafe via simple dict + GIL; no per-key lock needed since
# the writes are atomic at the dict level.
_WEBFETCH_CACHE: dict[str, tuple[float, str]] = {}
_WEBFETCH_TTL_SECONDS = 15 * 60


def _webfetch_get_cached(url: str) -> str | None:
    entry = _WEBFETCH_CACHE.get(url)
    if entry is None:
        return None
    ts, content = entry
    if time.time() - ts > _WEBFETCH_TTL_SECONDS:
        _WEBFETCH_CACHE.pop(url, None)
        return None
    return content


def _webfetch_set_cache(url: str, content: str) -> None:
    _WEBFETCH_CACHE[url] = (time.time(), content)
    # Trim cache if it grows past 32 entries to avoid unbounded memory.
    if len(_WEBFETCH_CACHE) > 32:
        oldest_key = min(_WEBFETCH_CACHE, key=lambda k: _WEBFETCH_CACHE[k][0])
        _WEBFETCH_CACHE.pop(oldest_key, None)


def _html_to_markdown(html: str) -> str:
    """Convert HTML to markdown via markdownify; fall back to a stripped-tag
    plain-text version if markdownify isn't installed."""
    try:
        from markdownify import markdownify  # type: ignore[import-not-found]
    except ImportError:
        # Fallback: strip tags. Lossy but functional without the dep.
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        # Decode common entities; we don't need exhaustive HTML entity handling here.
        for entity, char in (
            ("&amp;", "&"),
            ("&lt;", "<"),
            ("&gt;", ">"),
            ("&quot;", '"'),
            ("&#39;", "'"),
            ("&nbsp;", " "),
        ):
            text = text.replace(entity, char)
        # Collapse whitespace
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    return markdownify(html, heading_style="ATX").strip()


def _tool_webfetch(url: str, prompt: str = "") -> ToolResult:
    """Fetch a URL, return its content converted to markdown.

    The `prompt` arg is unused — it's kept in the signature to match Proteus's
    tool schema. The agent provides it for documentation purposes; we return
    the full content and let the agent (the main LLM) extract what matters.

    Returns content truncated to ~80K chars if larger (most pages fit fine).
    """
    _ = prompt  # documented as for-the-agent's-reference; intentionally unused
    if not url:
        return ToolResult(ok=False, content="url is required")

    # Normalize: upgrade http → https
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    if not url.startswith(("https://", "http://")):
        return ToolResult(ok=False, content=f"url must be http or https: {url!r}")

    # Cache check
    cached = _webfetch_get_cached(url)
    if cached is not None:
        snippet = cached if len(cached) <= 80_000 else cached[:80_000] + "\n\n[…truncated]"
        return ToolResult(
            ok=True,
            content=snippet,
            summary=f"{len(cached)} chars (cached)",
        )

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "aion-cli/0.1 (+webfetch)"})
    except httpx.RequestError as e:
        return ToolResult(ok=False, content=f"fetch failed: {e}")

    if resp.status_code >= 400:
        return ToolResult(
            ok=False,
            content=f"HTTP {resp.status_code} from {url}",
            summary=f"HTTP {resp.status_code}",
        )

    # Honor content-type — if it's not HTML/text, return raw (truncated).
    ctype = resp.headers.get("content-type", "").lower()
    text = resp.text or ""

    if "html" in ctype or text.lstrip().startswith(("<!", "<html", "<HTML")):
        content = _html_to_markdown(text)
    else:
        content = text

    _webfetch_set_cache(url, content)
    snippet = content if len(content) <= 80_000 else content[:80_000] + "\n\n[…truncated]"
    return ToolResult(
        ok=True,
        content=snippet,
        summary=f"{len(content)} chars from {url} (HTTP {resp.status_code})",
    )


_SCHEMA_WEBFETCH = {
    "type": "function",
    "function": {
        "name": "webfetch",
        "description": (
            "Fetch the content of a URL as markdown. Use this to read articles, "
            "documentation pages, GitHub READMEs, blog posts, anything web-accessible. "
            "Results cached for 15 minutes. For GitHub repos, prefer using `gh` CLI "
            "via the bash tool when you need API-level access."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL (https://...) to fetch."},
                "prompt": {
                    "type": "string",
                    "description": "Optional: what you're looking for in the page (for your reference; the tool returns full content).",
                },
            },
            "required": ["url"],
        },
    },
}


# ── websearch ───────────────────────────────────────────────────────────────


def _tool_websearch(query: str, max_results: int = 10) -> ToolResult:
    """Search the web via DuckDuckGo's HTML endpoint. No API key required."""
    if not query.strip():
        return ToolResult(ok=False, content="query is required")

    url = "https://html.duckduckgo.com/html/"
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.post(
                url,
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 aion-cli/0.1 (+websearch)"},
            )
    except httpx.RequestError as e:
        return ToolResult(ok=False, content=f"search failed: {e}")

    if resp.status_code >= 400:
        return ToolResult(ok=False, content=f"search HTTP {resp.status_code}")

    # Parse results out of the HTML. We use BeautifulSoup if available, else
    # a regex fallback. DuckDuckGo's HTML results have a stable shape:
    # <div class="result"> ... <a class="result__a" href="...">title</a>
    # ... <a class="result__snippet">snippet</a>
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-not-found]

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for div in soup.select(".result")[:max_results]:
            a_title = div.select_one(".result__a")
            a_snippet = div.select_one(".result__snippet")
            if a_title:
                href = a_title.get("href", "")
                # DuckDuckGo wraps real URLs; unwrap if it's a /l/?uddg=... redirect
                if isinstance(href, str) and "uddg=" in href:
                    m = re.search(r"uddg=([^&]+)", href)
                    if m:
                        href = urllib.parse.unquote(m.group(1))
                results.append(
                    {
                        "title": a_title.get_text(strip=True),
                        "url": href,
                        "snippet": a_snippet.get_text(strip=True) if a_snippet else "",
                    }
                )
    except ImportError:
        # Regex fallback if bs4 not installed
        results = []
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            r'.*?<a[^>]*class="result__snippet"[^>]*>([^<]+)</a>',
            re.DOTALL,
        )
        for href, title, snippet in pattern.findall(resp.text)[:max_results]:
            if "uddg=" in href:
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    href = urllib.parse.unquote(m.group(1))
            results.append({"title": title.strip(), "url": href, "snippet": snippet.strip()})

    if not results:
        return ToolResult(ok=True, content="(no results)", summary="0 results")

    # Format as markdown list with title, URL, snippet
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r['title']}**\n   {r['url']}\n   {r['snippet']}")
    return ToolResult(
        ok=True,
        content="\n\n".join(lines),
        summary=f"{len(results)} results",
    )


_SCHEMA_WEBSEARCH = {
    "type": "function",
    "function": {
        "name": "websearch",
        "description": (
            "Search the web for a query. Returns up to 10 results with title, URL, "
            "and snippet. Uses DuckDuckGo so no API key needed. Use webfetch after "
            "this to read a specific result's full content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (natural language)."},
                "max_results": {"type": "integer", "default": 10, "description": "Max results (1-20)."},
            },
            "required": ["query"],
        },
    },
}


# ── todo_write ──────────────────────────────────────────────────────────────


# Session-scoped todo list. Lives in module memory; reset on aion restart.
# For persistence across sessions, the agent uses the memory-git system to
# write a todos.md file instead.
_TODO_LIST: list[dict] = []


def _tool_todo_write(todos: list[dict]) -> ToolResult:
    """Overwrite the session's TODO list with a new set of items.

    Each item should have:
        content:   what needs to be done
        status:    "pending" | "in_progress" | "completed"
        activeForm: present-continuous form for spinners (e.g. "Fixing bug")
    """
    if not isinstance(todos, list):
        return ToolResult(ok=False, content="todos must be a list of items")

    validated: list[dict] = []
    for i, item in enumerate(todos):
        if not isinstance(item, dict):
            return ToolResult(ok=False, content=f"item {i} is not an object")
        content = item.get("content", "").strip()
        status = item.get("status", "pending")
        active = item.get("activeForm", content)
        if not content:
            continue
        if status not in {"pending", "in_progress", "completed"}:
            status = "pending"
        validated.append({"content": content, "status": status, "activeForm": active})

    _TODO_LIST.clear()
    _TODO_LIST.extend(validated)

    # Format the current list as a status summary
    if not validated:
        return ToolResult(ok=True, content="todo list cleared", summary="0 items")

    lines = []
    for item in validated:
        icon = {"pending": "○", "in_progress": "◐", "completed": "●"}[item["status"]]
        lines.append(f"  {icon} {item['content']}")
    summary = (
        f"{sum(1 for t in validated if t['status'] == 'completed')}/{len(validated)} done"
    )
    return ToolResult(ok=True, content="\n".join(lines), summary=summary)


_SCHEMA_TODO_WRITE = {
    "type": "function",
    "function": {
        "name": "todo_write",
        "description": (
            "Overwrite the session TODO list. Use to track progress on a multi-step "
            "task — emit it at the START of a task with all items as 'pending', then "
            "re-emit with the current item marked 'in_progress' as you work, then "
            "'completed' as each finishes. Helps the user see what you're doing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "What needs to be done."},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                            "activeForm": {
                                "type": "string",
                                "description": "Present-continuous form (e.g. 'Fixing the bug').",
                            },
                        },
                        "required": ["content", "status"],
                    },
                },
            },
            "required": ["todos"],
        },
    },
}


# ── ask_user ────────────────────────────────────────────────────────────────


# Callback that the REPL wires up so ask_user can actually prompt. If not set,
# ask_user returns a "non-interactive" placeholder so the agent doesn't hang
# in one-shot mode.
_ASK_USER_CALLBACK: list = []  # using a list as a mutable container


def set_ask_user_callback(callback) -> None:
    """REPL wires this up at startup. callback signature:
    (question: str, options: list[str] | None) -> str (user's answer)
    """
    _ASK_USER_CALLBACK.clear()
    _ASK_USER_CALLBACK.append(callback)


def _tool_ask_user(question: str, options: list[str] | None = None) -> ToolResult:
    """Ask the user a clarifying question mid-execution."""
    if not _ASK_USER_CALLBACK:
        return ToolResult(
            ok=False,
            content="ask_user is not available in non-interactive mode; "
            "make a reasonable assumption and continue",
        )
    callback = _ASK_USER_CALLBACK[0]
    try:
        answer = callback(question, options)
    except (EOFError, KeyboardInterrupt):
        return ToolResult(ok=False, content="user cancelled the question")
    return ToolResult(ok=True, content=answer, summary=f"answer: {answer[:50]}")


_SCHEMA_ASK_USER = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the user a clarifying question mid-execution. Use when the task "
            "is ambiguous and proceeding would risk doing the wrong thing. Pass "
            "options as a list if there's a finite set of valid answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask."},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: finite list of valid answers.",
                },
            },
            "required": ["question"],
        },
    },
}


# ── agent_dispatch (subagent) ───────────────────────────────────────────────


def _tool_agent_dispatch(prompt: str, description: str = "") -> ToolResult:
    """Spawn a fresh subagent with its own conversation context. The subagent
    runs the prompt to completion and returns its final text.

    The subagent inherits the parent's brand + tools but starts with a fresh
    message history. Useful for delegating bounded work that would clutter
    the parent's context (e.g., research dives, file surveys).

    For v1 this runs synchronously (parent blocks). Async subagent dispatch
    via the Task* family (TaskCreate + TaskGet/TaskOutput) is separate.
    """
    if not prompt.strip():
        return ToolResult(ok=False, content="prompt is required")

    # Lazy import to avoid circular dependency (agent.py imports from this module).
    from .agent import Agent
    from .config import load_brand_config
    from pathlib import Path
    import os

    # Find brand.config.json by walking up — same logic as the main CLI's
    # _resolve_install_dir. We can't import that without a circular dep, so
    # we duplicate the walk-up here. Short and self-contained.
    env_dir = os.environ.get("AION_INSTALL_DIR")
    install_dir = None
    if env_dir:
        p = Path(env_dir).expanduser()
        if (p / "brand.config.json").exists():
            install_dir = p

    if install_dir is None:
        # Try walking up from cwd
        cwd = Path.cwd()
        for parent in [cwd, *cwd.parents]:
            if (parent / "brand.config.json").exists():
                install_dir = parent
                break

    if install_dir is None:
        return ToolResult(
            ok=False,
            content="agent_dispatch couldn't locate brand.config.json — set AION_INSTALL_DIR",
        )

    try:
        brand = load_brand_config(install_dir)
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, content=f"failed to load brand: {e}")

    # Build the subagent with INHERITED permissions. Subagents run synchronously
    # (parent is blocked) but they spawn fresh contexts that can't show prompts
    # to the user. The right shape is:
    #   - Inherit parent's flag values (auto_accept_edits, bypass, plan_mode)
    #   - Force noninteractive=True so the gate auto-allows where safe and
    #     blocks shell/external tools that would need a prompt
    #   - Subagent has its own tool_overrides dict (clone, not shared reference)
    from .permissions import PermissionState
    from . import _PARENT_PERMISSIONS_REF
    parent_perms = _PARENT_PERMISSIONS_REF[0] if _PARENT_PERMISSIONS_REF else None
    if parent_perms:
        sub_perms = PermissionState(
            auto_accept_edits=parent_perms.auto_accept_edits,
            bypass_permissions=parent_perms.bypass_permissions,
            plan_mode=parent_perms.plan_mode,
            tool_overrides=dict(parent_perms.tool_overrides),  # copy, not share
            noninteractive=True,  # subagent can't prompt
        )
    else:
        sub_perms = PermissionState(noninteractive=True)
    subagent = Agent(brand=brand, permissions=sub_perms)

    framed_prompt = prompt
    if description:
        framed_prompt = f"[Subagent task: {description}]\n\n{prompt}"

    try:
        result_text = subagent.execute(framed_prompt)
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, content=f"subagent crashed: {e}")

    return ToolResult(
        ok=True,
        content=result_text or "(subagent returned no text)",
        summary=f"subagent ran ({len(subagent.history)} turns)",
    )


_SCHEMA_AGENT_DISPATCH = {
    "type": "function",
    "function": {
        "name": "agent_dispatch",
        "description": (
            "Spawn a fresh subagent with its own context and run a prompt to "
            "completion. Returns the subagent's final text. Use for bounded "
            "work you want isolated from the main conversation (research, file "
            "surveys, focused investigations). Subagent has the same tools as "
            "you, fresh history. Synchronous — you wait for the result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The full prompt for the subagent."},
                "description": {
                    "type": "string",
                    "description": "Short label for what the subagent is doing (logged for the user).",
                },
            },
            "required": ["prompt"],
        },
    },
}


# ── registry ────────────────────────────────────────────────────────────────


EXTRA_TOOL_REGISTRY: dict[str, Any] = {
    "webfetch": _tool_webfetch,
    "websearch": _tool_websearch,
    "todo_write": _tool_todo_write,
    "ask_user": _tool_ask_user,
    "agent_dispatch": _tool_agent_dispatch,
}

EXTRA_TOOL_SCHEMAS: list[dict[str, Any]] = [
    _SCHEMA_WEBFETCH,
    _SCHEMA_WEBSEARCH,
    _SCHEMA_TODO_WRITE,
    _SCHEMA_ASK_USER,
    _SCHEMA_AGENT_DISPATCH,
]
