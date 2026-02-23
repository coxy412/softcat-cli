"""C — Configure: Set up deployment scheduling, monitoring, and environment."""

from __future__ import annotations

import httpx
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from rich.console import Console

from softcat.config import Config
from softcat.core.orchestrator import OrchestrationPlan
from softcat.core.scanner import ScanResult

console = Console()


class DeployConfig(BaseModel):
    """Deployment configuration for an agent."""

    schedule: str = "0 6 * * *"
    timezone: str = "UTC"
    healthcheck_url: str | None = None
    healthcheck_id: str | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    restart_on_failure: bool = True
    max_retries: int = 3


class Configurator:
    """C — Configure phase of the S.O.F.T.C.A.T pipeline.

    Sets up cron scheduling, Healthchecks.io monitoring,
    and environment configuration.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def configure(
        self,
        agent_name: str,
        scan: ScanResult,
        plan: OrchestrationPlan,
    ) -> DeployConfig:
        """Create deployment configuration for an agent."""
        deploy = DeployConfig(
            schedule=scan.schedule.cron_expression,
            timezone=scan.schedule.timezone,
        )

        # Set up Healthchecks.io if configured
        if self.config.healthchecks.api_key:
            hc = self._create_healthcheck(agent_name, scan, deploy)
            if hc:
                deploy.healthcheck_url = hc["ping_url"]
                deploy.healthcheck_id = hc["id"]
                console.print(f"   → healthcheck: {deploy.healthcheck_url}")

                # Update agent config.yaml with healthcheck URL
                agent_config_path = self.config.agents_dir / agent_name / "config.yaml"
                if agent_config_path.exists():
                    with open(agent_config_path) as f:
                        agent_config = yaml.safe_load(f) or {}
                    agent_config["healthcheck_url"] = deploy.healthcheck_url
                    with open(agent_config_path, "w") as f:
                        yaml.dump(agent_config, f, default_flow_style=False, sort_keys=False)

        # Build env vars
        deploy.env_vars = {
            "ANTHROPIC_API_KEY": self.config.anthropic_api_key or "",
            "SOFTCAT_AGENT_NAME": agent_name,
        }

        return deploy

    def _create_healthcheck(
        self,
        agent_name: str,
        scan: ScanResult,
        deploy: DeployConfig,
    ) -> dict | None:
        """Create a Healthchecks.io check for this agent."""
        try:
            response = httpx.post(
                "https://healthchecks.io/api/v3/checks/",
                headers={"X-Api-Key": self.config.healthchecks.api_key},
                json={
                    "name": f"softcat/{agent_name}",
                    "tags": f"softcat {scan.intent}",
                    "desc": scan.summary,
                    "schedule": deploy.schedule,
                    "tz": deploy.timezone,
                    "grace": 3600,  # 1 hour grace period
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            console.print(f"[dim]   ⚠ Healthcheck creation failed: {e}[/dim]")
            return None
