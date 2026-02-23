"""F — Fabricate: Generate agent code, prompts, and configuration."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import yaml
from jinja2 import Environment, FileSystemLoader, PackageLoader
from rich.console import Console

from softcat.config import Config
from softcat.core.orchestrator import OrchestrationPlan
from softcat.core.scanner import ScanResult

console = Console()

FABRICATION_SYSTEM_PROMPT = """\
You are the SOFT CAT Fabricator. You generate a production-ready Python agent AND its
prompt template together in a single response.

Given the agent requirements and orchestration plan, generate TWO files:

1. agent.py — a complete standalone Python script
2. prompt.md — the prompt template the agent sends to Claude at runtime

CRITICAL: The placeholder names in prompt.md (e.g. {{DATE}}, {{STORIES}}) MUST exactly
match the str.replace() calls in agent.py. Design the placeholders first, then write
the agent code to substitute every one of them. Use UPPER_SNAKE_CASE for placeholder
names wrapped in double curly braces: {{PLACEHOLDER_NAME}}.

=== agent.py rules ===
- Single self-contained Python file, runs via `python agent.py`
- Use the Anthropic SDK to call Claude
- Read its config from a sibling config.yaml
- Read its prompt template from a sibling prompt.md
- Write outputs to a sibling outputs/ directory
- Ping a Healthchecks.io URL on success (if configured)
- Handle errors gracefully with logging
- Be idempotent — safe to run multiple times
- Use str.replace() NOT str.format() for prompt substitution
- Read ANTHROPIC_API_KEY from os.environ (it will be set via .env file)

Structure:
```python
#!/usr/bin/env python3
\"\"\"SOFT CAT Agent: {name} — {summary}\"\"\"

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import httpx
import yaml

# ... agent logic ...

def main():
    # Load config
    # Execute agent logic
    # Write output
    # Ping healthcheck

if __name__ == "__main__":
    main()
```

=== prompt.md rules ===
- Clearly state the task
- Define the expected output format
- Include any constraints or rules
- Use {{PLACEHOLDER_NAME}} for runtime data — every placeholder must be substituted by agent.py

=== Response format ===
Respond with EXACTLY this structure. No other text before or after.

===AGENT_CODE===
<the complete Python code, no markdown fences>
===PROMPT_TEMPLATE===
<the complete prompt markdown, no markdown fences>
"""


class Fabricator:
    """F — Fabricate phase of the S.O.F.T.C.A.T pipeline.

    Generates the agent code, prompt template, and config file.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

        # Try package templates first, fall back to config dir
        try:
            self.jinja_env = Environment(
                loader=PackageLoader("softcat", "templates"),
                keep_trailing_newline=True,
            )
        except Exception:
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(config.templates_dir)),
                keep_trailing_newline=True,
            )

    def fabricate(
        self,
        agent_name: str,
        scan: ScanResult,
        plan: OrchestrationPlan,
    ) -> Path:
        """Generate a complete agent directory."""
        agent_dir = self.config.agents_dir / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "outputs").mkdir(exist_ok=True)

        # Generate agent.py and prompt.md together in one Claude call
        agent_code, prompt_template = self._generate_agent_and_prompt(
            agent_name, scan, plan
        )
        (agent_dir / "agent.py").write_text(agent_code)
        (agent_dir / "agent.py").chmod(0o755)
        (agent_dir / "prompt.md").write_text(prompt_template)

        # Generate config.yaml from structured data
        config_data = {
            "name": agent_name,
            "summary": scan.summary,
            "intent": scan.intent,
            "model": plan.model,
            "schedule": scan.schedule.cron_expression,
            "timezone": scan.schedule.timezone,
            "output_format": scan.output.format,
            "output_destination": scan.output.destination,
            "data_sources": [s.model_dump() for s in scan.data_sources],
            "dependencies": plan.pip_dependencies,
            "healthcheck_url": None,  # Set during Configure phase
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(agent_dir / "config.yaml", "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        # Generate requirements.txt
        (agent_dir / "requirements.txt").write_text(
            "\n".join(plan.pip_dependencies) + "\n"
        )

        console.print(f"   → {agent_dir / 'agent.py'}")
        console.print(f"   → {agent_dir / 'prompt.md'}")
        console.print(f"   → {agent_dir / 'config.yaml'}")

        return agent_dir

    def _generate_agent_and_prompt(
        self, name: str, scan: ScanResult, plan: OrchestrationPlan
    ) -> tuple[str, str]:
        """Use a single Claude call to generate both agent.py and prompt.md."""
        context = (
            f"Agent name: {name}\n"
            f"Summary: {scan.summary}\n"
            f"Intent: {scan.intent}\n"
            f"Data sources: {json.dumps([s.model_dump() for s in scan.data_sources])}\n"
            f"Output format: {scan.output.format}\n"
            f"Output destination: {scan.output.destination}\n"
            f"Output description: {scan.output.description}\n"
            f"Model to use at runtime: {plan.model}\n"
            f"Dependencies available: {', '.join(plan.pip_dependencies)}\n"
            f"MCP servers: {json.dumps(plan.mcp_servers)}\n"
        )

        response = self.client.messages.create(
            model=plan.model,
            max_tokens=6000,
            system=FABRICATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        raw = response.content[0].text.strip()
        agent_code, prompt_template = self._parse_fabrication_response(raw)
        self._validate_placeholders(agent_code, prompt_template)
        return agent_code, prompt_template

    def _parse_fabrication_response(self, raw: str) -> tuple[str, str]:
        """Split the unified response into agent code and prompt template."""
        code_marker = "===AGENT_CODE==="
        prompt_marker = "===PROMPT_TEMPLATE==="

        if code_marker not in raw or prompt_marker not in raw:
            console.print(
                "[yellow]⚠ Response missing delimiters, attempting fallback parse[/yellow]"
            )
            # Fallback: assume everything before ===PROMPT_TEMPLATE=== is code
            # or if no markers at all, treat as code-only (prompt will be empty)
            if prompt_marker in raw:
                parts = raw.split(prompt_marker, 1)
                return self._strip_fences(parts[0].strip()), parts[1].strip()
            return self._strip_fences(raw), ""

        # Split on markers
        after_code = raw.split(code_marker, 1)[1]
        parts = after_code.split(prompt_marker, 1)

        agent_code = self._strip_fences(parts[0].strip())
        prompt_template = parts[1].strip() if len(parts) > 1 else ""

        return agent_code, prompt_template

    def _validate_placeholders(self, agent_code: str, prompt_template: str) -> None:
        """Check that all prompt placeholders appear in the agent code."""
        placeholders = set(re.findall(r"\{\{([A-Z_]+)\}\}", prompt_template))
        if not placeholders:
            return

        missing = [p for p in placeholders if f"{{{{{p}}}}}" not in agent_code]
        if missing:
            console.print(
                f"[yellow]⚠ Prompt placeholders not found in agent code: "
                f"{', '.join('{{' + p + '}}' for p in missing)}[/yellow]"
            )

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Strip markdown code fences from Claude's response."""
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return text
