"""S — Scan: Parse natural language description into structured agent requirements."""

from __future__ import annotations

import json

import anthropic
from pydantic import BaseModel, Field
from rich.console import Console

from softcat.config import Config

console = Console()

SCAN_SYSTEM_PROMPT = """\
You are the SOFT CAT Scanner — the first stage of an agent-building pipeline.

Your job: take a natural language description of what the user wants an agent to do,
and extract structured requirements.

Respond ONLY with valid JSON matching this schema:
{
    "suggested_name": "kebab-case-name",
    "summary": "One sentence summary of what the agent does",
    "intent": "digest|monitor|transformer|responder|custom",
    "data_sources": [
        {"type": "api|rss|web|file|database|mcp", "url_or_path": "...", "description": "..."}
    ],
    "output": {
        "format": "markdown|json|csv|text|html",
        "destination": "file|stdout|webhook|git_commit",
        "description": "What the output looks like"
    },
    "schedule": {
        "cadence": "daily|hourly|weekly|on_demand|cron",
        "cron_expression": "0 6 * * *",
        "timezone": "UTC"
    },
    "tools_needed": ["web_fetch", "file_write", "api_call", ...],
    "mcp_servers": ["web_search", "filesystem", ...],
    "dependencies": ["feedparser", "beautifulsoup4", ...],
    "complexity": "simple|moderate|complex",
    "estimated_tokens_per_run": 1000
}

Rules:
- suggested_name should be short, descriptive, kebab-case
- intent categorises the agent type:
  - digest: collects and summarises information on a schedule
  - monitor: watches for changes and alerts
  - transformer: takes input, processes it, produces output
  - responder: reacts to events or triggers
  - custom: doesn't fit the above
- Be conservative with dependencies — only include what's actually needed
- If the schedule isn't specified, default to daily at 06:00 UTC
- If the output destination isn't specified, default to file
"""


class DataSource(BaseModel):
    """A data source the agent needs to read from."""

    type: str
    url_or_path: str = ""
    description: str = ""


class OutputSpec(BaseModel):
    """What the agent produces."""

    format: str = "markdown"
    destination: str = "file"
    description: str = ""


class ScheduleSpec(BaseModel):
    """When the agent runs."""

    cadence: str = "daily"
    cron_expression: str = "0 6 * * *"
    timezone: str = "UTC"


class ScanResult(BaseModel):
    """Structured output from the Scanner."""

    suggested_name: str
    summary: str
    intent: str = "custom"
    data_sources: list[DataSource] = Field(default_factory=list)
    output: OutputSpec = Field(default_factory=OutputSpec)
    schedule: ScheduleSpec = Field(default_factory=ScheduleSpec)
    tools_needed: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    complexity: str = "simple"
    estimated_tokens_per_run: int = 1000

    def __str__(self) -> str:
        sources = ", ".join(s.type for s in self.data_sources) or "none"
        return (
            f"Name: {self.suggested_name}\n"
            f"Summary: {self.summary}\n"
            f"Intent: {self.intent}\n"
            f"Sources: {sources}\n"
            f"Output: {self.output.format} → {self.output.destination}\n"
            f"Schedule: {self.schedule.cron_expression}\n"
            f"Complexity: {self.complexity}"
        )


class Scanner:
    """S — Scan phase of the S.O.F.T.C.A.T pipeline.

    Takes a natural language description and uses Claude to extract
    structured requirements for the agent.
    """

    def __init__(self, config: Config, model: str | None = None) -> None:
        self.config = config
        self.model = model or config.default_model
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def scan(self, description: str) -> ScanResult:
        """Parse a natural language description into structured requirements."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SCAN_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": description},
            ],
        )

        raw_text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            console.print(f"[red]🙀 Failed to parse scan result: {e}[/red]")
            console.print(f"[dim]Raw response: {raw_text[:200]}[/dim]")
            raise

        return ScanResult(**data)
