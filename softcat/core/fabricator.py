"""F — Fabricate: Generate agent code, prompts, and configuration."""

from __future__ import annotations

import json
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
You are the SOFT CAT Fabricator. You generate production-ready Python agent code.

Given the agent requirements and orchestration plan, generate a complete agent.py
that can run standalone via `python agent.py`.

The agent MUST:
1. Be a single self-contained Python file
2. Use the Anthropic SDK to call Claude
3. Read its config from a sibling config.yaml
4. Read its prompt template from a sibling prompt.md
5. Write outputs to a sibling outputs/ directory
6. Ping a Healthchecks.io URL on success (if configured)
7. Handle errors gracefully with logging
8. Be idempotent — safe to run multiple times
9. When substituting variables into the prompt template, use str.replace() NOT str.format() — the prompt may contain curly braces that are not Python format specifiers
10. Read ANTHROPIC_API_KEY from os.environ (it will be set via .env file)

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

Respond ONLY with the Python code. No markdown fences. No explanation.
"""

PROMPT_TEMPLATE_SYSTEM = """\
You are the SOFT CAT Fabricator generating a prompt template for an AI agent.

Given the agent requirements, write a clear prompt.md that the agent will send
to Claude at runtime. The prompt should:
1. Clearly state the task
2. Define the expected output format
3. Include any constraints or rules
4. Be parameterised with {placeholders} for runtime data

Respond ONLY with the markdown content. No code fences.
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

        # Generate agent.py via Claude
        agent_code = self._generate_agent_code(agent_name, scan, plan)
        (agent_dir / "agent.py").write_text(agent_code)
        (agent_dir / "agent.py").chmod(0o755)

        # Generate prompt.md via Claude
        prompt_template = self._generate_prompt_template(scan, plan.model)
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

    def _generate_agent_code(
        self, name: str, scan: ScanResult, plan: OrchestrationPlan
    ) -> str:
        """Use Claude to generate the agent Python code."""
        context = (
            f"Agent name: {name}\n"
            f"Summary: {scan.summary}\n"
            f"Intent: {scan.intent}\n"
            f"Data sources: {json.dumps([s.model_dump() for s in scan.data_sources])}\n"
            f"Output format: {scan.output.format}\n"
            f"Output destination: {scan.output.destination}\n"
            f"Model to use at runtime: {plan.model}\n"
            f"Dependencies available: {', '.join(plan.pip_dependencies)}\n"
            f"MCP servers: {json.dumps(plan.mcp_servers)}\n"
        )

        response = self.client.messages.create(
            model=plan.model,
            max_tokens=4000,
            system=FABRICATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        return self._strip_fences(response.content[0].text.strip())

    def _generate_prompt_template(self, scan: ScanResult, model: str | None = None) -> str:
        """Use Claude to generate the runtime prompt template."""
        context = (
            f"Agent summary: {scan.summary}\n"
            f"Intent: {scan.intent}\n"
            f"Output format: {scan.output.format}\n"
            f"Output description: {scan.output.description}\n"
        )

        response = self.client.messages.create(
            model=model or self.config.default_model,
            max_tokens=2000,
            system=PROMPT_TEMPLATE_SYSTEM,
            messages=[{"role": "user", "content": context}],
        )

        return self._strip_fences(response.content[0].text.strip())

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Strip markdown code fences from Claude's response."""
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return text
