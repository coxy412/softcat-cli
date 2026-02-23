"""O — Orchestrate: Select the right model, tools, and template for the job."""

from __future__ import annotations

from pydantic import BaseModel, Field

from softcat.config import Config
from softcat.core.scanner import ScanResult
from softcat.mcp.registry import MCPRegistry


class OrchestrationPlan(BaseModel):
    """The plan for building the agent."""

    model: str = "claude-sonnet-4-5-20250929"
    template: str = "base"
    mcp_servers: list[dict] = Field(default_factory=list)
    pip_dependencies: list[str] = Field(default_factory=list)
    environment_vars: list[str] = Field(default_factory=list)
    estimated_cost_per_run: float = 0.0

    def __str__(self) -> str:
        mcps = ", ".join(s.get("name", "?") for s in self.mcp_servers) or "none"
        deps = ", ".join(self.pip_dependencies) or "none"
        return (
            f"Template: {self.template}\n"
            f"Model: {self.model}\n"
            f"MCP servers: {mcps}\n"
            f"Dependencies: {deps}\n"
            f"Est. cost/run: ${self.estimated_cost_per_run:.4f}"
        )


# Template selection based on agent intent
INTENT_TEMPLATE_MAP = {
    "digest": "digest",
    "monitor": "monitor",
    "transformer": "transformer",
    "responder": "responder",
    "custom": "base",
}

# Model selection based on complexity
COMPLEXITY_MODEL_MAP = {
    "simple": "claude-haiku-4-5-20251001",
    "moderate": "claude-sonnet-4-5-20250929",
    "complex": "claude-sonnet-4-5-20250929",
}

# Approximate cost per 1K tokens (input + output blended)
MODEL_COST_PER_1K = {
    "claude-haiku-4-5-20251001": 0.001,
    "claude-sonnet-4-5-20250929": 0.006,
}


class Orchestrator:
    """O — Orchestrate phase of the S.O.F.T.C.A.T pipeline.

    Given scan results, determines the optimal model, template,
    MCP servers, and dependencies for the agent.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.mcp_registry = MCPRegistry()

    def plan(self, scan: ScanResult) -> OrchestrationPlan:
        """Create an orchestration plan from scan results."""

        # Select template
        template = INTENT_TEMPLATE_MAP.get(scan.intent, "base")

        # Select model — use scan complexity unless overridden
        model = COMPLEXITY_MODEL_MAP.get(scan.complexity, self.config.default_model)

        # Resolve MCP servers
        mcp_servers = []
        for server_name in scan.mcp_servers:
            server_info = self.mcp_registry.get(server_name)
            if server_info:
                mcp_servers.append(server_info)

        # Build dependency list
        pip_deps = list(scan.dependencies)

        # Add standard deps based on data sources
        source_types = {s.type for s in scan.data_sources}
        if "rss" in source_types:
            pip_deps.append("feedparser")
        if "web" in source_types:
            pip_deps.append("beautifulsoup4")
        if "api" in source_types and "httpx" not in pip_deps:
            pip_deps.append("httpx")

        # Always need these
        for required in ["anthropic", "httpx", "pyyaml"]:
            if required not in pip_deps:
                pip_deps.append(required)

        # Deduplicate
        pip_deps = sorted(set(pip_deps))

        # Environment vars needed
        env_vars = ["ANTHROPIC_API_KEY"]
        if self.config.healthchecks.api_key:
            env_vars.append("HEALTHCHECKS_API_KEY")

        # Estimate cost
        tokens = scan.estimated_tokens_per_run
        cost_per_1k = MODEL_COST_PER_1K.get(model, 0.006)
        estimated_cost = (tokens / 1000) * cost_per_1k

        return OrchestrationPlan(
            model=model,
            template=template,
            mcp_servers=mcp_servers,
            pip_dependencies=pip_deps,
            environment_vars=env_vars,
            estimated_cost_per_run=estimated_cost,
        )
