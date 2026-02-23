"""T — Track: Monitor agent health, log outputs, detect and recover from failures."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import yaml
from pathlib import Path
from rich.console import Console

from softcat.config import Config
from softcat.core.configurator import DeployConfig

console = Console()


class AgentHealth:
    """Health status of an agent."""

    def __init__(
        self,
        name: str,
        status: str = "unknown",
        last_ping: str | None = None,
        last_output: str | None = None,
        output_count: int = 0,
    ) -> None:
        self.name = name
        self.status = status
        self.last_ping = last_ping
        self.last_output = last_output
        self.output_count = output_count


class Tracker:
    """T — Track phase of the S.O.F.T.C.A.T pipeline.

    Monitors running agents via Healthchecks.io and local output logs.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def register(self, agent_name: str, deploy: DeployConfig) -> None:
        """Register an agent for tracking."""
        tracking_file = self.config.agents_dir / agent_name / ".tracking"
        tracking_data = {
            "healthcheck_url": deploy.healthcheck_url,
            "healthcheck_id": deploy.healthcheck_id,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "schedule": deploy.schedule,
        }

        with open(tracking_file, "w") as f:
            yaml.dump(tracking_data, f, default_flow_style=False)

    def check_health(self, agent_name: str) -> AgentHealth:
        """Check the health of a specific agent."""
        agent_dir = self.config.agents_dir / agent_name
        health = AgentHealth(name=agent_name)

        # Check local status
        status_file = agent_dir / ".status"
        if status_file.exists():
            health.status = status_file.read_text().strip()

        # Count outputs
        outputs_dir = agent_dir / "outputs"
        if outputs_dir.exists():
            output_files = sorted(outputs_dir.iterdir())
            health.output_count = len(output_files)
            if output_files:
                health.last_output = output_files[-1].name

        # Check Healthchecks.io if configured
        tracking_file = agent_dir / ".tracking"
        if tracking_file.exists() and self.config.healthchecks.api_key:
            with open(tracking_file) as f:
                tracking = yaml.safe_load(f) or {}

            hc_id = tracking.get("healthcheck_id")
            if hc_id:
                hc_status = self._check_healthchecks(hc_id)
                if hc_status:
                    health.last_ping = hc_status.get("last_ping")
                    hc_state = hc_status.get("status", "unknown")
                    status_map = {
                        "up": "active",
                        "down": "error",
                        "grace": "grace",
                        "paused": "paused",
                        "new": "active",
                        "started": "active",
                    }
                    if hc_state in status_map:
                        health.status = status_map[hc_state]

        return health

    def check_all(self) -> list[AgentHealth]:
        """Check health of all agents."""
        results = []
        if self.config.agents_dir.exists():
            for agent_dir in sorted(self.config.agents_dir.iterdir()):
                if agent_dir.is_dir() and (agent_dir / "agent.py").exists():
                    results.append(self.check_health(agent_dir.name))
        return results

    def _check_healthchecks(self, check_id: str) -> dict | None:
        """Query Healthchecks.io for a check's status."""
        try:
            response = httpx.get(
                f"https://healthchecks.io/api/v3/checks/{check_id}",
                headers={"X-Api-Key": self.config.healthchecks.api_key},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
