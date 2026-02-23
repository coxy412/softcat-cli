"""Global configuration for SOFT CAT."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from rich.console import Console
from rich.prompt import Prompt

console = Console()

DEFAULT_CONFIG_DIR = Path.home() / ".softcat"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


class HealthchecksConfig(BaseModel):
    """Healthchecks.io monitoring configuration."""

    api_key: str | None = None
    base_url: str = "https://hc-ping.com"


class Config(BaseModel):
    """SOFT CAT global configuration."""

    anthropic_api_key: str | None = None
    default_model: str = "claude-sonnet-4-5-20250929"
    agents_dir: Path = Field(default_factory=lambda: DEFAULT_CONFIG_DIR / "agents")
    templates_dir: Path = Field(default_factory=lambda: DEFAULT_CONFIG_DIR / "templates")
    healthchecks: HealthchecksConfig = Field(default_factory=HealthchecksConfig)
    default_schedule: str = "0 6 * * *"  # daily at 06:00
    output_format: str = "markdown"
    verbose: bool = False


def get_config() -> Config:
    """Load config from file and environment, with env vars taking precedence."""
    config_data = {}

    if DEFAULT_CONFIG_FILE.exists():
        with open(DEFAULT_CONFIG_FILE) as f:
            config_data = yaml.safe_load(f) or {}

    # Environment overrides
    if api_key := os.environ.get("ANTHROPIC_API_KEY"):
        config_data["anthropic_api_key"] = api_key

    if hc_key := os.environ.get("HEALTHCHECKS_API_KEY"):
        config_data.setdefault("healthchecks", {})["api_key"] = hc_key

    if model := os.environ.get("SOFTCAT_MODEL"):
        config_data["default_model"] = model

    config = Config(**config_data)

    # Ensure directories exist
    config.agents_dir.mkdir(parents=True, exist_ok=True)
    config.templates_dir.mkdir(parents=True, exist_ok=True)

    return config


def init_config() -> Config:
    """Interactive config initialisation."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    console.print("\n[bold]Let's set up SOFT CAT.[/bold]\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY") or Prompt.ask(
        "Anthropic API key", password=True
    )

    model = Prompt.ask(
        "Default model",
        default="claude-sonnet-4-5-20250929",
    )

    hc_key = Prompt.ask(
        "Healthchecks.io API key [dim](optional, press enter to skip)[/dim]",
        default="",
    )

    config_data = {
        "anthropic_api_key": api_key,
        "default_model": model,
    }

    if hc_key:
        config_data["healthchecks"] = {"api_key": hc_key}

    with open(DEFAULT_CONFIG_FILE, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    console.print(f"\n[dim]Config saved to {DEFAULT_CONFIG_FILE}[/dim]")

    return get_config()
