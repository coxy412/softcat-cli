"""Interactive multi-turn agent designer — the 'meow' engine."""

from __future__ import annotations

import json

import anthropic
from rich.console import Console
from rich.prompt import Prompt

from softcat.config import Config
from softcat.core.scanner import ScanResult

console = Console()

MAX_TURNS = 20

DESIGNER_SYSTEM_PROMPT = """\
You are the SOFT CAT Designer — a conversational agent architect. Your job is to help
the user design an automated agent through a short, friendly conversation.

Gather enough information to produce a complete agent specification. Cover these areas
(ask about what's unclear, don't re-ask what's already obvious):

- **Purpose**: What does the agent do? One-sentence summary.
- **Data sources**: Where does it get its input? (APIs, RSS feeds, websites, files, databases)
- **Output**: What does it produce and where? (markdown file, JSON, webhook, git commit)
- **Schedule**: How often should it run? (daily, weekly, hourly, custom cron)
- **Dependencies**: Any specific Python libraries needed beyond the basics?

Guidelines:
- Be concise — ask 2-3 questions at a time, not a wall of text
- Be slightly playful but technically precise
- Use "we" not "I"
- Don't ask questions the user already answered
- Suggest reasonable defaults (daily at 06:00 UTC, markdown file output) when the user \
doesn't specify

When you have gathered enough information to fully specify the agent, end your response with
the marker ===DESIGN_COMPLETE=== followed by a JSON object (no markdown fences) matching
this exact schema:

{
    "suggested_name": "kebab-case-name",
    "summary": "One sentence summary",
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
    "tools_needed": [],
    "mcp_servers": [],
    "dependencies": ["anthropic", "httpx", "pyyaml"],
    "complexity": "simple|moderate|complex",
    "estimated_tokens_per_run": 1000
}

IMPORTANT: Only output the ===DESIGN_COMPLETE=== marker when you are confident you have
enough detail. The JSON must be valid and complete. Include "anthropic", "httpx", and
"pyyaml" in dependencies by default — add others as needed.
"""

DESIGN_COMPLETE_MARKER = "===DESIGN_COMPLETE==="


class Designer:
    """Multi-turn conversational agent designer.

    Runs an interactive conversation with Claude to gather requirements,
    then produces a ScanResult that feeds into the spawn pipeline.
    """

    def __init__(self, config: Config, model: str | None = None) -> None:
        self.config = config
        self.model = model or config.default_model
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def design(self) -> ScanResult | None:
        """Run multi-turn conversation. Returns ScanResult or None if user quits."""
        messages: list[dict[str, str]] = []

        for turn in range(MAX_TURNS):
            # Get user input
            try:
                user_input = Prompt.ask("[bold cyan]>[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Conversation ended.[/dim]")
                return None

            if user_input.strip().lower() in ("quit", "exit"):
                console.print("[dim]Conversation ended.[/dim]")
                return None

            messages.append({"role": "user", "content": user_input})

            # Call Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=DESIGNER_SYSTEM_PROMPT,
                messages=messages,
            )

            assistant_text = response.content[0].text.strip()
            messages.append({"role": "assistant", "content": assistant_text})

            # Check for completion marker
            if DESIGN_COMPLETE_MARKER in assistant_text:
                return self._parse_design(assistant_text)

            # Print Claude's conversational response
            console.print(f"\n[cyan]🐱[/cyan] {assistant_text}\n")

        console.print("[yellow]Conversation limit reached. Try again with a clearer description.[/yellow]")
        return None

    def _parse_design(self, text: str) -> ScanResult:
        """Extract ScanResult JSON from a response containing the completion marker."""
        # Show the conversational part (before the marker)
        parts = text.split(DESIGN_COMPLETE_MARKER, 1)
        if parts[0].strip():
            console.print(f"\n[cyan]🐱[/cyan] {parts[0].strip()}\n")

        # Parse the JSON part (after the marker)
        json_text = parts[1].strip()

        # Strip markdown fences if present
        if json_text.startswith("```"):
            json_text = json_text.split("\n", 1)[1]
            if json_text.endswith("```"):
                json_text = json_text[:-3]
            json_text = json_text.strip()

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            console.print(f"[red]🙀 Failed to parse design: {e}[/red]")
            console.print(f"[dim]Raw: {json_text[:200]}[/dim]")
            raise

        return ScanResult(**data)
