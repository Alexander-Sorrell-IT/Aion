"""Brand config loader. Mirrors Proteus's brand.config.json schema.

Reads <install-dir>/brand.config.json and validates it into a typed BrandConfig.
The CLI runtime consults this for binary name, display strings, model identity,
default plugin list, and memory-git behavior. install-time scripts also read it
to materialize env files and templated settings.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class VersionConfig:
    base: str = "0.1.0"
    preset: str = "alpha"

    @property
    def label(self) -> str:
        """e.g. '0.1.0-alpha' — what users see in --version output."""
        return f"{self.base}-{self.preset}" if self.preset else self.base


@dataclass(frozen=True)
class ApiConfig:
    preset: str = "openai"
    # When an explicit URL is set, takes precedence over the preset's default.
    base_url: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class PromptsConfig:
    prepend: str = ""


@dataclass(frozen=True)
class ModelIdentityConfig:
    mode: Literal["off", "partial", "full"] = "partial"


@dataclass(frozen=True)
class DefaultsConfig:
    plugins: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    memory: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryGitConfig:
    enabled: bool = True
    remote: str | None = None
    branch: str = "main"
    auto_commit: bool = True
    auto_push: bool = False


@dataclass(frozen=True)
class BrandConfig:
    binary: str = "aion"
    display: str = "aion"
    tagline: str = ""
    config_dir: str = "~/.aion"
    version: VersionConfig = field(default_factory=VersionConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    prompts: PromptsConfig = field(default_factory=PromptsConfig)
    model_identity: ModelIdentityConfig = field(default_factory=ModelIdentityConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    memory_git: MemoryGitConfig = field(default_factory=MemoryGitConfig)

    @property
    def resolved_config_dir(self) -> Path:
        """Tilde-expanded, absolute config dir path."""
        return Path(os.path.expanduser(self.config_dir)).resolve()


def _extract_install_list(block: dict | None) -> list[str]:
    if not block:
        return []
    items = block.get("install", [])
    return [str(x) for x in items if x]


def load_brand_config(install_dir: Path | str) -> BrandConfig:
    """Load brand.config.json from the given install directory.

    Raises FileNotFoundError if brand.config.json is missing — this is intentional.
    A aion install without a brand config is misconfigured; refuse to start
    silently with a default.
    """
    install_dir = Path(install_dir).resolve()
    config_path = install_dir / "brand.config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"brand.config.json not found at {config_path}. "
            "Every aion install needs one (copy from the template if missing)."
        )

    raw = json.loads(config_path.read_text())

    version_raw = raw.get("version", {}) or {}
    api_raw = raw.get("api", {}) or {}
    prompts_raw = raw.get("prompts", {}) or {}
    identity_raw = raw.get("modelIdentity", {}) or {}
    defaults_raw = raw.get("defaults", {}) or {}
    mg_raw = raw.get("memoryGit", {}) or {}

    return BrandConfig(
        binary=str(raw.get("binary", "aion")),
        display=str(raw.get("display", "aion")),
        tagline=str(raw.get("tagline", "")),
        config_dir=str(raw.get("configDir", "~/.aion")),
        version=VersionConfig(
            base=str(version_raw.get("base", "0.1.0")),
            preset=str(version_raw.get("preset", "alpha")),
        ),
        api=ApiConfig(
            preset=str(api_raw.get("preset", "openai")),
            base_url=api_raw.get("base_url"),
            model=api_raw.get("model"),
        ),
        prompts=PromptsConfig(prepend=str(prompts_raw.get("prepend", ""))),
        model_identity=ModelIdentityConfig(
            mode=str(identity_raw.get("mode", "partial")),  # type: ignore[arg-type]
        ),
        defaults=DefaultsConfig(
            plugins=_extract_install_list(defaults_raw.get("plugins")),
            skills=_extract_install_list(defaults_raw.get("skills")),
            agents=_extract_install_list(defaults_raw.get("agents")),
            memory=_extract_install_list(defaults_raw.get("memory")),
        ),
        memory_git=MemoryGitConfig(
            enabled=bool(mg_raw.get("enabled", True)),
            remote=mg_raw.get("remote"),
            branch=str(mg_raw.get("branch", "main")),
            auto_commit=bool(mg_raw.get("autoCommit", True)),
            auto_push=bool(mg_raw.get("autoPush", False)),
        ),
    )
